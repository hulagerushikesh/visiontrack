"""Hand-worked numerical tables, NOT measured tracker or held-out results."""

import copy
import math

import pytest

from experiments import box_gate_decision as decision
from experiments.box_gate_protocol import load_registration
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import _sha


@pytest.fixture(autouse=True)
def no_tracker_or_inputs(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("numerical rule fixtures must not execute trackers or generate observations")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.box_gate_scene.generate_inputs", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)


def endpoints():
    return {
        name: None if name.endswith(("mean_frames", "mean_world", "mean_distance_world")) else 0
        for name in decision.ENDPOINTS
    }


@pytest.fixture
def table():
    spec, _ = load_registration()
    parent, _ = load_frozen_protocol()
    rows = []
    for split in ("development", "heldout"):
        for scenario, seed, condition in decision.cases(spec, parent, split):
            baseline, candidate = endpoints(), endpoints()
            objects = len(spec["scenarios"][scenario])
            if condition in spec["evaluation"]["error_conditions"]:
                baseline["tracking.id_switches"] = 4 * objects
                candidate["tracking.id_switches"] = 2 * objects
            rows.append(
                {
                    "split": split,
                    "scenario": scenario,
                    "seed": seed,
                    "condition": condition,
                    "endpoints": {"baseline": baseline, "gate_off": candidate},
                }
            )
    return rows


def test_complete_pass_exact_per_object_denominator_and_digest(table):
    result = decision.evaluate_rules(table)
    assert result["classification"] == "pass"
    for split in result["splits"]:
        assert split["complete"] and split["adequate_challenge"] and split["benefit_margin_met"]
        assert split["regressions"] == []
        for scene in split["scenarios"]:
            assert scene["error_cases"] == 20
            assert scene["baseline_primary"] == 4
            assert scene["gate_off_primary"] == 2
            assert scene["absolute_reduction"] == 2
            assert scene["relative_reduction"] == 0.5
    assert result["provenance_verified_by_rules"] is False
    assert result["tracker_execution_established_by_rules"] is False
    assert result["production_change_authorized"] is result["cpp_port_authorized"] is False
    digest = result.pop("rules_sha256")
    assert digest == _sha(result)


@pytest.mark.parametrize("split", ["development", "heldout"])
@pytest.mark.parametrize("endpoint", list(decision.SAFETY.values()))
def test_single_control_regression_cannot_be_averaged_away(table, split, endpoint):
    row = next(r for r in table if r["split"] == split and r["condition"] == "control")
    row["endpoints"]["gate_off"][endpoint] = 1
    result = decision.evaluate_rules(table)
    assert result["classification"] == "failure"
    selected = next(s for s in result["splits"] if s["split"] == split)
    assert selected["benefit_margin_met"]
    assert selected["regressions"] == [
        {
            "scenario": row["scenario"],
            "seed": row["seed"],
            "condition": "control",
            "endpoint": endpoint,
            "baseline": 0,
            "gate_off": 1,
            "increase": 1,
        }
    ]


def test_two_improved_scenarios_required_independently_in_each_split(table):
    for row in table:
        if row["split"] == "heldout" and row["scenario"] != "gate_test_solo":
            row["endpoints"]["gate_off"] = copy.deepcopy(row["endpoints"]["baseline"])
    result = decision.evaluate_rules(table)
    assert result["classification"] == "failure"
    assert result["splits"][0]["benefit_margin_met"]
    assert not result["splits"][1]["benefit_margin_met"]


def test_no_effect_is_not_failure_or_pass_if_challenge_is_adequate(table):
    for row in table:
        row["endpoints"]["gate_off"] = copy.deepcopy(row["endpoints"]["baseline"])
    result = decision.evaluate_rules(table)
    assert result["classification"] == "no_effect"
    assert all(s["all_endpoints_identical"] for s in result["splits"])


def test_secondary_difference_breaks_all_37_no_effect_but_not_benefit_margin(table):
    for row in table:
        row["endpoints"]["gate_off"] = copy.deepcopy(row["endpoints"]["baseline"])
    table[0]["endpoints"]["gate_off"]["crossing.box_centre.matched_x_abs_mean_world"] = 0.1
    result = decision.evaluate_rules(table)
    assert result["classification"] == "failure"
    assert not result["splits"][0]["all_endpoints_identical"]
    assert not result["splits"][0]["regressions"]


def test_inadequate_challenge_precedes_regressions_and_no_effect(table):
    for row in table:
        for value in row["endpoints"].values():
            value["tracking.id_switches"] = 0
    table[0]["endpoints"]["gate_off"]["tracking.false_positive_rows"] = 1
    result = decision.evaluate_rules(table)
    assert result["classification"] == "inconclusive"
    assert result["splits"][0]["regressions"]
    assert all(
        s["relative_reduction"] is None for split in result["splits"] for s in split["scenarios"]
    )


@pytest.mark.parametrize("missing", ["development", "heldout"])
def test_development_or_heldout_alone_is_never_overall_pass(table, missing):
    result = decision.evaluate_rules([r for r in table if r["split"] != missing])
    assert result["classification"] == "inconclusive"
    absent = next(s for s in result["splits"] if s["split"] == missing)
    assert len(absent["missing_cases"]) == 120 and not absent["complete"]


def test_challenge_and_absolute_margin_exact_half_switch_boundary(table):
    spec, _ = load_registration()
    for row in table:
        objects = len(spec["scenarios"][row["scenario"]])
        for value in row["endpoints"].values():
            value["tracking.id_switches"] = 0
        if row["condition"] == "box_error_only":
            row["endpoints"]["baseline"]["tracking.id_switches"] = objects
    result = decision.evaluate_rules(table)
    assert result["classification"] == "pass"
    assert all(
        s["baseline_primary"] == 0.5 and s["absolute_reduction"] == 0.5
        for split in result["splits"]
        for s in split["scenarios"]
    )
    for row in table:
        if row["condition"] == "box_error_only" and row["seed"] in (2001, 4001):
            row["endpoints"]["baseline"]["tracking.id_switches"] -= 1
    assert decision.evaluate_rules(table)["classification"] == "inconclusive"


def test_relative_margin_exact_quarter_and_one_switch_below(table):
    spec, _ = load_registration()
    for row in table:
        if row["condition"] in ("box_error_only", "combined"):
            row["endpoints"]["gate_off"]["tracking.id_switches"] = 3 * len(
                spec["scenarios"][row["scenario"]]
            )
    assert decision.evaluate_rules(table)["classification"] == "pass"
    for row in table:
        if row["condition"] == "box_error_only" and row["seed"] in (2001, 4001):
            row["endpoints"]["gate_off"]["tracking.id_switches"] += 1
    result = decision.evaluate_rules(table)
    assert result["classification"] == "failure"
    assert not any(s["regressions"] for s in result["splits"])


def test_absolute_margin_required_even_with_large_relative_reduction(table):
    spec, _ = load_registration()
    for row in table:
        objects = len(spec["scenarios"][row["scenario"]])
        if row["condition"] in ("box_error_only", "combined"):
            row["endpoints"]["baseline"]["tracking.id_switches"] = objects
            row["endpoints"]["gate_off"]["tracking.id_switches"] = objects
            if row["condition"] == "box_error_only" and row["seed"] not in (2001, 4001):
                row["endpoints"]["gate_off"]["tracking.id_switches"] = 0
    result = decision.evaluate_rules(table)
    assert result["classification"] == "failure"
    assert all(
        s["absolute_reduction"] == 0.45 and s["relative_reduction"] == 0.45
        for split in result["splits"]
        for s in split["scenarios"]
    )


@pytest.mark.parametrize("bad", [True, 1.0, None, -1, math.nan, math.inf, "1"])
def test_invalid_primary_is_inconclusive_not_coerced(table, bad):
    table[0]["endpoints"]["baseline"]["tracking.id_switches"] = bad
    result = decision.evaluate_rules(table)
    assert result["classification"] == "inconclusive" and result["invalid_evidence"]


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "extra",
        "missing_endpoint",
        "missing_variant",
        "bool_seed",
        "bad_split",
        "fraction",
        "null_count",
    ],
)
def test_malformed_tables_are_inconclusive(table, change):
    if change == "duplicate":
        table[-1] = table[0]
    elif change == "extra":
        table.append(table[0])
    elif change == "missing_endpoint":
        table[0]["endpoints"]["baseline"].pop("tracking.fragmentations")
    elif change == "missing_variant":
        table[0]["endpoints"].pop("gate_off")
    elif change == "bool_seed":
        table[0]["seed"] = True
    elif change == "bad_split":
        table[0]["split"] = "old_heldout"
    elif change == "fraction":
        table[0]["endpoints"]["baseline"]["crossing.bottom_centre.recall"] = 1.1
    else:
        table[0]["endpoints"]["baseline"]["tracking.false_positive_rows"] = None
    result = decision.evaluate_rules(table)
    assert result["classification"] == "inconclusive" and result["invalid_evidence"]


def test_inputs_not_mutated_or_reordered_and_empty_is_inconclusive(table):
    original = copy.deepcopy(table)
    assert decision.evaluate_rules(list(reversed(table)))["classification"] == "pass"
    assert table == original
    assert decision.evaluate_rules([])["classification"] == "inconclusive"
