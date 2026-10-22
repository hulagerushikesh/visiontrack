"""Summary/export oracles; fake outcomes are not measured tracker results."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments import traffic_report as report
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_scene import generate_scene

SOURCE = {"actual_revision": "a" * 40, "experiment_sha256": {"fixture.py": "b" * 64}}


def _record(scenario="solo", seed=101, condition="control"):
    spec, hashes = load_frozen_protocol()
    inputs = generate_scene(
        split="development", scenario=scenario, seed=seed, condition=condition
    ).manifest()
    modifier = {"control": 0, "perspective_only": 3, "box_error_only": 5, "combined": 11}[condition]
    value = seed - 100 + modifier
    contact = {
        anchor: {"sample_count": 300, "mean_distance_world": float(value)}
        for anchor in ("bottom_centre", "box_centre")
    }
    timing = None if condition == "combined" and seed == 101 else float(seed)
    result = {
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "input": inputs,
        "config": spec["tracker_config"],
        "config_sha256": report._sha(spec["tracker_config"]),
        "source": {
            **SOURCE,
            "tracked_worktree_dirty": False,
            "baseline": {"revision": spec["baseline_revision"], "files": {}, "sha256": "c" * 64},
        },
        "environment": {"fixture": "not actual runtime results"},
        "replay": {"passes": 3, "reset_equal": True, "fresh_equal": True, "updates_per_pass": 300},
        "output": [],
        "output_sha256": report._sha([]),
        "crossing": {
            anchor: {
                "summary": {
                    "truth_count": 2,
                    "predicted_count": 2,
                    "matched_count": 1,
                    "missed_events": 1,
                    "extra_events": 1,
                    "recall": 0.5,
                    "matched_x_abs_mean_world": 0.25,
                    "matched_wrong_window_events": 0,
                    "event_error": value,
                    "window_count_abs_error": value,
                    "matched_time_abs_mean_frames": timing,
                }
            }
            for anchor in ("bottom_centre", "box_centre")
        },
        "diagnostics": {
            "input_sha256": inputs["input_sha256"],
            "overall": {
                "true_object_frames": 300,
                "matched_object_frames": 150,
                "fragmentations": 0,
                "id_switches": value,
                "missed_object_frames": value,
                "false_positive_rows": value,
                "matched_object_frame_fraction": 0.5,
                "observation_contact_error": contact,
                "matched_track_contact_error": contact,
            },
        },
        "heldout_tracking_executed": False,
    }
    result["record_sha256"] = report._sha(result)
    return result


@pytest.fixture(scope="module")
def records():
    spec, _ = load_frozen_protocol()
    return [_record(s, n, c) for s, n, c in report._cases(spec)]


def test_all_120_cases_are_development_only():
    spec, _ = load_frozen_protocol()
    cases = report._cases(spec)
    assert len(cases) == len(set(cases)) == 120
    assert {s for s, _, _ in cases} == {"solo", "opposing", "converging"}
    assert {n for _, n, _ in cases} == set(range(101, 111))


def test_hand_calculated_absolutes_differences_interaction_and_ranges(records):
    result = report.summarize_development(records)
    metric = "crossing.bottom_centre.event_error"
    assert result["run_count"] == 120 and result["scenario_count"] == 3
    assert result["complete_development_grid"] is True
    assert result["heldout_tracking_executed"] is False
    for scene in result["scenarios"]:
        first = scene["seeds"][0]
        assert first["absolute"]["control"][metric] == 1
        assert first["absolute"]["combined"][metric] == 12
        for condition, value in (("perspective_only", 3), ("box_error_only", 5), ("combined", 11)):
            assert first["difference_from_control"][condition][metric] == value
        assert first["interaction"][metric] == 3
        assert scene["absolute"]["control"][metric] == {
            "defined_seeds": 10,
            "undefined_seeds": 0,
            "mean": 5.5,
            "min": 1,
            "max": 10,
        }
        assert scene["interaction"][metric]["mean"] == 3
    assert "No winner is selected" in report._markdown(result)
    json.dumps(result, allow_nan=False)


def test_null_contrasts_not_imputed(records):
    result = report.summarize_development(records)
    metric = "crossing.bottom_centre.matched_time_abs_mean_frames"
    for scene in result["scenarios"]:
        first = scene["seeds"][0]
        assert first["absolute"]["combined"][metric] is None
        assert first["difference_from_control"]["combined"][metric] is None
        assert first["interaction"][metric] is None
        assert scene["interaction"][metric] == {
            "defined_seeds": 9,
            "undefined_seeds": 1,
            "mean": 0,
            "min": 0,
            "max": 0,
        }
    assert report._descriptive([{"x": None}, {"x": None}])["x"] == {
        "defined_seeds": 0,
        "undefined_seeds": 2,
        "mean": None,
        "min": None,
        "max": None,
    }


def test_negative_and_zero_differences_preserved():
    assert report._contrast([(1, {"x": 1}), (-1, {"x": 5})]) == {"x": -4}
    assert report._contrast([(1, {"x": 5}), (-1, {"x": 5})]) == {"x": 0}


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "duplicate",
        "heldout",
        "protocol",
        "truth",
        "draws",
        "ideal",
        "nonfinite",
        "boolean",
    ],
)
def test_bad_grids_fail_closed(records, defect):
    bad = copy.deepcopy(records)
    if defect == "missing":
        bad.pop()
    elif defect == "duplicate":
        bad.append(bad[0])
    elif defect == "heldout":
        bad[0]["input"]["split"] = "heldout"
    elif defect == "protocol":
        bad[0]["protocol_hashes"] = {}
    elif defect in {"truth", "draws", "ideal"}:
        name = {"truth": "world_truth", "draws": "random_draws", "ideal": "ideal_truth"}[defect]
        bad[2]["input"]["sha256"][name] = "0" * 64
    else:
        bad[0]["crossing"]["bottom_centre"]["summary"]["event_error"] = (
            True if defect == "boolean" else float("inf")
        )
    with pytest.raises(ValueError):
        report.summarize_development(bad)


@pytest.mark.parametrize(
    "defect",
    ["record", "config", "output", "revision", "dirty", "source", "environment_source", "baseline"],
)
def test_run_validation_checks_provenance_and_digests(defect):
    record = _record()
    planned = copy.deepcopy(record["input"])
    spec, hashes = load_frozen_protocol()
    if defect == "record":
        record["record_sha256"] = "0" * 64
    elif defect == "config":
        record["config_sha256"] = "0" * 64
    elif defect == "output":
        record["output_sha256"] = "0" * 64
    elif defect == "revision":
        record["source"]["actual_revision"] = "f" * 40
    elif defect == "dirty":
        record["source"]["tracked_worktree_dirty"] = True
    elif defect == "source":
        record["source"]["experiment_sha256"] = {}
    elif defect == "environment_source":
        record["diagnostics"]["input_sha256"] = "0" * 64
    else:
        record["source"]["baseline"]["revision"] = "0" * 40
    if defect != "record":
        record.pop("record_sha256")
        record["record_sha256"] = report._sha(record)
    with pytest.raises(ValueError):
        report._validate_record(record, planned, SOURCE, spec, hashes)


def _mock_grid(monkeypatch):
    spec, _ = load_frozen_protocol()
    monkeypatch.setattr(report, "_snapshot", lambda: copy.deepcopy(SOURCE))
    monkeypatch.setattr(
        report, "_cases", lambda spec: [("solo", 101, c["id"]) for c in spec["conditions"]]
    )
    monkeypatch.setattr(report, "run_development", _record)
    monkeypatch.setattr(report, "summarize_development", lambda records: {"records": len(records)})
    monkeypatch.setattr(report, "_markdown", lambda summary: "# Fixture summary\n")
    return spec


def _check_files(output, manifest):
    persisted = json.loads((output / "manifest.json").read_bytes())
    assert persisted == manifest
    digest = persisted.pop("manifest_sha256")
    assert report._sha(persisted) == digest
    assert "manifest.json" not in manifest["files_sha256"]
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


def test_export_new_bundle_digests_and_repeat_bytes(tmp_path, monkeypatch):
    _mock_grid(monkeypatch)
    first, second = tmp_path / "first", tmp_path / "second"
    a = report.export_development(first)
    b = report.export_development(second)
    assert a == b
    assert a["status"] == "complete" and a["successful_runs"] == a["planned_runs"] == 4
    assert a["unattempted_runs"] == 0
    assert json.loads((first / "plan.json").read_bytes())["heldout_tracking_authorized"] is False
    _check_files(first, a)
    _check_files(second, b)
    ledger = [json.loads(line) for line in (first / "attempts.jsonl").read_bytes().splitlines()]
    assert [row["event"] for row in ledger] == ["start", "success"] * 4
    before = (first / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        report.export_development(first)
    assert (first / "manifest.json").read_bytes() == before


def test_failure_is_retained_and_stops_without_favorable_rerun(tmp_path, monkeypatch):
    _mock_grid(monkeypatch)
    calls = []

    def fail(scenario, seed, condition):
        calls.append(condition)
        if condition == "perspective_only":
            raise ValueError("fixture failure")
        return _record(scenario, seed, condition)

    monkeypatch.setattr(report, "run_development", fail)
    output = tmp_path / "attempt"
    manifest = report.export_development(output)
    assert manifest["status"] == "failed"
    assert manifest["successful_runs"] == 1 and manifest["unattempted_runs"] == 2
    assert calls == ["control", "perspective_only"]
    assert not (output / "summary.json").exists()
    assert manifest["error"]["condition"] == "perspective_only"
    _check_files(output, manifest)


def test_environment_drift_fails_grid(tmp_path, monkeypatch):
    _mock_grid(monkeypatch)

    def changed(scenario, seed, condition):
        record = _record(scenario, seed, condition)
        if condition == "perspective_only":
            record["environment"] = {"changed": True}
            record.pop("record_sha256")
            record["record_sha256"] = report._sha(record)
        return record

    monkeypatch.setattr(report, "run_development", changed)
    result = report.export_development(tmp_path / "attempt")
    assert result["status"] == "failed"
    assert "environment" in result["error"]["message"]


def test_export_inside_repo_rejected(monkeypatch):
    _mock_grid(monkeypatch)
    with pytest.raises(ValueError, match="outside"):
        report.export_development(ROOT / "not-created-traffic-results")
    assert not (ROOT / "not-created-traffic-results").exists()


def test_clean_committed_snapshot_required(monkeypatch):
    monkeypatch.setattr(
        report, "_git", lambda root, *args: b"abc" if args[0] == "rev-parse" else b" M tracked.py"
    )
    with pytest.raises(ValueError, match="commit tracked"):
        report._snapshot()


def test_unknown_source_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(
        report, "_git", lambda root, *args: b"" if args[0] == "status" else b"wrong source"
    )
    with pytest.raises(ValueError, match="uncommitted"):
        report._snapshot()


def test_no_heldout_or_config_override():
    with pytest.raises(TypeError):
        report.export_development(Path("unused"), split="heldout")


def test_final_source_drift_preserves_full_attempt_but_no_summary(tmp_path, monkeypatch):
    _mock_grid(monkeypatch)
    calls = []

    def snapshot():
        calls.append(None)
        return SOURCE if len(calls) == 1 else {**SOURCE, "changed": True}

    monkeypatch.setattr(report, "_snapshot", snapshot)
    output = tmp_path / "attempt"
    result = report.export_development(output)
    assert result["status"] == "failed"
    assert result["successful_runs"] == result["attempted_runs"] == 4
    assert result["unattempted_runs"] == 0
    assert not (output / "summary.json").exists()
    _check_files(output, result)


def test_progress_error_does_not_miscount_attempts(tmp_path, monkeypatch):
    _mock_grid(monkeypatch)

    def broken_progress(*args):
        raise OSError("fixture stdout failure")

    result = report.export_development(tmp_path / "attempt", progress=broken_progress)
    assert result["status"] == "failed"
    assert result["successful_runs"] == result["attempted_runs"] == 1
    assert result["unattempted_runs"] == 3


def test_all_37_fixed_endpoints_present(records):
    assert len(report._metrics(records[0])) == 37
    summary = report.summarize_development(list(reversed(records)))
    assert summary == report.summarize_development(records)
