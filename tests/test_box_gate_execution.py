"""Held-out gate plumbing and hand-fed scorer fixtures, NEVER actual tracking.

Geometry may be generated before opening; every constructed replay object below
is an explicit empty-output double. Fixture exports are not research evidence.
"""

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from experiments import box_gate_execution as execution
from experiments import box_gate_holdout as holdout
from experiments import box_gate_report as report
from experiments import box_gate_runner as runner
from experiments import box_gate_scoring as scoring
from experiments.box_gate_decision import ENDPOINTS, cases
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_scene import generate_inputs
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_report import _sha
from experiments.traffic_runner import _environment, _json_bytes, _verify_tree
from visiontrack.tracking.config import TrackerConfig


@pytest.fixture(autouse=True)
def forbid_real_tracking(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("gate tests must not execute an actual tracker or the old scene generator")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)
    monkeypatch.setattr(runner, "_construct", forbidden)


@pytest.fixture(scope="module")
def geometry():
    spec, _ = load_registration()
    parent, _ = load_frozen_protocol()
    return [
        generate_inputs(split="heldout", scenario=s, seed=n, condition=c).manifest()
        for s, n, c in cases(spec, parent, "heldout")
    ]


@pytest.fixture
def prepared(tmp_path, monkeypatch, geometry):
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    source = runner._snapshot()
    source["worktree_dirty"] = False  # Explicit provenance double, not a clean-checkout claim.
    state = {
        "protocol_id": spec["protocol_id"], "protocol_hashes": hashes, "registration": spec,
        "source": {"replay_source": source, "harness_sha256": {"fixture": "a" * 64}},
        "baseline_source": _verify_tree(ROOT, spec["baseline_revision"]),
        "environment": _environment(),
        "configurations": [
            {"id": v["id"], "settings": {**parent["tracker_config"], **v["config_patch"]}}
            for v in spec["variants"]
        ],
    }
    evidence = {"environment": state["environment"], "safety_endpoint_violations": 174,
                "candidate_accepted": False, "fixture_only": True}
    monkeypatch.setattr(holdout, "_state", lambda: copy.deepcopy(state))
    monkeypatch.setattr(holdout, "_inputs", lambda: copy.deepcopy(geometry))
    monkeypatch.setattr(holdout, "_development_evidence", lambda p: copy.deepcopy(evidence))
    monkeypatch.setattr(runner, "_snapshot", lambda: copy.deepcopy(source))
    freeze = holdout.prepare_freeze(tmp_path / "freeze", development_bundle=tmp_path / "dev")
    return tmp_path / "freeze" / "freeze.json", tmp_path / "output", freeze


def load(path):
    return json.loads(path.read_bytes())


def sealed(value, field):
    value.pop(field, None)
    value[field] = _sha(value)
    return value


@pytest.mark.parametrize("scenario,time", [
    ("gate_test_solo", 149.5), ("gate_test_slanted", 299 * 8 / 14),
    ("gate_test_close", 299 * 6 / 14),
])
@pytest.mark.parametrize("condition", ["control", "perspective_only", "box_error_only", "combined"])
def test_private_heldout_reference_ideal_rows_are_hand_fed_not_tracker_results(
    scenario, time, condition,
):
    scene = generate_inputs(split="heldout", scenario=scenario, seed=4001, condition=condition)
    rows = [
        {"frame": f, "track_id": identity + 10, "xyxy": box.tolist(), "score": .9, "class_id": 0}
        for f, boxes in enumerate(scene.ideal_boxes)
        for identity, box in zip(scene.object_ids, boxes, strict=True)
    ]
    original = copy.deepcopy(rows)
    result = execution._score_heldout(scene, rows)
    assert rows == original
    assert result["format"] == "visiontrack.box-gate-heldout-scoring/v1"
    assert result["tracker_executed_by_scorer"] is result["heldout_opened_by_scorer"] is False
    assert result["endpoints"]["tracking.id_switches"] == 0
    assert result["endpoints"]["tracking.missed_object_frames"] == 0
    assert result["endpoints"]["crossing.bottom_centre.event_error"] == 0
    assert set(result["endpoints"]) == ENDPOINTS
    assert [e["frame_time"] for e in result["crossing"]["bottom_centre"]["truth_events"]] == (
        pytest.approx([time] * len(scene.object_ids))
    )


