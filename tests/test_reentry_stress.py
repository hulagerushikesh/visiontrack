"""The synthetic probe is reproducible and cannot select on held-out events."""

import json
import sys
from dataclasses import replace

import pytest

from experiments import reentry_stress
from experiments.reentry_stress import (
    ProbeEvent,
    calibrate,
    evaluate,
    generate_events,
    operating_curve,
    policy_grid,
    run_probe,
)


def test_synthetic_probe_is_repeatable_and_tracks_novel_and_expired_returns() -> None:
    a = generate_events(seed=9, gallery_size=10, events=200)
    b = generate_events(seed=9, gallery_size=10, events=200)
    assert a == b
    assert any(event.truth_id is None for event in a)
    assert any(event.truth_id and event.truth_id.startswith("expired-") for event in a)
    result = evaluate(a, threshold=-1, margin=0)
    assert result["restoration_coverage"] == 1
    assert result["false_restorations"] > 0


def test_abstain_all_is_safe_but_has_no_restoration_recall() -> None:
    events = generate_events(seed=4, gallery_size=10, events=100)
    result = evaluate(events, threshold=1, margin=2)
    assert result["correct_restorations"] == 0
    assert result["false_restorations"] == 0
    assert result["selective_risk"] is None
    assert result["eligible_return_recall"] == 0


def test_development_calibration_and_held_out_test_are_separate() -> None:
    development = generate_events(seed=4, gallery_size=10, events=100)
    test = generate_events(seed=5, gallery_size=10, events=100)
    assert development[0].event_id != test[0].event_id
    assert calibrate(development, allow_margin=True) is None  # insufficient evidence
    result = run_probe(gallery_size=10, events=100, seed=4)
    assert result["calibrated_policies"]["threshold_and_margin"] is None
    assert result["held_out_events"] == 100


def _known_events() -> list[ProbeEvent]:
    candidates = frozenset({"g0", "g1"})
    return [
        ProbeEvent("correct", "g0", candidates, "g0", 0.9, 0.2),
        ProbeEvent("wrong", "g1", candidates, "g0", 0.85, 0.83),
        ProbeEvent("low", "g0", candidates, "g0", 0.35, 0.3),
        ProbeEvent("novel", None, candidates, "g0", 0.8, 0.7),
        ProbeEvent("unavailable", "expired", candidates, "g0", 0.2, 0.1),
    ]


def test_fixed_grid_is_complete_ordered_and_shared_by_both_rules() -> None:
    threshold_only = policy_grid(allow_margin=False)
    with_margin = policy_grid(allow_margin=True)
    assert len(threshold_only) == 10
    assert len(with_margin) == 60
    assert tuple(threshold for threshold, _ in threshold_only) == (
        0,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
        1,
    )
    assert tuple(margin for threshold, margin in with_margin if threshold == 0) == (
        0,
        0.03,
        0.06,
        0.1,
        0.15,
        0.2,
    )
    assert with_margin == tuple(sorted(set(with_margin)))
    assert threshold_only == tuple(point for point in with_margin if point[1] == 0)
    assert with_margin[0] == (0, 0)
    assert with_margin[-1] == (1, 0.2)


def test_curve_counts_and_undefined_rates_match_hand_scored_events() -> None:
    events = _known_events()
    before = events.copy()
    points = operating_curve(events, allow_margin=True)
    assert points == operating_curve(events, allow_margin=True)
    assert events == before
    indexed = {(point["threshold"], point["margin"]): point["metrics"] for point in points}
    forced = indexed[(0, 0)]
    assert forced["opportunities"] == 5
    assert forced["eligible_returns"] == 3
    assert forced["unavailable_returns"] == 1
    assert forced["novel_arrivals"] == 1
    assert forced["attempted_restorations"] == 5
    assert forced["correct_restorations"] == 2
    assert forced["false_restorations"] == 3
    assert forced["selective_risk"] == 3 / 5
    selective = indexed[(0.4, 0.03)]
    assert selective["attempted_restorations"] == 2
    assert selective["correct_restorations"] == 1
    assert selective["false_restorations"] == 1
    assert selective["eligible_return_recall"] == 1 / 3
    assert selective["restoration_coverage"] == 2 / 5
    assert selective["selective_risk"] == 1 / 2
    assert selective["novel_false_match_rate"] == 1
    # The similarity boundary is inclusive, not a strict greater-than gate.
    assert indexed[(0.9, 0)]["correct_restorations"] == 1
    abstain = indexed[(1, 0)]
    assert abstain["attempted_restorations"] == 0
    assert abstain["selective_risk"] is None
    assert abstain["synthetic_risk_upper_95"] is None
    assert abstain["eligible_return_recall"] == 0
    assert abstain["unavailable_abstentions"] == 1
    assert abstain["novel_abstentions"] == 1
    empty = operating_curve([], allow_margin=False)[0]["metrics"]
    assert empty["restoration_coverage"] is None
    assert empty["eligible_return_recall"] is None
    assert empty["novel_false_match_rate"] is None


