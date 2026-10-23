"""Authored fixtures test retention/repeatability plumbing, not real performance."""
import json
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import mot17_case_baseline as baseline
from visiontrack.detection.mot_loader import FrameData
from visiontrack.eval.mot17 import evaluate_frames, run_sequence
from visiontrack.tracking.config import TrackerConfig


class Sequence:
    length = 5

    def iter_range(self, first, last):
        for frame in range(first, last + 1):
            yield FrameData(
                frame=frame, det_xyxy=np.array([[0., 0, 10, 10], [20., 0, 30, 10]]),
                det_scores=np.array([0.9, 0.9]),
                gt_xyxy=np.array([[0., 0, 10, 10], [20., 0, 30, 10]]),
                gt_ids=np.array([1, 2]), gt_classes=np.array([1, 7]),
                gt_conf=np.array([1., 1.]), gt_vis=np.array([1., 0.5]),
            )


def scripted(monkeypatch, ids):
    class Tracker:
        def __init__(self, cfg):
            assert asdict(cfg) == asdict(TrackerConfig())
            self.index = 0

        def update(self, detections):
            identity = ids[self.index]
            self.index += 1
            if identity is None:
                return []
            return [SimpleNamespace(track_id=identity, xyxy=np.array([0., 0, 10, 10])),
                    SimpleNamespace(track_id=99, xyxy=np.array([20., 0, 30, 10]))]
    monkeypatch.setattr(baseline, "ByteTracker", Tracker)


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_retains_raw_ignore_rows_and_first_canonical_switch(tmp_path, monkeypatch):
    scripted(monkeypatch, [10, 10, 11, 12, 12])
    out = tmp_path / "run"
    result = baseline.run_once(Sequence(), out)
    assert result["metrics"]["IDSW"] == 2
    assert result["metrics"]["FP"] == 0
    assert result["removed_by_ignore_preprocessing"] == 5
    assert result["raw_public_boxes"] == 10
    assert result["scored_public_boxes"] == 5
    raw, scored = read_lines(out / "raw.jsonl"), read_lines(out / "scored.jsonl")
    assert raw[2]["gt_classes"] == [1, 7]
    assert raw[2]["gt_visibility"] == [1, 0.5]
    assert raw[2]["track_ids"] == [11, 99]
    assert scored[2]["gt_ids"] == [1]
    assert scored[2]["track_ids"] == [11]
    first = result["first_chronological_switch"]
    assert (first["source_frame"], first["frame_index"]) == (3, 2)
    assert (first["gt_id"], first["previous_hyp_id"], first["hyp_id"]) == (1, 10, 11)
    context = baseline.first_switch_context(out, first, Sequence.length)
    assert context["window"] == [1, 5]
    assert len(context["frames"]) == 5
    assert context["visual_cause_established"] is False


def test_switch_after_gap_not_relabelled_no_error(tmp_path, monkeypatch):
    scripted(monkeypatch, [10, 10, None, 12, 12])
    result = baseline.run_once(Sequence(), tmp_path / "run")
    assert result["metrics"]["FN"] == 1
    assert result["metrics"]["Frag"] == 1  # current canonical interruption definition
    assert result["first_chronological_switch"]["source_frame"] == 4
    assert result["first_chronological_switch"]["previous_hyp_id"] == 10


def test_no_event_is_explicit_and_no_overwrite(tmp_path, monkeypatch):
    scripted(monkeypatch, [10] * 5)
    out = tmp_path / "run"
    result = baseline.run_once(Sequence(), out)
    assert result["first_chronological_switch"] is None
    assert baseline.first_switch_context(out, None, 5)["reason"] == "no scored identity switch"
    with pytest.raises(FileExistsError):
        baseline.run_once(Sequence(), out)


