"""Selected-pair explanations observe the real solver, never replace it."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from visiontrack.cli import main
from visiontrack.core.kalman import KalmanBoxTracker, chi2_gating_threshold
from visiontrack.detection.base import Detection
from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    build_association_explanation,
    create_experiment_bundle,
    detection_payload_sha256,
    run_comparison,
    sha256_json,
)
from visiontrack.lab.association import _AssociationObserver
from visiontrack.tracking import tracker as tracker_module
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def make_bundle(tmp_path, rows, *, overrides=None, start=0):
    records = [DetectionRecord(f, None, key, tuple(box), score, cls)
               for f, detections in enumerate(rows) for key, box, score, cls in detections]
    now = "2026-11-01T12:00:00Z"
    source = SourceManifest.create(
        kind="synthetic", name="association hand fixture",
        detection_sha256=detection_payload_sha256(records, frame_count=len(rows)),
        ground_truth_sha256=None, video_sha256=None, detector={"name": "fixture"},
        frame_count=len(rows), width=300, height=300, fps=30., coordinate_space="pixel_xyxy",
        created_at=now,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id, baseline="baseline",
        variants=({"name": "baseline", "overrides": overrides or {}},),
        metrics=("track_count",), frame_range={"start": start, "end": len(rows)},
        visiontrack_version="0.4.0", git_revision=None,
        environment={"python": "fixture"}, created_at=now,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, records)
    run_comparison(bundle)
    return bundle


BOX = (10., 10., 30., 30.)
D = (7, BOX, .9, 1)


def explain(bundle, frame=1, track_id=1, detection_index=7):
    return build_association_explanation(
        bundle, variant="baseline", frame=frame, track_id=track_id,
        detection_index=detection_index,
    )


def pair(result):
    pairs = [s["pair"] for s in result["stages"] if s["pair"] is not None]
    assert len(pairs) == 1
    return pairs[0]


def snapshot(bundle):
    return {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}


def test_exact_selected_pair_and_immutable_replay(tmp_path):
    bundle = make_bundle(tmp_path, [[D]] * 6)
    before = snapshot(bundle)
    result = explain(bundle, frame=4)
    assert result == explain(bundle, frame=4)
    assert snapshot(bundle) == before
    assert result["schema"] == "visiontrack.association-explanation/v1"
    assert result["track_sha256"] == hashlib.sha256(
        before[Path("runs/baseline/tracks.jsonl")],
    ).hexdigest()
    content = dict(result)
    assert content.pop("explanation_id") == sha256_json(content)
    assert result["accuracy_claim"] is result["physical_identity_verified"] is False
    assert result["public_output_parity"] == "exact_sha256_match"
    assert str(tmp_path) not in json.dumps(result)
    assert [s["stage"] for s in result["stages"]] == [
        "confirmed_high", "confirmed_low", "tentative_high",
    ]
    first = result["stages"][0]
    assert first["track_offered"] and first["detection_offered"]
    p = pair(result)
    assert p["predicted_xyxy"] == list(BOX)
    assert p["iou"] == 1 and p["mahalanobis_squared"] == 0
    assert p["solver_cost"] == 0 and p["maximum_cost"] == .7
    assert p["failed_gates"] == [] and p["outcome"] == "selected"
    assert p["track_matched_detection_index"] == 7
    assert p["detection_matched_track_id"] == 1


@pytest.mark.parametrize("box,cls,overrides,failures", [
    ((100., 100., 120., 120.), 2, {}, ["iou", "class", "mahalanobis"]),
    (BOX, 2, {}, ["class"]),
    ((11., 10., 31., 30.), 1, {"kf_noise_scale": .001}, ["mahalanobis"]),
    ((100., 100., 120., 120.), 1, {"use_mahalanobis_gating": False}, ["iou"]),
])
def test_each_actual_gate_and_multiple_reasons_are_retained(
    tmp_path, box, cls, overrides, failures,
):
    bundle = make_bundle(tmp_path, [[D], [(7, box, .9, cls)]], overrides=overrides)
    p = pair(explain(bundle))
    assert p["failed_gates"] == failures
    assert p["outcome"] == "blocked_by_gate"
    assert p["cost_eligible"] is False
    assert p["track_matched_detection_index"] is None
    assert p["detection_matched_track_id"] is None
    if failures == ["mahalanobis"]:
        assert p["iou"] > p["minimum_iou"]
        assert p["mahalanobis_squared"] > p["mahalanobis_limit"]


@pytest.mark.parametrize("classes,aware", [((1, -1), True), ((-1, 2), True), ((1, 2), False)])
def test_class_agnostic_and_disabled_class_gates(tmp_path, classes, aware):
    bundle = make_bundle(tmp_path, [[(7, BOX, .9, classes[0])], [(7, BOX, .9, classes[1])]],
                         overrides={"class_aware": aware})
    p = pair(explain(bundle))
    assert p["class_gate_enabled"] is aware
    assert p["class_mismatch"] is False
    assert p["outcome"] == "selected"


def test_eligible_pair_not_selected_records_actual_competitor(tmp_path):
    bundle = make_bundle(tmp_path, [[D, (99, BOX, .9, 1)], [D]])
    p = pair(explain(bundle, track_id=2))
    assert p["failed_gates"] == [] and p["cost_eligible"]
    assert p["outcome"] == "eligible_not_selected"
    assert p["track_matched_detection_index"] is None
    assert p["detection_matched_track_id"] == 1


def test_giou_pair_can_exceed_solver_limit_without_hard_gate_failure(tmp_path):
    bundle = make_bundle(tmp_path, [[D], [(7, (15.5, 15.5, 35.5, 35.5), .9, 1)]],
                         overrides={"use_giou": True, "use_mahalanobis_gating": False})
    p = pair(explain(bundle))
    assert p["failed_gates"] == [] and p["iou"] > p["minimum_iou"]
    assert p["solver_cost"] > p["maximum_cost"]
    assert p["outcome"] == "above_cost_limit"


def test_gate_and_solver_boundaries_are_inclusive_and_distances_not_reconstructed(
    tmp_path, monkeypatch,
):
    bundle = make_bundle(tmp_path, [[D], [D]], overrides={"match_iou_thresh": 1.})
    limit = chi2_gating_threshold(dof=4)
    # Put the actual production matrix exactly on its bound. A diagnostic
    # recomputation from the identical boxes would instead yield zero.
    def boundary_distance(self, means, covs, measurements):
        return np.full((len(means), len(measurements)), limit)
    monkeypatch.setattr(KalmanBoxTracker, "gating_distance_batch", boundary_distance)
    p = pair(explain(bundle))
    assert p["iou"] == p["minimum_iou"] == 1.
    assert p["mahalanobis_squared"] == p["mahalanobis_limit"] == limit
    assert p["solver_cost"] == p["maximum_cost"] == 0.
    assert p["outcome"] == "selected" and p["failed_gates"] == []


def test_recovery_does_not_apply_hard_kalman_gate_but_retains_soft_distance(tmp_path):
    rows = [[D]] * 3 + [[(7, BOX, .3, 1)]]
    bundle = make_bundle(tmp_path, rows, overrides={"w_unc": .2})
    result = explain(bundle, frame=3)
    assert result["stages"][1]["pair"] is not None
    p = pair(result)
    assert p["mahalanobis_squared"] == 0 and p["mahalanobis_limit"] is None
    assert p["outcome"] == "selected"


def test_unoffered_low_proposal_is_not_reported_as_gate_failure(tmp_path):
    # Confirmed ID 1 has already matched high detection 7; it is not offered
    # to low detection 99 even though both are the same geometric box.
    bundle = make_bundle(tmp_path, [[D]] * 3 + [[D, (99, BOX, .3, 1)]])
    result = explain(bundle, frame=3, detection_index=99)
    assert all(s["pair"] is None for s in result["stages"])
    assert result["stages"][0]["track_offered"]
    assert not result["stages"][0]["detection_offered"]
    assert not result["stages"][1]["track_offered"]
    assert result["stages"][1]["detection_offered"]
    assert result["detection"]["disposition"] == "unmatched_low_score"


def test_below_score_inputs_and_absolute_warmup(tmp_path):
    bundle = make_bundle(tmp_path, [[D]] * 7 + [[(99, BOX, .05, 1)]], start=3)
    result = explain(bundle, frame=7, detection_index=99)
    assert result["replay_frame_range"] == {"start": 3, "end": 8}
    assert result["stages"][0]["track_offered"]  # confirmed through warm-up
    assert all(not s["detection_offered"] and s["pair"] is None for s in result["stages"])
    assert result["detection"]["disposition"] == "below_low_score"


@pytest.mark.parametrize("field,value", [("frame", True), ("frame", -1), ("frame", 1.),
                                       ("track_id", 0), ("track_id", False),
                                       ("detection_index", -1), ("detection_index", 7.)])
def test_invalid_selectors_fail_before_bundle_access(field, value):
    args = {"frame": 1, "track_id": 1, "detection_index": 7, field: value}
    with pytest.raises(ValueError, match="require integer"):
        build_association_explanation("missing", variant="baseline", **args)


def test_absent_keys_newborn_track_corrupt_input_and_wrong_output_refused(tmp_path):
    bundle = make_bundle(tmp_path, [[D]] * 4)
    with pytest.raises(ValueError, match="detection index does not exist"):
        explain(bundle, detection_index=0)  # position is not the source key 7
    with pytest.raises(ValueError, match="not active before"):
        explain(bundle, track_id=99)
    with pytest.raises(ValueError, match="not active before"):
        explain(bundle, frame=0)  # newborn did not enter association yet
    with pytest.raises(ValueError, match="inside"):
        explain(bundle, frame=4)
    path = bundle / "runs/baseline/tracks.jsonl"
    path.write_bytes(b"")
    run_path = path.with_name("run.json")
    data = json.loads(run_path.read_text())
    data.update(track_sha256=hashlib.sha256(b"").hexdigest(), observation_count=0)
    data.pop("run_id")
    data["run_id"] = sha256_json(data)
    run_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="replay differs"):
        explain(bundle)
    (bundle / "inputs/detections.jsonl").write_text("corrupt\n")
    with pytest.raises(ValueError, match="SHA-256"):
        explain(bundle)


def test_cli_and_no_partial_json_on_error(tmp_path, capsys):
    bundle = make_bundle(tmp_path, [[D]] * 4)
    before = snapshot(bundle)
    args = ["lab-association", str(bundle), "--variant", "baseline", "--frame", "1",
            "--track-id", "1", "--detection-index", "7"]
    assert main(args) == 0
    out = capsys.readouterr()
    assert "selected; failed gates: []" in out.out and not out.err
    assert "Read-only: nothing was written" in out.out
    assert main([*args, "--json"]) == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == explain(bundle)
    assert not out.err
    assert main([*args, "--track-id", "99", "--json"]) == 2
    out = capsys.readouterr()
    assert out.out == "" and out.err.startswith("error:")
    assert snapshot(bundle) == before


def test_missing_production_hook_or_changed_implementation_fails_closed(tmp_path, monkeypatch):
    from visiontrack.lab import initiation

    bundle = make_bundle(tmp_path, [[D]] * 4)
    with monkeypatch.context() as patch:
        patch.setattr(_AssociationObserver, "_association_observer", None)
        with pytest.raises(ValueError, match="observation missing"):
            explain(bundle)
    calls = iter([{"a.py": "a" * 64}, {"a.py": "b" * 64}])
    monkeypatch.setattr(initiation, "_implementation_hashes", lambda: next(calls))
    with pytest.raises(ValueError, match="implementation changed"):
        explain(bundle)


@pytest.mark.parametrize("overrides", [
    {}, {"use_giou": True}, {"w_unc": .2}, {"w_ocm": .2, "use_oru": True},
    {"class_aware": False}, {"n_init": 1}, {"use_mahalanobis_gating": False},
    {"w_ocm": .2, "ocm_delta_t": 9, "use_oru": True},
])
def test_observation_is_exact_and_calls_production_solver_once_per_nonempty_stage(
    overrides, monkeypatch,
):
    cfg = replace(TrackerConfig(), **overrides)
    plain = ByteTracker(replace(cfg))
    observer = _AssociationObserver(cfg, track_id=1, detection_index=7,
                                    offset=0, start=0, end=30)
    original = tracker_module.associate
    calls = []
    def counted(cost, max_cost):
        calls.append(cost.copy())
        return original(cost, max_cost)
    monkeypatch.setattr(tracker_module, "associate", counted)
    for frame in range(30):
        detections = [Detection(np.array([x, 10., x + 20., 30.]), score, cls)
                      for x, score, cls in [(10. + frame, .9, 1), (50. - frame, .3, 2)]
                      if frame not in (5, 6, 22)]
        observer._detection_keys = (7, 99) if detections else ()
        inputs = [d.xyxy.tobytes() for d in detections]
        before = len(calls)
        expected = plain.update(detections)
        reference_calls = calls[before:]
        before = len(calls)
        actual = observer.update(detections)
        observed_calls = calls[before:]
        assert len(reference_calls) == len(observed_calls)
        assert all(a.tobytes() == b.tobytes()
                   for a, b in zip(reference_calls, observed_calls, strict=True))
        assert len(expected) == len(actual)
        for a, b in zip(expected, actual, strict=True):
            assert (a.frame, a.track_id, a.class_id, a.score) == (
                b.frame, b.track_id, b.class_id, b.score,
            )
            assert a.xyxy.tobytes() == b.xyxy.tobytes()
        assert [d.xyxy.tobytes() for d in detections] == inputs
