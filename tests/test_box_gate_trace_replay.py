"""Explicit provenance/execution doubles, NEVER actual saved-study tracking."""

import copy
import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import box_gate_trace_replay as replay
from experiments.box_gate_protocol import load_registration
from experiments.traffic_protocol import load_frozen_protocol


@pytest.fixture(autouse=True)
def forbid_real_tracking(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("wrapper tests must not construct or execute a real tracker")
    monkeypatch.setattr(replay, "_construct", forbidden)
    monkeypatch.setattr(replay, "observe_sequence", forbidden)
    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)


class SceneDouble:
    def __init__(self, scenario, seed, condition):
        self.selector = dict(scenario=scenario, seed=seed, condition=condition)
        self.observed_boxes = np.tile([[[0.0, 0.0, 2.0, 4.0]]], (300, 1, 1))
        self.detection_score, self.detection_class_id = 0.9, 0

    def manifest(self):
        return dict(split="development", frame_count=300, **self.selector,
                    input_sha256=replay.sha(replay.canonical(self.selector)))


def record(scene, name, settings):
    return dict(id=name, config=settings, output=[], output_sha256=replay.sha(b"[]"),
                scoring=dict(input=scene.manifest(), crossing=dict(bottom_centre=dict(
                    predicted_events=[dict(frame_time=127.25)] if name == "baseline" else []))))


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    bundle = tmp_path / "original" / "bundle"
    bundle.mkdir(parents=True)
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    cases = []
    for s, n, c in replay.grid(spec, parent, "development"):
        scene = SceneDouble(s, n, c)
        variants = [record(scene, d["id"], {**parent["tracker_config"], **d["config_patch"]})
                    for d in spec["variants"]]
        cases.append(dict(selector=scene.selector, scene=scene, variants=variants,
                          frames=replay.selected_frames([127.25])))
    environment = dict(fixture="runtime double")
    state = dict(source=dict(actual_revision="a" * 40, worktree_dirty=False,
                            experiment_sha256={"experiments/fixture.py": "b" * 64}),
                 environment=environment)
    baseline = dict(revision=spec["baseline_revision"], files={"src/fixture.py": "c" * 64})
    audit = dict(fixture="reviewed arithmetic double")
    index = dict(protocol_hashes=hashes, source_revision="d" * 40, environment=environment,
                 audit=dict(script="experiments/helper.py", script_sha256=replay.sha(b"fixture"),
                            output_sha256=replay.sha(replay.canonical(audit))))
    manifest = dict(manifest_sha256="e" * 64)
    plan = dict(inputs=[c["scene"].manifest() for c in cases], baseline_source=baseline)

    class EvidenceDouble:
        def __init__(self):
            self.final_checks = 0

        def index(self, selected_root, split):
            assert selected_root == root and split == "development"
            return index

        def bundle(self, path, supplied_index, supplied_spec, supplied_parent, split):
            assert path == bundle and supplied_index == index and split == "development"
            assert supplied_spec == spec and supplied_parent == parent
            return manifest, plan

        def bytes(self, path):
            return replay.canonical(audit) if path.name == "audit.json" else b"fixture"

        def load(self, path):
            if path.name == "audit.json":
                return audit
            s, n, c, name = path.parts[-4:]
            selected = next(x for x in cases if x["selector"] ==
                            dict(scenario=s, seed=int(n), condition=c))
            return next(v for v in selected["variants"] if v["id"] == name[:-5])

        def unchanged(self):
            self.final_checks += 1

    evidence = EvidenceDouble()
    monkeypatch.setattr(replay, "ROOT", root)
    monkeypatch.setattr(replay, "load_registration", lambda *a: (spec, hashes))
    monkeypatch.setattr(replay, "load_frozen_protocol", lambda *a: (parent, {}))
    monkeypatch.setattr(replay, "_state", lambda: copy.deepcopy(state))
    monkeypatch.setattr(replay, "Evidence", lambda: evidence)
    monkeypatch.setattr(replay, "_verify_tree", lambda *a: copy.deepcopy(baseline))
    monkeypatch.setattr(replay, "development_audit", lambda *a: copy.deepcopy(audit))

    def generate(*, split, scenario, seed, condition):
        assert split == "development"
        return SceneDouble(scenario, seed, condition)

    monkeypatch.setattr(replay, "generate_inputs", generate)
    return SimpleNamespace(root=root, bundle=bundle, spec=spec, parent=parent, cases=cases,
                           state=state, evidence=evidence, plan=plan, index=index)


def test_full_preparation_only_regenerates_dev_inputs(prepared):
    p = prepared
    context = replay._prepare(p.bundle, p.root)
    assert len(context["cases"]) == 120
    assert p.evidence.final_checks == 1
    assert all(126 in c["frames"] and 129 in c["frames"] for c in context["cases"])
    assert list(p.bundle.iterdir()) == []


