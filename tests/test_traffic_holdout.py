"""Freeze/gate fixtures only: no actual held-out tracker is run by these tests."""

import copy
import hashlib
import json
import subprocess

import pytest

from experiments import traffic_holdout as holdout
from experiments import traffic_report as report
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from experiments.traffic_runner import _json_bytes
from experiments.traffic_scene import generate_scene

SOURCE = {"actual_revision": "a" * 40, "experiment_sha256": {"fixture.py": "b" * 64}}
ENVIRONMENT = {"fixture": "not measured tracker outcomes"}
BASELINE = {
    "revision": load_frozen_protocol()[0]["baseline_revision"],
    "files": {},
    "sha256": "c" * 64,
}


def _evidence():
    index = holdout._load(ROOT / holdout.INDEX)
    return {
        "index_sha256": hashlib.sha256(holdout._read(ROOT / holdout.INDEX)).hexdigest(),
        "harness_revision": index["harness_revision"],
        "manifest_content_sha256": index["bundle"]["manifest_content_sha256"],
        "verified_non_manifest_files": 124,
        "successful_runs": 120,
        "file_sha256": index["bundle"]["file_sha256"],
    }


def _mock_state(monkeypatch):
    monkeypatch.setattr(holdout, "_snapshot", lambda: copy.deepcopy(SOURCE))
    monkeypatch.setattr(report, "_snapshot", lambda: copy.deepcopy(SOURCE))
    monkeypatch.setattr(holdout, "_harness", lambda: {"fixture.py": "d" * 64})
    monkeypatch.setattr(holdout, "_verify_tree", lambda *args: copy.deepcopy(BASELINE))
    monkeypatch.setattr(holdout, "_environment", lambda: copy.deepcopy(ENVIRONMENT))
    monkeypatch.setattr(holdout, "_development_evidence", lambda path: _evidence())
    monkeypatch.setattr(holdout, "_git", lambda *args: b"")


def _prepare(tmp_path, monkeypatch):
    _mock_state(monkeypatch)
    path = tmp_path / "freeze" / "freeze.json"
    freeze = holdout.prepare_freeze(path.parent, development_bundle=tmp_path / "fixture-dev")
    return path, freeze


def _fake_record(*, split, scenario, seed, condition):
    """Deliberately fake zero outcomes exercise plumbing, never tracker performance."""
    assert split == "heldout"
    spec, hashes = load_frozen_protocol()
    inputs = generate_scene(
        split=split, scenario=scenario, seed=seed, condition=condition
    ).manifest()
    contacts = {a: {"sample_count": 0, "mean_distance_world": None} for a in spec["anchors"]}
    record = {
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "input": inputs,
        "config": spec["tracker_config"],
        "config_sha256": report._sha(spec["tracker_config"]),
        "source": {**SOURCE, "tracked_worktree_dirty": False, "baseline": BASELINE},
        "environment": copy.deepcopy(ENVIRONMENT),
        "replay": {"passes": 3, "reset_equal": True, "fresh_equal": True, "updates_per_pass": 300},
        "output": [],
        "output_sha256": report._sha([]),
        "crossing": {
            a: {"summary": dict.fromkeys(report.CROSSING_METRICS, 0)} for a in spec["anchors"]
        },
        "diagnostics": {
            "input_sha256": inputs["input_sha256"],
            "overall": {
                **dict.fromkeys(report.TRACKING_METRICS, 0),
                "observation_contact_error": contacts,
                "matched_track_contact_error": contacts,
            },
        },
        "heldout_tracking_executed": True,
    }
    record["record_sha256"] = report._sha(record)
    return record