def test_private_scorer_retains_nulls_and_rejects_wrong_split_or_forged_geometry():
    scene = generate_inputs(split="heldout", scenario="gate_test_solo", seed=4001,
                            condition="control")
    result = execution._score_heldout(scene, [])
    assert result["endpoints"]["crossing.bottom_centre.matched_time_abs_mean_frames"] is None
    assert result["endpoints"]["tracking.missed_object_frames"] == 300
    with pytest.raises(ValueError):
        execution._score_heldout(replace(scene, split="development"), [])
    changed = scene.observed_boxes.copy()
    changed[0, 0, 0] += 1
    with pytest.raises(ValueError, match="observed_boxes"):
        execution._score_heldout(replace(scene, observed_boxes=changed), [])


def test_public_development_guards_still_reject_before_generation(monkeypatch):
    scene = generate_inputs(split="heldout", scenario="gate_test_solo", seed=4001,
                            condition="control")

    def forbidden(*args, **kwargs):
        pytest.fail("development wrapper generated held-out geometry")

    monkeypatch.setattr(scoring, "generate_inputs", forbidden)
    with pytest.raises(ValueError, match="development"):
        scoring.score_development(scene, [])
    with pytest.raises(ValueError, match="development"):
        report._validate_pair({}, scene, {}, {}, {})
    with pytest.raises(ValueError):
        runner.run_development(scenario="gate_test_solo", seed=4001, condition="control")


def install_grid_double(monkeypatch, prepared):
    """Minimal structural records; validation is doubled only for export plumbing."""
    freeze_path, output, freeze = prepared
    calls = []

    def replay(scene, spec, hashes, parent, scorer, sink):
        # Assert the claim, full preplanned grid and durable plan predate replay.
        opening = load(freeze_path.parent / "opening.json")
        assert opening["freeze_sha256"] == freeze["freeze_sha256"]
        assert opening["output"] == str(output)
        assert load(output / "plan.json")["inputs"] == freeze["inputs"]
        calls.append((scene.scenario, scene.seed, scene.condition))
        endpoints = {name: 0 for name in ENDPOINTS}
        variants = [
            {"id": v["id"], "scoring": {"endpoints": copy.deepcopy(endpoints)}}
            for v in spec["variants"]
        ]
        for variant in variants:
            sink(variant["id"], _json_bytes(variant))
        return {"input": scene.manifest(), "variants": variants,
                "candidate_minus_baseline": {name: 0 for name in ENDPOINTS}}

    monkeypatch.setattr(execution, "_run_pair", replay)
    monkeypatch.setattr(execution, "_validate_pair_core", lambda *args: None)
    return calls, replay


