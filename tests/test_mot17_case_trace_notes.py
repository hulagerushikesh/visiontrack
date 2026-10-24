"""Readable stage/confirmation counterexample; synthetic, not MOT17 footage."""
import json

import pytest

from experiments import mot17_case_trace_notes as notes
from experiments.mot17_case_baseline import encoded
from experiments.mot17_case_trace import observed_update
from tests.test_mot17_case_trace import detection
from visiontrack.tracking.tracker import ByteTracker


@pytest.fixture
def example():
    tracker, events, rows = ByteTracker(), [], []
    for frame in range(1, 8):
        dets = [detection()]
        if frame >= 4:
            dets.append(detection(40., score=0.2 if frame == 4 else 0.9))
        observed_update(tracker, dets, frame, events.append)
        rows.append(dict(source_frame=frame, gt_ids=[7], gt_xyxy=[[40., 0., 50., 20.]],
                         gt_classes=[1], gt_consider=[1.],
                         detections_xyxy=[d.xyxy.tolist() for d in dets],
                         detection_scores=[d.score for d in dets]))
    event = dict(gt_id=7, previous_hyp_id=1, hyp_id=2, source_frame=7)
    contents = dict(
        **{"summary.json": encoded(dict(
            exact_raw_and_scored_parity=True, exact_failures_parity=True, frame_count=7,
            selected=dict(event=event, source_window=[1, 7]))).encode()},
        **{"events.jsonl": "".join(encoded(e) for e in events).encode(),
           "raw.jsonl": "".join(encoded(r) for r in rows).encode()})
    return contents


def test_readable_timeline_preserves_stage_priority_birth_and_confirmation(example):
    result = notes.summarize(example)
    f4, f5, f6, f7 = result["frames"][3:]
    assert f4["best_raw"] == dict(row=2, score=0.2, iou_to_reference=1.,
                                  accepted_by=[], spawned_ids=[])
    assert f4["best_raw_stage_membership"] == [
        dict(stage="confirmed_high", offered=False, target_tracks_present=[1]),
        dict(stage="confirmed_low_recovery", offered=True, target_tracks_present=[]),
        dict(stage="tentative_leftover_high", offered=False, target_tracks_present=[])]
    assert f4["actual_best_raw_target_pairs"] == []  # absent pair, NOT a zero gate distance
    assert f4["target_updates"][0]["track_id"] == 1
    assert f4["target_updates"][0]["raw_iou_to_reference"] == 0.
    assert f5["best_raw"]["spawned_ids"] == [2]
    assert f5["public_target_ids"] == [1]
    assert f6["public_target_ids"] == [1]
    assert f7["public_target_ids"] == [1, 2]
    assert f6["best_raw"]["accepted_by"] == f7["best_raw"]["accepted_by"] == [2]
    assert result["physical_identity_established"] is False
    assert result["counterfactual_improvement_tested"] is False


def test_both_iou_and_gate_can_forbid_but_not_a_gate_only_diagnosis(example):
    frame = notes.summarize(example)["frames"][4]
    pair = frame["actual_best_raw_target_pairs"][0]
    assert pair["track_id"] == 1
    assert pair["iou"] < 0.3
    assert pair["d2"] > pair["gate_threshold"]
    assert pair["forbidden"] is True
    assert pair["cost"] > pair["max_cost"]


def test_shared_geometry_keeps_both_scoring_neighbors_not_physical_identity():
    raw = dict(gt_ids=[7, 8, 9, 10], gt_classes=[1, 1, 7, 1],
               gt_consider=[1., 1., 1., 0.],
               gt_xyxy=[[0., 0., 10., 20.]] * 4)
    assert notes.scoring_neighbors(raw, [0., 0., 10., 20.]) == [
        dict(gt_id=7, iou=1.), dict(gt_id=8, iou=1.)]


def test_update_without_accepted_assignment_refused(example):
    events = [json.loads(s) for s in example["events.jsonl"].splitlines()]
    next(e for e in events if e["kind"] == "_apply_match")["detection_row"] = 99
    example["events.jsonl"] = "".join(encoded(e) for e in events).encode()
    with pytest.raises(ValueError, match="accepted stage pair"):
        notes.summarize(example)


@pytest.mark.parametrize("defect", ["parity", "window", "raw"])
def test_incomplete_or_unverified_notes_refused(example, defect):
    if defect == "raw":
        example["raw.jsonl"] = b"\n".join(example["raw.jsonl"].splitlines()[1:])
    else:
        summary = json.loads(example["summary.json"])
        if defect == "parity":
            summary["exact_raw_and_scored_parity"] = False
        else:
            summary["selected"]["source_window"] = [2, 7]
        example["summary.json"] = encoded(summary).encode()
    with pytest.raises(ValueError):
        notes.summarize(example)