def test_prepare_and_verify_all_120_geometry_inputs_without_tracker(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("held-out tracker must not run during preparation or verification")

    monkeypatch.setattr(holdout, "_run_case", forbidden)
    path, freeze = _prepare(tmp_path, monkeypatch)
    assert holdout.verify_freeze(path) == freeze
    assert freeze["heldout_tracking_executed"] is False
    assert freeze["complete_study_report"] is False
    assert len(freeze["inputs"]) == freeze["planned_runs"] == 120
    assert {p["scenario"] for p in freeze["inputs"]} == {"offcentre", "close_opposing", "slanted"}
    assert {p["seed"] for p in freeze["inputs"]} == set(range(1001, 1011))
    assert all(p["split"] == "heldout" and not p["tracker_executed"] for p in freeze["inputs"])
    assert not (path.parent / "opening.json").exists()
    content = dict(freeze)
    assert content.pop("freeze_sha256") == report._sha(content)
    with pytest.raises(FileExistsError):
        holdout.prepare_freeze(path.parent, development_bundle=tmp_path / "unused")


@pytest.mark.parametrize("drift", ["source", "harness", "baseline", "environment", "inputs"])
def test_freeze_refuses_drift_before_opening(tmp_path, monkeypatch, drift):
    path, _ = _prepare(tmp_path, monkeypatch)
    target = {
        "source": "_snapshot",
        "harness": "_harness",
        "baseline": "_verify_tree",
        "environment": "_environment",
        "inputs": "_inputs",
    }[drift]
    value = {**SOURCE, "experiment_sha256": {}} if drift == "source" else {}
    monkeypatch.setattr(holdout, target, lambda *args: value)
    with pytest.raises(ValueError, match="changed"):
        holdout.verify_freeze(path)
    assert not (path.parent / "opening.json").exists()


@pytest.mark.parametrize("defect", ["hash", "protocol", "count", "opened", "evidence"])
def test_corrupted_or_wrong_scope_freeze_rejected(tmp_path, monkeypatch, defect):
    path, freeze = _prepare(tmp_path, monkeypatch)
    if defect == "hash":
        freeze["freeze_sha256"] = "0" * 64
    else:
        if defect == "protocol":
            freeze["recipe"] = {}
        elif defect == "count":
            freeze["planned_runs"] = 119
        elif defect == "opened":
            freeze["heldout_tracking_executed"] = True
        else:
            freeze["development_evidence"]["successful_runs"] = 119
        freeze.pop("freeze_sha256")
        freeze["freeze_sha256"] = report._sha(freeze)
    path.write_bytes(_json_bytes(freeze))
    with pytest.raises(ValueError):
        holdout.verify_freeze(path)


def test_source_must_be_committed_and_descend_from_freeze(tmp_path, monkeypatch):
    path, _ = _prepare(tmp_path, monkeypatch)

    def fail(*args):
        raise subprocess.CalledProcessError(1, "fixture ancestry")

    monkeypatch.setattr(holdout, "_git", fail)
    with pytest.raises(subprocess.CalledProcessError):
        holdout.verify_freeze(path)


def test_full_fake_grid_is_bound_to_freeze_and_single_opening(tmp_path, monkeypatch):
    path, freeze = _prepare(tmp_path, monkeypatch)
    calls = []

    def fake(**selector):
        assert (path.parent / "opening.json").exists()
        calls.append(selector)
        return _fake_record(**selector)

    monkeypatch.setattr(holdout, "_run_case", fake)
    output = tmp_path / "outputs"
    manifest = holdout.export_heldout(output, freeze_path=path)
    assert manifest["status"] == "complete"
    assert manifest["attempted_runs"] == manifest["successful_runs"] == len(calls) == 120
    assert manifest["unattempted_runs"] == 0
    assert manifest["heldout_tracking_executed"] is True
    assert manifest["complete_study_report"] is False
    assert manifest["freeze_sha256"] == freeze["freeze_sha256"]
    assert manifest["frozen_harness_revision"] == freeze["source"]["actual_revision"]
    first_run = json.loads((output / "runs/offcentre/1001/control.json").read_bytes())
    assert first_run["heldout_freeze"]["sha256"] == freeze["freeze_sha256"]
    summary = json.loads((output / "summary.json").read_bytes())
    assert summary["complete_heldout_grid"] is True
    assert summary["complete_development_grid"] is False
    assert "Held-out tracking is now opened" in (output / "summary.md").read_text()
    assert len(summary["scenarios"][0]["seeds"][0]["absolute"]["control"]) == 37
    assert (
        summary["scenarios"][0]["seeds"][0]["interaction"][
            "tracking.observation_contact_error.bottom_centre.mean_distance_world"
        ]
        is None
    )
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    ledger = [json.loads(line) for line in (output / "attempts.jsonl").read_bytes().splitlines()]
    assert [row["event"] for row in ledger] == ["start", "success"] * 120
    with pytest.raises(FileExistsError, match="already claimed"):
        holdout.export_heldout(tmp_path / "retry", freeze_path=path)
    assert not (tmp_path / "retry").exists()
    assert len(calls) == 120


def test_failed_opening_consumed_and_unattempted_cases_not_hidden(tmp_path, monkeypatch):
    path, _ = _prepare(tmp_path, monkeypatch)
    calls = []

    def fail(**selector):
        calls.append(selector)
        if len(calls) == 2:
            raise ValueError("fixture failure, not a real held-out outcome")
        return _fake_record(**selector)

    monkeypatch.setattr(holdout, "_run_case", fail)
    output = tmp_path / "failed"
    manifest = holdout.export_heldout(output, freeze_path=path)
    assert manifest["status"] == "failed"
    assert manifest["attempted_runs"] == 2 and manifest["successful_runs"] == 1
    assert manifest["unattempted_runs"] == 118
    assert not (output / "summary.json").exists()
    assert (path.parent / "opening.json").exists()
    with pytest.raises(FileExistsError):
        holdout.export_heldout(tmp_path / "retry", freeze_path=path)
    assert len(calls) == 2


@pytest.mark.parametrize("field", ["environment", "baseline"])
def test_first_run_must_match_frozen_runtime_and_baseline(tmp_path, monkeypatch, field):
    path, _ = _prepare(tmp_path, monkeypatch)

    def changed(**selector):
        record = _fake_record(**selector)
        if field == "environment":
            record[field] = {}
        else:
            record["source"]["baseline"] = {}
        return record

    monkeypatch.setattr(holdout, "_run_case", changed)
    manifest = holdout.export_heldout(tmp_path / "failed", freeze_path=path)
    assert manifest["status"] == "failed" and manifest["successful_runs"] == 0
    assert manifest["attempted_runs"] == 1 and manifest["unattempted_runs"] == 119


def test_invalid_freeze_and_existing_output_do_not_execute_or_consume(tmp_path, monkeypatch):
    path, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(holdout, "_run_case", lambda **kw: pytest.fail("no tracker"))
    with pytest.raises(FileNotFoundError):
        holdout.export_heldout(tmp_path / "unused", freeze_path=tmp_path / "missing.json")
    with pytest.raises(FileExistsError):
        holdout.export_heldout(path.parent, freeze_path=path)
    assert not (path.parent / "opening.json").exists()
    with pytest.raises(TypeError):
        holdout.export_heldout(tmp_path / "unused", freeze_path=path, seed=1001)


def test_freeze_never_created_inside_repo(tmp_path, monkeypatch):
    _mock_state(monkeypatch)
    with pytest.raises(ValueError, match="outside"):
        holdout.prepare_freeze(ROOT / "never-created", development_bundle=tmp_path)
    assert not (ROOT / "never-created").exists()


def test_low_level_export_requires_gate_and_complete_summary_requires_all_cases(tmp_path):
    with pytest.raises(ValueError, match="gate"):
        report._export_grid(tmp_path, split="heldout", runner=None, summarize=None)
    record = _fake_record(split="heldout", scenario="offcentre", seed=1001, condition="control")
    with pytest.raises(ValueError, match="complete registered heldout"):
        report._summarize([record], split="heldout")
    with pytest.raises(ValueError, match="non-development"):
        report.summarize_development([record])


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b"[]"])
def test_evidence_json_rejects_duplicates_nonfinite_and_nonobject(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        holdout._load(path)


def test_bounded_files_and_symlinks(tmp_path):
    large = tmp_path / "large"
    large.write_bytes(b"x" * (holdout.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="size"):
        holdout._read(large)
    link = tmp_path / "link"
    link.symlink_to(large)
    with pytest.raises(ValueError, match="symlink"):
        holdout._read(link)


def test_uncommitted_harness_not_accepted(monkeypatch):
    monkeypatch.setattr(holdout, "_git", lambda *args: b"not committed bytes")
    with pytest.raises(ValueError, match="commit"):
        holdout._harness()


def _fixture_development_bundle(tmp_path, monkeypatch):
    """Small fake evidence files, not a measured development experiment."""
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    bundle = tmp_path / "fixture-development"
    bundle.mkdir()
    spec, hashes = load_frozen_protocol()
    names = ["plan.json", "attempts.jsonl", "summary.json", "summary.md"] + [
        f"runs/{s}/{n}/{c}.json" for s, n, c in report._cases(spec)
    ]
    digests = {}
    for name in names:
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = b"fixture evidence only\n"
        path.write_bytes(data)
        digests[name] = hashlib.sha256(data).hexdigest()
    manifest = {
        "format": "visiontrack.traffic-development-bundle/v1",
        "status": "complete",
        "planned_runs": 120,
        "attempted_runs": 120,
        "successful_runs": 120,
        "unattempted_runs": 0,
        "error": None,
        "heldout_tracking_executed": False,
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "source": SOURCE,
        "files_sha256": digests,
    }
    manifest["manifest_sha256"] = report._sha(manifest)
    (bundle / "manifest.json").write_bytes(_json_bytes(manifest))
    index = {
        "harness_revision": SOURCE["actual_revision"],
        "bundle": {
            "manifest_content_sha256": manifest["manifest_sha256"],
            "file_sha256": {
                "manifest.json": hashlib.sha256(
                    (bundle / "manifest.json").read_bytes()
                ).hexdigest(),
                "plan.json": digests["plan.json"],
                "summary.json": digests["summary.json"],
            },
        },
    }
    (root / holdout.INDEX).write_bytes(_json_bytes(index))
    monkeypatch.setattr(holdout, "ROOT", root)
    return bundle


def test_all_development_evidence_files_checked_not_just_summary(tmp_path, monkeypatch):
    bundle = _fixture_development_bundle(tmp_path, monkeypatch)
    result = holdout._development_evidence(bundle)
    assert result["verified_non_manifest_files"] == 124
    path = bundle / "runs/converging/110/combined.json"
    path.write_bytes(b"changed raw record, not just summary")
    with pytest.raises(ValueError, match="file digest"):
        holdout._development_evidence(bundle)


@pytest.mark.parametrize("defect", ["missing", "heldout", "outside-path", "manifest", "symlink"])
def test_invalid_development_evidence_stops_freeze(tmp_path, monkeypatch, defect):
    bundle = _fixture_development_bundle(tmp_path, monkeypatch)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if defect == "missing":
        (bundle / "summary.md").unlink()
    elif defect == "symlink":
        (bundle / "summary.md").unlink()
        (bundle / "summary.md").symlink_to(bundle / "summary.json")
    else:
        if defect == "heldout":
            manifest["heldout_tracking_executed"] = True
        elif defect == "outside-path":
            manifest["files_sha256"]["../outside"] = "0" * 64
        else:
            manifest["manifest_sha256"] = "0" * 64
        manifest_path.write_bytes(_json_bytes(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        holdout._development_evidence(bundle)


def test_preparation_drift_keeps_heldout_closed_and_writes_no_freeze(tmp_path, monkeypatch):
    _mock_state(monkeypatch)
    sources = iter([SOURCE, {**SOURCE, "actual_revision": "f" * 40}])
    monkeypatch.setattr(holdout, "_snapshot", lambda: next(sources))
    with pytest.raises(ValueError, match="changed while preparing"):
        holdout.prepare_freeze(tmp_path / "not-created", development_bundle=tmp_path)
    assert not (tmp_path / "not-created").exists()