def test_full_ordered_grid_retained_and_claim_consumed(prepared, monkeypatch):
    calls, _ = install_grid_double(monkeypatch, prepared)
    path, output, freeze = prepared
    progress = []
    result = execution.run_heldout(
        path, output, progress=lambda n, total: progress.append((n, total)),
    )
    assert result["status"] == "complete"
    assert result["planned_pairs"] == result["attempted_pairs"] == result["successful_pairs"] == 120
    assert result["unattempted_pairs"] == 0 and result["error"] is None
    assert calls == [(m["scenario"], m["seed"], m["condition"]) for m in freeze["inputs"]]
    assert progress == [(n, 120) for n in range(1, 121)]
    assert result["opening_consumed"] and result["heldout_tracking_executed"]
    assert result["candidate_accepted"] is result["production_change_authorized"] is False
    assert result["cpp_port_authorized"] is result["complete_study_report"] is False
    assert len(result["files_sha256"]) == 364
    assert len(list(output.rglob("*.json"))) == 363
    for name, digest in result["files_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert load(output / "manifest.json") == result
    body = dict(result)
    digest = body.pop("manifest_sha256")
    assert digest == _sha(body)
    summary = load(output / "summary.json")
    assert summary["complete_heldout_grid"] and summary["heldout_tracking_executed"]
    assert summary["numerical_rules"]["classification"] == "inconclusive"
    assert summary["numerical_rules"]["splits"][0]["complete"] is False
    assert summary["numerical_rules"]["splits"][1]["complete"] is True
    ledger = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
    assert len(ledger) == 480
    assert [r["event"] for r in ledger[:4]] == [
        "start", "variant_retained", "variant_retained", "success",
    ]
    with pytest.raises(FileExistsError, match="claimed"):
        execution.run_heldout(path, output.parent / "other")
    assert len(calls) == 120


@pytest.mark.parametrize("failure", ["before_variant", "after_baseline", "after_pair", "interrupt"])
def test_failed_or_interrupted_opening_cannot_retry_and_preserves_partial(
    prepared, monkeypatch, failure,
):
    calls, normal = install_grid_double(monkeypatch, prepared)
    path, output, _ = prepared

    def fail(scene, spec, hashes, parent, scorer, sink):
        if failure == "after_pair":
            return normal(scene, spec, hashes, parent, scorer, sink)
        calls.append((scene.scenario, scene.seed, scene.condition))
        if failure in {"after_baseline", "interrupt"}:
            sink("baseline", _json_bytes({"id": "baseline", "fixture": True}))
        if failure == "interrupt":
            raise KeyboardInterrupt("test interruption")
        raise ValueError("test candidate failure")

    monkeypatch.setattr(execution, "_run_pair", fail)
    if failure == "after_pair":
        def reject(*args):
            raise ValueError("invalid pair fixture")
        monkeypatch.setattr(execution, "_validate_pair_core", reject)
    if failure == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            execution.run_heldout(path, output)
        assert not (output / "manifest.json").exists()
    else:
        result = execution.run_heldout(path, output)
        assert result["status"] == "failed"
        assert result["attempted_pairs"] == 1 and result["successful_pairs"] == 0
        assert result["unattempted_pairs"] == 119
        expected_execution = None if failure == "before_variant" else True
        assert result["heldout_tracking_executed"] is expected_execution
        assert not (output / "summary.json").exists()
    prefix = output / "pairs" / "gate_test_solo" / "4001" / "control"
    assert (prefix / "baseline.json").exists() is (failure != "before_variant")
    assert (prefix / "pair.json").exists() is (failure == "after_pair")
    assert len(calls) == 1
    assert (path.parent / "opening.json").exists()
    with pytest.raises(FileExistsError):
        execution.run_heldout(path, output.parent / "retry")
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["state", "freeze", "claim", "inputs", "variant_order"])
def test_drift_or_wrong_order_stops_first_pair_without_later_attempts(
    prepared, monkeypatch, failure,
):
    calls, normal = install_grid_double(monkeypatch, prepared)
    path, output, _ = prepared
    original = execution.generate_inputs

    def generate(**kwargs):
        scene = original(**kwargs)
        if failure == "inputs":
            scene = replace(scene, observed_boxes=scene.observed_boxes + np.array([1, 0, 1, 0]))
        return scene

    monkeypatch.setattr(execution, "generate_inputs", generate)

    def changed(scene, spec, hashes, parent, scorer, sink):
        if failure == "variant_order":
            calls.append((scene.scenario, scene.seed, scene.condition))
            sink("gate_off", b"{}")
        result = normal(scene, spec, hashes, parent, scorer, sink)
        if failure == "freeze":
            path.write_bytes(b"{}")
        elif failure == "claim":
            (path.parent / "opening.json").write_bytes(b"{}")
        elif failure == "state":
            monkeypatch.setattr(holdout, "_state", lambda: {"changed": True})
        return result

    monkeypatch.setattr(execution, "_run_pair", changed)
    result = execution.run_heldout(path, output)
    assert result["status"] == "failed" and result["attempted_pairs"] == 1
    assert result["successful_pairs"] == 0 and len(calls) <= 1
    assert not (output / "summary.json").exists()