@pytest.mark.parametrize("change", ["runtime", "baseline", "input", "config", "output", "audit"])
def test_preparation_refuses_forgery_before_execution(prepared, monkeypatch, change):
    p = prepared
    if change == "runtime":
        p.index["environment"] = dict(other="runtime")
    elif change == "baseline":
        p.plan["baseline_source"] = dict(other="baseline")
    elif change == "input":
        p.plan["inputs"][0]["split"] = "heldout"
    elif change == "config":
        p.cases[0]["variants"][0]["config"]["w_unc"] = 1.0
    elif change == "output":
        p.cases[0]["variants"][0]["output_sha256"] = "f" * 64
    else:
        monkeypatch.setattr(replay, "development_audit", lambda *a: dict(changed=True))
    with pytest.raises(ValueError):
        replay._prepare(p.bundle, p.root)


def test_dirty_source_refused_before_import_checks(monkeypatch):
    monkeypatch.setattr(replay, "_snapshot", lambda: dict(worktree_dirty=True))
    monkeypatch.setattr(replay, "_check_import_origins", lambda: pytest.fail("too late"))
    with pytest.raises(ValueError, match="commit all"):
        replay._state()


def test_guard_detects_source_change(prepared, monkeypatch):
    context = replay._prepare(prepared.bundle, prepared.root)
    monkeypatch.setattr(replay, "_state", lambda: dict(changed=True))
    with pytest.raises(ValueError, match="source or runtime"):
        replay._guard(context)


@pytest.fixture
def tracing(prepared, monkeypatch):
    p = prepared
    context = replay._prepare(p.bundle, p.root)
    calls = []
    monkeypatch.setattr(replay, "_prepare", lambda *a: context)

    def traced(case, record):
        calls.append((case["selector"], record["id"]))
        return dict(interpretation_allowed=False, fixture="NOT a real trace")

    monkeypatch.setattr(replay, "_trace_variant", traced)
    p.context, p.calls = context, calls
    return p


def test_complete_export_all_240_variants_and_hashes(tracing):
    p, output = tracing, tracing.root.parent / "new-traces"
    manifest = replay.run_development_trace(p.bundle, output, root=p.root)
    assert manifest["status"] == "complete"
    assert manifest["attempted_variants"] == manifest["completed_variants"] == 240
    assert manifest["exploratory_interpretation_allowed"] is True
    assert manifest["validation_evidence"] is False
    assert manifest["heldout_files_read"] is False
    assert len(p.calls) == 240
    assert [name for _, name in p.calls] == list(replay.VARIANTS) * 120
    assert len(manifest["files_sha256"]) == 481
    for name, digest in manifest["files_sha256"].items():
        assert replay.sha((output / name).read_bytes()) == digest
    saved = json.loads((output / "manifest.json").read_bytes())
    assert saved == manifest
    digest = saved.pop("manifest_sha256")
    assert replay.sha(replay.canonical(saved)) == digest


@pytest.mark.parametrize("kind", ["ordinary", "parity", "guard"])
def test_first_error_retains_partial_and_stops(tracing, monkeypatch, kind):
    p, output = tracing, tracing.root.parent / "failed-traces"
    original = replay._trace_variant

    def trace(case, record):
        if len(p.calls) == 1 and kind != "guard":
            if kind == "parity":
                raise replay.ParityMismatch(dict(interpretation_allowed=False, fixture="failed"))
            raise ValueError("injected failure")
        return original(case, record)

    monkeypatch.setattr(replay, "_trace_variant", trace)
    if kind == "guard":
        def guard(*args, **kwargs):
            if len(p.calls) == 2:
                raise ValueError("source changed after second trace")
        monkeypatch.setattr(replay, "_guard", guard)
    manifest = replay.run_development_trace(p.bundle, output, root=p.root)
    assert manifest["status"] == "failed"
    assert manifest["completed_variants"] == 1
    assert manifest["attempted_variants"] == 2
    assert manifest["exploratory_interpretation_allowed"] is False
    assert (output / "traces/001.json").exists()
    assert (output / "traces/002.json").exists() is (kind == "guard")
    assert (output / "failed_trace.json").exists() is (kind == "parity")
    with pytest.raises(ValueError, match="new output"):
        replay.run_development_trace(p.bundle, output, root=p.root)