def test_tightening_gates_reduces_attempts_but_risk_is_not_assumed_monotone() -> None:
    indexed = {
        (point["threshold"], point["margin"]): point["metrics"]
        for point in operating_curve(_known_events(), allow_margin=True)
    }
    thresholds = sorted({threshold for threshold, _ in indexed})
    margins = sorted({margin for _, margin in indexed})
    for threshold, margin in indexed:
        stricter = [
            metrics for (t, m), metrics in indexed.items() if t >= threshold and m >= margin
        ]
        for metric in ("attempted_restorations", "correct_restorations", "false_restorations"):
            assert all(row[metric] <= indexed[(threshold, margin)][metric] for row in stricter)
    assert len(thresholds) == 10 and len(margins) == 6
    # Tightening this threshold removes a correct restore, increasing risk.
    assert indexed[(0.4, 0)]["selective_risk"] > indexed[(0.3, 0)]["selective_risk"]


def test_optional_curves_preserve_the_default_report_and_selected_results() -> None:
    original = run_probe(gallery_size=10, events=100, seed=4)
    expanded = run_probe(gallery_size=10, events=100, seed=4, include_curves=True)
    curves = expanded.pop("operating_curves")
    assert expanded == original
    assert curves["schema_version"] == 1
    assert "not real-data accuracy" in curves["label"]
    assert "must not select" in curves["selection_partition"]
    assert "synthetic events only" in curves["risk_bound_scope"]
    for name, allow_margin in (("threshold_only", False), ("threshold_and_margin", True)):
        rows = curves["policies"][name]
        assert [(row["threshold"], row["margin"]) for row in rows] == list(
            policy_grid(allow_margin=allow_margin)
        )
        assert not any(row["selected_on_development"] for row in rows)  # too few attempts
        for row in rows:
            assert row["development"]["opportunities"] == 100
            assert row["held_out"]["opportunities"] == 100


def test_held_out_truth_cannot_change_development_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    development = [replace(_known_events()[0], event_id=f"dev-{i}") for i in range(500)]
    test = [replace(event, event_id=f"test-{i}") for i, event in enumerate(development)]

    def generate(*, seed: int, **kwargs: int) -> list[ProbeEvent]:
        return development if seed == 4 else test

    monkeypatch.setattr(reentry_stress, "generate_events", generate)
    first = run_probe(seed=4, events=500, include_curves=True)
    test[:] = [replace(event, truth_id=None) for event in test]
    second = run_probe(seed=4, events=500, include_curves=True)
    for name in ("threshold_only", "threshold_and_margin"):
        a, b = first["calibrated_policies"][name], second["calibrated_policies"][name]
        assert a is not None and b is not None
        assert (a["threshold"], a["margin"]) == (b["threshold"], b["margin"])
        assert a["held_out"]["selective_risk"] == 0
        assert b["held_out"]["selective_risk"] == 1
        first_rows = first["operating_curves"]["policies"][name]
        second_rows = second["operating_curves"]["policies"][name]
        assert sum(row["selected_on_development"] for row in first_rows) == 1
        assert sum(row["selected_on_development"] for row in second_rows) == 1
        for dev, changed in zip(first_rows, second_rows, strict=True):
            assert dev["development"] == changed["development"]
            assert dev["selected_on_development"] == changed["selected_on_development"]
        chosen_row = next(row for row in second_rows if row["selected_on_development"])
        assert chosen_row["held_out"]["false_restorations"] == 500
        selected_metrics = chosen_row["held_out"].copy()
        selected_metrics.pop("attempted_restorations")
        assert selected_metrics == b["held_out"]
        assert (chosen_row["threshold"], chosen_row["margin"]) == (b["threshold"], b["margin"])


def test_cli_curves_are_opt_in_strict_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["reentry_stress", "--gallery-size", "10", "--events", "5", "--seed", "4"]
    monkeypatch.setattr(sys, "argv", args)
    reentry_stress.main()
    default = json.loads(capsys.readouterr().out)
    assert "operating_curves" not in default
    monkeypatch.setattr(sys, "argv", [*args, "--include-curves"])
    reentry_stress.main()
    output = capsys.readouterr()
    assert output.err == ""
    assert "NaN" not in output.out and "Infinity" not in output.out
    expanded = json.loads(output.out)
    assert "operating_curves" in expanded
    assert expanded["calibrated_policies"] == default["calibrated_policies"]