@pytest.mark.parametrize("failure", ["missing_freeze", "existing_output", "claimed", "claim_link",
                                     "dirty", "inside_repo", "inside_freeze", "inside_dev"])
def test_preflight_rejects_without_replay(prepared, monkeypatch, failure):
    calls, _ = install_grid_double(monkeypatch, prepared)
    path, output, freeze = prepared
    if failure == "missing_freeze":
        path.unlink()
    elif failure == "existing_output":
        output.mkdir()
    elif failure == "claimed":
        (path.parent / "opening.json").write_bytes(b"existing")
    elif failure == "claim_link":
        (path.parent / "opening.json").symlink_to(path.parent / "missing")
    elif failure == "dirty":
        def dirty():
            raise ValueError("dirty checkout fixture")
        monkeypatch.setattr(holdout, "_state", dirty)
    elif failure == "inside_repo":
        output = ROOT / "not-created-heldout-output"
    elif failure == "inside_freeze":
        output = path.parent / "not-created"
    elif failure == "inside_dev":
        output = Path(freeze["development_bundle"]) / "not-created"
    with pytest.raises((OSError, ValueError)):
        execution.run_heldout(path, output)
    assert not calls


class EmptyDouble:
    def __init__(self, settings):
        self.cfg, self.frame_index = TrackerConfig(**settings), -1

    def update(self, detections):
        self.frame_index += 1
        return []

    def reset(self):
        self.frame_index = -1


def test_actual_adapter_with_empty_doubles_claims_before_construction_and_fully_rescores(
    prepared, monkeypatch,
):
    path, output, freeze = prepared
    instances = []

    def construct(settings):
        assert load(path.parent / "opening.json")["freeze_sha256"] == freeze["freeze_sha256"]
        instances.append(EmptyDouble(settings))
        return instances[-1]

    monkeypatch.setattr(runner, "_construct", construct)
    original = execution._validate_pair_core

    def validate_then_stop(*args):
        original(*args)  # Real full scorer/lineage checks, no tracker implementation.
        raise ValueError("fixture stops deliberately after one fully validated empty-double pair")

    monkeypatch.setattr(execution, "_validate_pair_core", validate_then_stop)
    result = execution.run_heldout(path, output)
    assert result["status"] == "failed" and result["attempted_pairs"] == 1
    assert len(instances) == 4 and len({id(t.cfg) for t in instances}) == 4
    assert [t.cfg.use_mahalanobis_gating for t in instances] == [True, True, False, False]
    pair = load(output / "pairs/gate_test_solo/4001/control/pair.json")
    assert pair["format"] == "visiontrack.box-gate-heldout-pair/v1"
    assert pair["heldout_tracking_executed"]
    assert all(v["replay"]["passes"] == 3 for v in pair["variants"])
    assert all(v["replay"]["updates_per_pass"] == 300 for v in pair["variants"])
    scene = generate_inputs(split="heldout", scenario="gate_test_solo", seed=4001,
                            condition="control")
    for fault in ("heldout_flag", "seed", "reset", "bool_updates", "config", "endpoints",
                  "diagnostics", "receipt", "delta", "source", "input_bool", "scoring_hash"):
        changed = copy.deepcopy(pair)
        variant = changed["variants"][1]
        if fault == "heldout_flag":
            changed["heldout_tracking_executed"] = False
        elif fault == "seed":
            changed["input"]["seed"] = 4002
        elif fault == "input_bool":
            changed["input"]["tracker_executed"] = 0
        elif fault == "reset":
            variant["replay"]["reset_equal"] = False
        elif fault == "bool_updates":
            variant["replay"]["updates_per_pass"] = 300.0
        elif fault == "config":
            variant["config"]["use_mahalanobis_gating"] = 0
            variant["config_sha256"] = _sha(variant["config"])
        elif fault == "endpoints":
            variant["scoring"]["endpoints"]["tracking.id_switches"] = 1
            sealed(variant["scoring"], "scoring_sha256")
        elif fault == "diagnostics":
            variant["scoring"]["diagnostics"]["overall"]["missed_object_frames"] = 0
            sealed(variant["scoring"], "scoring_sha256")
        elif fault == "receipt":
            variant["replay"]["detection_receipts"][0]["class_id"] = 1
        elif fault == "delta":
            changed["candidate_minus_baseline"]["tracking.id_switches"] = 1
        elif fault == "source":
            changed["source"]["actual_revision"] = "0" * 40
        else:
            variant["scoring"]["scoring_sha256"] = "0" * 64
        sealed(changed, "record_sha256")
        with pytest.raises(ValueError):
            original(changed, scene, freeze["source"], freeze["baseline_source"],
                     freeze["environment"], execution._score_heldout)