def test_interruption_receipt_and_no_resume(tracing, monkeypatch):
    output = tracing.root.parent / "interrupted-traces"

    def interrupt(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(replay, "_trace_variant", interrupt)
    with pytest.raises(KeyboardInterrupt):
        replay.run_development_trace(tracing.bundle, output, root=tracing.root)
    assert json.loads((output / "interrupted.json").read_bytes())["interpretation_allowed"] is False
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("where", ["repo", "original", "existing", "symlink", "ancestor"])
def test_output_path_protection_before_preparation(prepared, monkeypatch, where):
    p = prepared
    output = {"repo": p.root / "new", "original": p.bundle.parent / "new",
              "existing": p.bundle, "symlink": p.root.parent / "link",
              "ancestor": p.root.parent}[where]
    if where == "symlink":
        output.symlink_to(p.root.parent / "not-yet-created")
    monkeypatch.setattr(replay, "_prepare", lambda *a: pytest.fail("preflight must not run"))
    with pytest.raises(ValueError):
        replay.run_development_trace(p.bundle, output, root=p.root)


def test_preflight_failure_does_not_create_output(prepared, monkeypatch):
    output = prepared.root.parent / "new"

    def refuse(*args):
        raise ValueError("preflight failure")

    monkeypatch.setattr(replay, "_prepare", refuse)
    with pytest.raises(ValueError):
        replay.run_development_trace(prepared.bundle, output, root=prepared.root)
    assert not output.exists()


@pytest.fixture
def observed(prepared, monkeypatch):
    case = prepared.cases[0]
    record = case["variants"][0]
    _, payload = replay._payload(case["scene"])
    result = dict(format="visiontrack.box-gate-internal-trace/v1", frame_count=300,
                  settings=record["config"], selected_frames=case["frames"], public_output=[],
                  expected_output_sha256=record["output_sha256"],
                  actual_output_sha256=record["output_sha256"],
                  detection_payload_sha256=payload, exact_public_output_parity=True,
                  provenance_verified=False, interpretation_allowed=False,
                  validation_evidence=False)
    monkeypatch.setattr(replay, "_construct", lambda *a: "explicit tracker double")

    def observer(tracker, detections, **kwargs):
        assert tracker == "explicit tracker double"
        assert len(detections) == 300
        assert kwargs == dict(frames=case["frames"], expected_output=record["output"])
        assert all(d.feature is None and d.class_id == 0 and d.score == 0.9
                   for batch in detections for d in batch)
        return copy.deepcopy(result)

    monkeypatch.setattr(replay, "observe_sequence", observer)
    return case, record, result


def test_variant_payload_and_complete_output_gate(observed):
    case, record, _ = observed
    result = replay._trace_variant(case, record)
    assert result["interpretation_allowed"] is False
    assert result["saved_input_sha256"] == case["scene"].manifest()["input_sha256"]


@pytest.mark.parametrize("key,value", [
    ("detection_payload_sha256", "f" * 64), ("frame_count", 299),
    ("exact_public_output_parity", False), ("interpretation_allowed", True),
    ("provenance_verified", True), ("validation_evidence", True),
    ("expected_output_sha256", "f" * 64), ("actual_output_sha256", "f" * 64),
    ("selected_frames", [0]), ("settings", {}), ("public_output", [{}]),
])
def test_variant_forgery_refused(observed, key, value):
    case, record, result = observed
    result[key] = value
    with pytest.raises(ValueError):
        replay._trace_variant(case, record)


@pytest.mark.parametrize("option", ["--heldout", "--seed", "--resume", "--variant", "--retry"])
def test_cli_has_no_heldout_or_selective_entry(option):
    completed = subprocess.run([sys.executable, "-m", "experiments.box_gate_trace_replay",
                                "--development", "/unused", "--output", "/unused-new",
                                option, "x"], capture_output=True, timeout=15)
    assert completed.returncode == 2
    assert b"unrecognized arguments" in completed.stderr


def test_cli_failure_status_is_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["trace", "--development", "/unused",
                                      "--output", "/unused-new"])
    monkeypatch.setattr(replay, "run_development_trace", lambda *a: dict(
        status="failed", manifest_sha256="a" * 64))
    assert replay.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


@pytest.mark.parametrize("change", ["bytes", "extra", "symlink", "oversize"])
def test_output_integrity_refuses_tamper(tracing, monkeypatch, change):
    output = tracing.root.parent / "tampered-traces"
    verify = replay._verify_written

    def tamper_then_verify(path, files):
        if change == "bytes":
            (path / "traces/001.json").write_bytes(b"changed")
        elif change == "extra":
            (path / "unexpected.json").write_bytes(b"extra")
        elif change == "symlink":
            (path / "unexpected").symlink_to(path / "plan.json")
        else:
            monkeypatch.setattr(replay, "MAX_TRACE_BYTES", 1)
        verify(path, files)

    monkeypatch.setattr(replay, "_verify_written", tamper_then_verify)
    # Restore the writer's size limit after the intentional verification failure
    # so it can retain the FAILED manifest rather than simulate disk failure.
    if change == "oversize":
        def tamper_then_verify(path, files):
            try:
                monkeypatch.setattr(replay, "MAX_TRACE_BYTES", 1)
                verify(path, files)
            finally:
                monkeypatch.setattr(replay, "MAX_TRACE_BYTES", 64 * 1024 * 1024)
        monkeypatch.setattr(replay, "_verify_written", tamper_then_verify)
    manifest = replay.run_development_trace(tracing.bundle, output, root=tracing.root)
    assert manifest["status"] == "failed"
    assert manifest["exploratory_interpretation_allowed"] is False


def test_new_output_writes_are_exclusive(tracing, monkeypatch):
    output = tracing.root.parent / "racing-traces"
    original = replay._trace_variant

    def existing(case, record):
        result = original(case, record)
        if len(tracing.calls) == 1:
            (output / "traces").mkdir()
            (output / "traces/001.json").write_bytes(b"preserve existing bytes")
        return result

    monkeypatch.setattr(replay, "_trace_variant", existing)
    manifest = replay.run_development_trace(tracing.bundle, output, root=tracing.root)
    assert manifest["status"] == "failed"
    assert (output / "traces/001.json").read_bytes() == b"preserve existing bytes"