def test_real_tracker_wrapper_matches_existing_evaluation_path(tmp_path):
    out = tmp_path / "run"
    result = baseline.run_once(Sequence(), out)
    assert result["metrics"] == evaluate_frames(run_sequence(Sequence(), TrackerConfig(), 1, 5))
    assert result["raw_public_boxes"] == 6  # no public tentative output at frames 1/2
    assert result["scored_public_boxes"] == 3
    second = tmp_path / "second"
    baseline.run_once(Sequence(), second)
    for name in ("raw.jsonl", "scored.jsonl", "failures.jsonl", "summary.json"):
        assert (out / name).read_bytes() == (second / name).read_bytes()


def test_nonfinite_json_refused():
    with pytest.raises(ValueError):
        baseline.encoded({"bad": float("nan")})


def test_incomplete_context_refused(tmp_path):
    (tmp_path / "raw.jsonl").write_text(baseline.encoded(dict(source_frame=3)))
    with pytest.raises(ValueError, match="incomplete first-switch"):
        baseline.first_switch_context(tmp_path, dict(source_frame=3), 5)


@pytest.mark.parametrize("defect", ["frames", "appearance", "incomplete"])
def test_nonadmitted_stream_refused(tmp_path, defect):
    class BadSequence(Sequence):
        def iter_range(self, first, last):
            for fd in super().iter_range(first, last):
                if defect == "frames":
                    fd.frame = 2
                if defect == "appearance":
                    fd.det_features = np.zeros((2, 3))
                if defect == "incomplete" and fd.frame == 5:
                    return
                yield fd
    with pytest.raises(ValueError):
        baseline.run_once(BadSequence(), tmp_path / "run")


def test_orchestration_records_plan_before_runs_and_checks_all_bytes(tmp_path, monkeypatch):
    out = tmp_path / "case"
    monkeypatch.setattr(baseline, "audit", lambda *args: {"verified": True})
    monkeypatch.setattr(baseline, "code_identity", lambda: {"code": "fixed"})
    monkeypatch.setattr(baseline, "CachedSequence", lambda path: Sequence())
    scripted(monkeypatch, [10] * 5)
    original = baseline.run_once
    calls = []

    def checked(seq, directory):
        plan = json.loads((out / "plan.json").read_text())
        assert plan["tracker_config"] == asdict(TrackerConfig())
        assert not (out / "manifest.json").exists()
        calls.append(directory.name)
        return original(seq, directory)

    monkeypatch.setattr(baseline, "run_once", checked)
    baseline.execute("cache", "labels", out)
    assert calls == ["run-1", "run-2"]
    receipt = json.loads((out / "repeatability.json").read_text())
    assert all(receipt["exact_bytes"].values())
    assert receipt["independent_implementation"] is False
    manifest = json.loads((out / "manifest.json").read_text())
    for name, record in manifest["files"].items():
        assert record["sha256"] == baseline.sha(out / name)
    with pytest.raises(ValueError, match="new directory"):
        baseline.execute("cache", "labels", out)


def test_code_drift_prevents_tracker_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "audit", lambda *args: {})
    identities = iter([{"code": 1}, {"code": 2}])
    monkeypatch.setattr(baseline, "code_identity", lambda: next(identities))
    monkeypatch.setattr(baseline, "CachedSequence", lambda *args: pytest.fail("must not load"))
    with pytest.raises(ValueError, match="code changed before"):
        baseline.execute("cache", "labels", tmp_path / "case")


def test_mismatch_retains_runs_without_success_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "audit", lambda *args: {})
    monkeypatch.setattr(baseline, "code_identity", lambda: {})
    monkeypatch.setattr(baseline, "CachedSequence", lambda *args: Sequence())
    scripted(monkeypatch, [10] * 5)
    original = baseline.run_once

    def drift(seq, directory):
        result = original(seq, directory)
        if directory.name == "run-2":
            (directory / "raw.jsonl").write_text("changed\n")
        return result

    monkeypatch.setattr(baseline, "run_once", drift)
    out = tmp_path / "case"
    with pytest.raises(ValueError, match="repeatability mismatch"):
        baseline.execute("cache", "labels", out)
    assert (out / "run-2/raw.jsonl").read_text() == "changed\n"
    assert not (out / "manifest.json").exists()
