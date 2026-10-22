"""Development replay checks; no held-out tracker evaluations."""

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import traffic_runner as runner
from experiments.traffic_protocol import ROOT, load_frozen_protocol
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker, TrackObservation


@pytest.fixture(scope="module")
def control():
    return runner.run_development(scenario="solo", seed=101, condition="control")


def test_real_baseline_reset_provenance_and_serialization(control):
    spec, hashes = load_frozen_protocol()
    assert control["protocol_hashes"] == hashes
    assert control["source"]["baseline"]["revision"] == spec["baseline_revision"]
    assert "src/visiontrack/tracking/tracker.py" in control["source"]["baseline"]["files"]
    assert control["config"] == spec["tracker_config"] == asdict(TrackerConfig())
    assert len(control["detection_sha256"]) == 64
    assert control["detection_features"] is None
    assert control["environment"]["numpy"] == np.__version__
    assert control["replay"] == {
        "passes": 3,
        "reset_equal": True,
        "fresh_equal": True,
        "updates_per_pass": 300,
    }
    assert control["heldout_tracking_executed"] is False
    assert control["complete_study_report"] is False
    # n_init=3: preserve the public confirmation gap, no synthetic first rows.
    assert control["output"][0]["frame"] == 2
    assert len(control["output"]) == 298
    assert {r["track_id"] for r in control["output"]} == {1}
    assert control["output"][-1]["frame"] == 299
    assert (
        hashlib.sha256(runner._json_bytes(control["output"])).hexdigest()
        == control["output_sha256"]
    )
    clone = json.loads(json.dumps(control, allow_nan=False))
    digest = clone.pop("record_sha256")
    assert hashlib.sha256(runner._json_bytes(clone)).hexdigest() == digest
    assert control["crossing"]["bottom_centre"]["summary"]["event_error"] == 0
    tracking = control["diagnostics"]["overall"]
    assert tracking["matched_object_frames"] == 298
    assert tracking["missed_object_frames"] == 2
    assert tracking["id_switches"] == tracking["false_positive_rows"] == 0
    assert control["diagnostics"]["input_sha256"] == control["input"]["input_sha256"]


def test_repeat_is_byte_identical(control):
    repeated = runner.run_development(scenario="solo", seed=101, condition="control")
    assert runner._json_bytes(repeated) == runner._json_bytes(control)


@pytest.mark.parametrize("condition", ["perspective_only", "box_error_only", "combined"])
def test_other_development_conditions_are_finite_and_complete(condition):
    result = runner.run_development(scenario="opposing", seed=101, condition=condition)
    assert result["input"]["split"] == "development"
    assert result["input"]["condition"] == condition
    assert result["replay"]["reset_equal"] and result["replay"]["fresh_equal"]
    assert set(result["crossing"]) == {"bottom_centre", "box_centre"}
    assert result["output"][-1]["frame"] == 299
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "scenario,seed",
    [
        ("offcentre", 1001),
        ("close_opposing", 1001),
        ("slanted", 1001),
        ("solo", 1001),
        ("solo", True),
        ("unknown", 101),
    ],
)
def test_non_development_selectors_rejected_before_tracker(monkeypatch, scenario, seed):
    def forbidden(*args, **kwargs):
        pytest.fail("tracker construction must not occur")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker", forbidden)
    with pytest.raises(ValueError):
        runner.run_development(scenario=scenario, seed=seed, condition="control")


def test_no_split_override():
    with pytest.raises(TypeError):
        runner.run_development(
            split="heldout", scenario="offcentre", seed=1001, condition="control"
        )


def test_broken_reset_fails_closed(monkeypatch):
    monkeypatch.setattr(ByteTracker, "reset", lambda self: None)
    with pytest.raises(ValueError, match="start at frame"):
        runner.run_development(scenario="solo", seed=101, condition="control")


def test_replay_mismatch_fails_closed(monkeypatch):
    calls = []

    def inconsistent(*args):
        calls.append(None)
        return [{"changed": len(calls)}]

    monkeypatch.setattr(runner, "_replay", inconsistent)
    with pytest.raises(ValueError, match="replay mismatch"):
        runner.run_development(scenario="solo", seed=101, condition="control")


def test_source_drift_checked_before_tracking(monkeypatch):
    def drift(*args):
        raise ValueError("baseline source drift")

    monkeypatch.setattr(runner, "_verify_tree", drift)
    monkeypatch.setattr(ByteTracker, "update", lambda *args: pytest.fail("must not track"))
    with pytest.raises(ValueError, match="source drift"):
        runner.run_development(scenario="solo", seed=101, condition="control")


def test_shadowed_import_rejected(monkeypatch, tmp_path):
    monkeypatch.setitem(
        sys.modules, "visiontrack.shadow", SimpleNamespace(__file__=str(tmp_path / "wheel.py"))
    )
    with pytest.raises(ValueError, match="verified checkout"):
        runner._check_import_origins()


