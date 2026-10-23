"""Freeze fixtures and input geometry only; NEVER new held-out tracker outcomes."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from experiments import box_gate_holdout as holdout
from experiments.box_gate_decision import cases
from experiments.box_gate_protocol import load_registration
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import _sha
from experiments.traffic_runner import _json_bytes


@pytest.fixture(autouse=True)
def no_tracking_or_old_inputs(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("freeze tests must not execute trackers, scorers or old scenes")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.box_gate_runner._construct", forbidden)
    monkeypatch.setattr("experiments.box_gate_scoring.score_development", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)


@pytest.fixture(scope="module")
def geometry():
    # Permitted pre-opening geometry, NOT held-out performance measurements.
    return holdout._inputs()


@pytest.fixture
def state():
    return {
        "source": {
            "replay_source": {"actual_revision": "a" * 40, "worktree_dirty": False},
            "harness_sha256": {"fixture": "b" * 64},
        },
        "environment": {"fixture": "not measured outcomes"},
        "baseline_source": {"revision": "c" * 40},
        "protocol_id": "test-only",
        "protocol_hashes": {"fixture": "d" * 64},
        "registration": {"test": True},
        "configurations": [{"id": "baseline"}, {"id": "gate_off"}],
    }


@pytest.fixture
def prepared(tmp_path, monkeypatch, geometry, state):
    monkeypatch.setattr(holdout, "_state", lambda: copy.deepcopy(state))
    monkeypatch.setattr(holdout, "_inputs", lambda: copy.deepcopy(geometry))
    evidence = {
        "paired_cases": 120, "safety_endpoint_violations": 174, "candidate_accepted": False,
        "environment": copy.deepcopy(state["environment"]),
    }
    monkeypatch.setattr(holdout, "_development_evidence", lambda p: copy.deepcopy(evidence))
    directory = tmp_path / "freeze"
    freeze = holdout.prepare_freeze(directory, development_bundle=tmp_path / "dev")
    return directory / "freeze.json", freeze


def write_freeze(path, freeze):
    freeze.pop("freeze_sha256", None)
    freeze["freeze_sha256"] = _sha(freeze)
    path.write_bytes(_json_bytes(freeze) + b"\n")


def test_complete_new_geometry_and_roundtrip_without_opening(prepared, geometry):
    path, freeze = prepared
    assert holdout.verify_freeze(path) == freeze
    spec, _ = load_registration()
    parent, _ = load_frozen_protocol()
    assert [(m["scenario"], m["seed"], m["condition"]) for m in geometry] == cases(
        spec, parent, "heldout",
    )
    assert len(geometry) == freeze["planned_pairs"] == 120
    assert freeze["variant_runs"] == 240 and freeze["replay_passes"] == 720
    assert {m["seed"] for m in geometry} == set(range(4001, 4011))
    assert {m["scenario"] for m in geometry} == {
        "gate_test_solo", "gate_test_slanted", "gate_test_close",
    }
    assert all(m["split"] == "heldout" and m["tracker_executed"] is False for m in geometry)
    assert freeze["inputs_sha256"] == _sha(geometry)
    assert freeze["development_evidence"]["safety_endpoint_violations"] == 174
    assert freeze["development_evidence"]["candidate_accepted"] is False
    assert not (path.parent / "opening.json").exists()
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("field", [
    "format", "protocol_id", "protocol_hashes", "registration", "source",
    "baseline_source", "environment", "configurations", "development_evidence",
    "inputs", "inputs_sha256", "planned_pairs", "variant_runs", "replay_passes",
    "execution_policy", "heldout_tracking_executed", "complete_study_report",
    "production_change_authorized", "cpp_port_authorized",
])
def test_resealed_changed_scope_or_lineage_is_rejected(prepared, field):
    path, freeze = prepared
    freeze[field] = "forged"
    write_freeze(path, freeze)
    with pytest.raises(ValueError, match="changed|differs"):
        holdout.verify_freeze(path)
    assert not (path.parent / "opening.json").exists()


@pytest.mark.parametrize("fault", ["boolean_count", "extra_field", "bad_seal", "pretty_bytes"])
def test_strict_structure_types_and_exact_saved_bytes(prepared, fault):
    path, freeze = prepared
    if fault == "boolean_count":
        freeze["planned_pairs"] = True
        write_freeze(path, freeze)
    elif fault == "extra_field":
        freeze["unexpected"] = False
        write_freeze(path, freeze)
    elif fault == "bad_seal":
        freeze["freeze_sha256"] = "0" * 64
        path.write_bytes(_json_bytes(freeze) + b"\n")
    else:
        path.write_text(json.dumps(freeze, indent=2))
    with pytest.raises(ValueError):
        holdout.verify_freeze(path)


@pytest.mark.parametrize("field", ["source", "environment", "baseline_source", "configurations"])
def test_exact_revision_runtime_source_or_settings_drift_refused(prepared, state, field):
    path, _ = prepared
    state[field] = {"changed": True}
    with pytest.raises(ValueError, match="changed|differs"):
        holdout.verify_freeze(path)


def test_any_descendant_revision_is_refused_even_with_same_harness(prepared, state):
    path, _ = prepared
    state["source"]["replay_source"]["actual_revision"] = "e" * 40
    with pytest.raises(ValueError, match="changed"):
        holdout.verify_freeze(path)


@pytest.mark.parametrize("claim", ["regular", "dangling_symlink"])
def test_consumed_opening_refused_before_audit(prepared, monkeypatch, claim):
    path, _ = prepared
    opening = path.parent / "opening.json"
    if claim == "regular":
        opening.write_text("consumed, including incomplete executions")
    else:
        opening.symlink_to(path.parent / "missing")
    monkeypatch.setattr(
        holdout, "_state", lambda: pytest.fail("must reject consumed opening first"),
    )
    with pytest.raises(FileExistsError, match="already claimed"):
        holdout.verify_freeze(path)


def test_existing_directory_never_overwritten(prepared):
    path, _ = prepared
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        holdout.prepare_freeze(path.parent, development_bundle=path.parent / "unused")
    assert path.read_bytes() == original


def test_refuse_source_drift_during_preparation(prepared, tmp_path, monkeypatch, state):
    calls = 0

    def drifting():
        nonlocal calls
        calls += 1
        result = copy.deepcopy(state)
        result["source"]["replay_source"]["actual_revision"] = str(calls) * 40
        return result

    monkeypatch.setattr(holdout, "_state", drifting)
    output = tmp_path / "drift"
    with pytest.raises(ValueError, match="changed during preparation"):
        holdout.prepare_freeze(output, development_bundle=tmp_path / "dev")
    assert not output.exists()


def test_prepare_refuses_a_different_development_runtime(prepared, tmp_path, state):
    state["environment"] = {"new": "runtime"}
    output = tmp_path / "changed-runtime"
    with pytest.raises(ValueError, match="reviewed development environment"):
        holdout.prepare_freeze(output, development_bundle=tmp_path / "dev")
    assert not output.exists()


def test_repo_output_or_evidence_and_symlinks_refused(prepared, tmp_path):
    path, _ = prepared
    with pytest.raises(ValueError, match="outside"):
        holdout.prepare_freeze(holdout.ROOT / "not-created", development_bundle=tmp_path / "dev")
    with pytest.raises(ValueError, match="outside"):
        holdout.prepare_freeze(tmp_path / "not-created", development_bundle=holdout.ROOT)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        holdout.verify_freeze(link)


@pytest.mark.parametrize("data", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'[]'])
def test_strict_json_object_reader(tmp_path, data):
    path = tmp_path / "bad.json"
    path.write_bytes(data)
    with pytest.raises(ValueError):
        holdout._load(path)


def test_bounded_regular_file_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(holdout, "MAX_BYTES", 3)
    path = tmp_path / "large"
    path.write_bytes(b"1234")
    with pytest.raises(ValueError, match="size limit"):
        holdout._read(path)


@pytest.fixture
def bundle_fixture(tmp_path, monkeypatch):
    """365 tiny file/evidence doubles; NOT real development tracker results."""
    root, bundle = tmp_path / "repo", tmp_path / "dev"
    root.mkdir()
    bundle.mkdir()
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    files = {n: b"fixture\n" for n in ("plan.json", "attempts.jsonl", "summary.json", "summary.md")}
    for scenario, seed, condition in cases(spec, parent, "development"):
        for name in ("baseline", "gate_off", "pair"):
            files[f"pairs/{scenario}/{seed}/{condition}/{name}.json"] = b"fixture\n"
    file_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = {
        "files_sha256": file_hashes, "manifest_sha256": "fixture-self-seal",
        "source": {"replay_source": {"actual_revision": "fixture-revision"}},
        "environment": {"fixture": True},
    }
    files["manifest.json"] = _json_bytes(manifest) + b"\n"
    for name, data in files.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    audit_result = {
        "paired_cases": 120, "fixture_primary": 4,
        "safety_regressions": [{"fixture": i} for i in range(174)],
    }
    (bundle.parent / "audit.json").write_text(json.dumps(audit_result, indent=2) + "\n")
    script = root / "experiments/box_gate_audit.py"
    script.parent.mkdir()
    script.write_text("fixture-only auditor bytes")
    index = {
        "protocol_hashes": hashes, "complete_development_grid": True,
        "heldout_tracking_executed": False, "candidate_tuned": False,
        "manifest_raw_sha256": hashlib.sha256(files["manifest.json"]).hexdigest(),
        "bundle_manifest_sha256": manifest["manifest_sha256"],
        "source_revision": "fixture-revision", "environment": {"fixture": True},
        "artifact_sha256": {"plan.json": file_hashes["plan.json"]},
        "audit": {
            "script": "experiments/box_gate_audit.py",
            "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(
                (json.dumps(audit_result, indent=2, allow_nan=False) + "\n").encode(),
            ).hexdigest(),
        },
    }
    index_path = root / holdout.INDEX
    index_path.write_bytes(_json_bytes(index))
    monkeypatch.setattr(holdout, "ROOT", root)
    calls = []

    def fake_audit(*args):
        calls.append(args)
        return copy.deepcopy(audit_result)

    monkeypatch.setattr(holdout, "audit", fake_audit)
    return bundle, root, index, audit_result, calls


def test_full_evidence_binding_retains_negative_audit(bundle_fixture):
    bundle, root, _, _, calls = bundle_fixture
    evidence = holdout._development_evidence(bundle)
    assert calls == [(bundle, root)]
    assert len(evidence["files_sha256"]) == 365
    assert evidence["paired_cases"] == 120
    assert evidence["safety_endpoint_violations"] == 174
    assert evidence["candidate_accepted"] is False


def test_historic_integral_float_serialization_keeps_original_audit_bytes(bundle_fixture):
    bundle, _, _, result, _ = bundle_fixture
    original = (bundle.parent / "audit.json").read_bytes()
    result["fixture_primary"] = 4.0
    holdout._development_evidence(bundle)
    assert (bundle.parent / "audit.json").read_bytes() == original


@pytest.mark.parametrize("value", [4.0000000000001, True])
def test_no_tolerance_or_boolean_alias_for_reviewed_audit_values(bundle_fixture, value):
    bundle, _, _, result, _ = bundle_fixture
    result["fixture_primary"] = value
    with pytest.raises(ValueError):
        holdout._development_evidence(bundle)


@pytest.mark.parametrize("fault", [
    "missing", "extra", "modified", "file_symlink", "directory_symlink", "index",
    "script", "audit_changed", "audit_file_changed", "changed_during_audit",
])
def test_incomplete_forged_or_drifting_development_is_refused(bundle_fixture, monkeypatch, fault):
    bundle, root, index, audit_result, _ = bundle_fixture
    path = bundle / "summary.md"
    if fault == "missing":
        path.unlink()
    elif fault == "extra":
        (bundle / "unindexed.txt").write_text("not allowed")
    elif fault == "modified":
        path.write_text("changed")
    elif fault == "file_symlink":
        path.unlink()
        path.symlink_to(bundle / "summary.json")
    elif fault == "directory_symlink":
        (bundle / "linked").symlink_to(bundle / "pairs", target_is_directory=True)
    elif fault == "index":
        index["candidate_tuned"] = True
        (root / holdout.INDEX).write_bytes(_json_bytes(index))
    elif fault == "script":
        (root / "experiments/box_gate_audit.py").write_text("changed auditor")
    elif fault == "audit_changed":
        audit_result["safety_regressions"].pop()
    elif fault == "audit_file_changed":
        (bundle.parent / "audit.json").write_text("changed")
    else:
        def drift(*args):
            path.write_text("changed during audit")
            return copy.deepcopy(audit_result)

        monkeypatch.setattr(holdout, "audit", drift)
    with pytest.raises(ValueError):
        holdout._development_evidence(bundle)


def test_state_binds_index_and_requires_committed_bytes(tmp_path, monkeypatch, state):
    root = tmp_path / "repo"
    path = root / holdout.INDEX
    path.parent.mkdir(parents=True)
    path.write_bytes(b"reviewed index")
    monkeypatch.setattr(holdout, "ROOT", root)
    monkeypatch.setattr(holdout, "_snapshot", lambda: copy.deepcopy(state["source"]))
    monkeypatch.setattr(holdout, "_git", lambda *args: b"reviewed index")
    monkeypatch.setattr(holdout, "_verify_tree", lambda *args: {"fixture": True})
    monkeypatch.setattr(holdout, "_check_import_origins", lambda: None)
    current = holdout._state()
    assert current["source"]["harness_sha256"][holdout.INDEX] == hashlib.sha256(
        b"reviewed index",
    ).hexdigest()
    a, b = [entry["settings"] for entry in current["configurations"]]
    assert {name for name in a if _json_bytes(a[name]) != _json_bytes(b[name])} == {
        "use_mahalanobis_gating",
    }
    path.write_bytes(b"uncommitted changed index")
    with pytest.raises(ValueError, match="commit"):
        holdout._state()


def test_no_run_cli_or_public_heldout_runner(monkeypatch):
    assert not hasattr(holdout, "export_heldout")
    monkeypatch.setattr("sys.argv", ["box_gate_holdout", "run"])
    with pytest.raises(SystemExit) as exc:
        holdout.main()
    assert exc.value.code == 2