def test_exclusive_creation_loses_race_without_replay_or_overwriting_claim(prepared, monkeypatch):
    calls, _ = install_grid_double(monkeypatch, prepared)
    path, output, _ = prepared
    original = holdout.verify_freeze

    def concurrent_claim(freeze_path):
        freeze = original(freeze_path)
        (path.parent / "opening.json").write_bytes(b"another executor won the claim")
        return freeze

    monkeypatch.setattr(holdout, "verify_freeze", concurrent_claim)
    with pytest.raises(FileExistsError):
        execution.run_heldout(path, output)
    assert not calls and not list(output.iterdir())
    assert (path.parent / "opening.json").read_bytes() == b"another executor won the claim"


@pytest.mark.parametrize("fault", ["artifact", "extra_file", "development_audit", "plan_write"])
def test_final_integrity_or_storage_failure_retains_consumed_opening(prepared, monkeypatch, fault):
    calls, normal = install_grid_double(monkeypatch, prepared)
    path, output, _ = prepared

    def changed(scene, spec, hashes, parent, scorer, sink):
        result = normal(scene, spec, hashes, parent, scorer, sink)
        if len(calls) == 120:
            if fault == "artifact":
                (output / "plan.json").write_bytes(b"changed")
            elif fault == "extra_file":
                (output / "undeclared.json").write_bytes(b"{}")
            elif fault == "development_audit":
                monkeypatch.setattr(holdout, "_development_evidence", lambda p: {"changed": True})
        return result

    monkeypatch.setattr(execution, "_run_pair", changed)
    if fault == "plan_write":
        original = Path.open

        def refuse_plan(file, *args, **kwargs):
            if file == output / "plan.json":
                raise OSError("test storage failure")
            return original(file, *args, **kwargs)

        monkeypatch.setattr(Path, "open", refuse_plan)
        with pytest.raises(OSError, match="storage"):
            execution.run_heldout(path, output)
        assert not calls and not (output / "manifest.json").exists()
    else:
        result = execution.run_heldout(path, output)
        assert result["status"] == "failed" and len(calls) == 120
        assert result["error"] and result["complete_study_report"] is False
    assert (path.parent / "opening.json").exists()


def test_cli_requires_freeze_and_output_without_selector_or_retry_flags(monkeypatch):
    for flag in ("--scenario", "--seed", "--resume", "--retry", "--config"):
        monkeypatch.setattr("sys.argv", ["box_gate_execution", flag, "x"])
        with pytest.raises(SystemExit) as exc:
            execution.main()
        assert exc.value.code == 2