def _source_tree(tmp_path):
    package = tmp_path / "src/visiontrack"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# original\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "src"], check=True)
    revision = runner._git(tmp_path, "write-tree").decode().strip()
    return package, revision


def test_tree_verification_ignores_git_index_as_authority(tmp_path):
    package, revision = _source_tree(tmp_path)
    accepted = runner._verify_tree(tmp_path, revision)
    assert accepted["files"] == {
        "src/visiontrack/__init__.py": hashlib.sha256(b"# original\n").hexdigest()
    }
    (package / "__init__.py").write_text("# modified\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "src"], check=True)
    with pytest.raises(ValueError, match="source drift"):
        runner._verify_tree(tmp_path, revision)


@pytest.mark.parametrize("kind", ["extra", "symlink", "missing", "large"])
def test_invalid_package_tree_rejected(tmp_path, kind):
    package, revision = _source_tree(tmp_path)
    path = package / "__init__.py"
    if kind == "extra":
        (package / "extra.py").write_text("# extra\n")
    elif kind == "symlink":
        path.unlink()
        target = tmp_path / "other.py"
        target.write_text("# original\n")
        path.symlink_to(target)
    elif kind == "missing":
        path.unlink()
    else:
        path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises((OSError, ValueError)):
        runner._verify_tree(tmp_path, revision)


class FakeTracker:
    def __init__(self, outputs):
        self.frame_index = -1
        self.outputs = outputs
        self.received = []

    def update(self, detections):
        self.frame_index += 1
        self.received.append(detections)
        return self.outputs[self.frame_index]


def _tiny_replay(outputs):
    boxes = np.array([[[10.0, 10.0, 20.0, 20.0]]] * len(outputs))
    boxes.flags.writeable = False
    scene = SimpleNamespace(observed_boxes=boxes)
    spec = {
        "frame_grid": {"frames": len(outputs), "width": 100, "height": 100},
        "ideal_box": {"score": 0.9, "class_id": 0},
    }
    return FakeTracker(outputs), scene, spec


def _observation(frame=0, identity=7, box=None, score=0.9, class_id=0):
    return TrackObservation(
        frame, identity, np.array([10.0, 10.0, 20.0, 20.0] if box is None else box), score, class_id
    )


def test_public_rows_are_not_filled_or_truth_id_filtered():
    tracker, scene, spec = _tiny_replay(
        [
            [_observation(0)],
            [],
            [_observation(2)],
        ]
    )
    rows = runner._replay(tracker, scene, spec)
    assert [(r["frame"], r["track_id"]) for r in rows] == [(0, 7), (2, 7)]
    for received in tracker.received:
        assert len(received) == 1
        detection = received[0]
        assert detection.feature is None
        assert detection.score == 0.9 and detection.class_id == 0
        assert not hasattr(detection, "track_id") and not hasattr(detection, "object_id")
        assert not np.shares_memory(detection.xyxy, scene.observed_boxes)
    # The adapter passes the gap to the scorer, not an interpolated crossing.
    projection = runner.GroundProjection(np.eye(3))
    assert len(runner._anchor_samples(rows, projection, "bottom_centre")) == 2


@pytest.mark.parametrize(
    "observation",
    [
        _observation(frame=1),
        _observation(frame=False),
        _observation(identity=0),
        _observation(identity=True),
        _observation(identity=1.5),
        _observation(box=[10, 10, 10, 20]),
        _observation(box=[-1, 10, 20, 20]),
        _observation(box=[10, 10, 101, 20]),
        _observation(box=[10, 10, float("nan"), 20]),
        _observation(score=float("inf")),
        _observation(score=-0.1),
        _observation(score=1.1),
        _observation(score=True),
        _observation(class_id=1),
        _observation(class_id=False),
        _observation(class_id=0.0),
    ],
)
def test_invalid_public_rows_invalidate_run(observation):
    with pytest.raises(ValueError):
        runner._replay(*_tiny_replay([[observation]]))


def test_duplicate_output_ids_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        runner._replay(*_tiny_replay([[_observation(), _observation()]]))


def test_anchor_coordinates_derived_from_same_public_box():
    row = {"frame": 5, "track_id": 12, "xyxy": [2.0, 4.0, 6.0, 12.0]}
    projection = runner.GroundProjection(np.eye(3))
    assert runner._anchor_samples([row], projection, "bottom_centre") == [
        runner.AnchorSample(5, 12, 4, 12)
    ]
    assert runner._anchor_samples([row], projection, "box_centre") == [
        runner.AnchorSample(5, 12, 4, 8)
    ]


def test_cli_failure_is_nonzero_and_no_heldout_override(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["traffic_runner", "--scenario", "offcentre", "--seed", "1001", "--condition", "control"],
    )
    assert runner.main() == 2
    assert "failed" in capsys.readouterr().err


def test_frozen_artifacts_and_production_sources_unchanged():
    spec, _ = load_frozen_protocol()
    assert runner._verify_tree(ROOT, spec["baseline_revision"])["files"]
