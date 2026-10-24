"""Authored default-tracker mechanism checks; not real-data accuracy evidence."""
import json
import sys
from dataclasses import replace

import numpy as np
import pytest

from experiments import mot17_case_trace as trace
from experiments.mot17_case_baseline import encoded, run_once
from visiontrack.detection.base import Detection
from visiontrack.detection.mot_loader import FrameData
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def detection(x=0., score=0.9):
    return Detection(np.array([x, 0., x + 10., 20.]), score=score, class_id=0)


def observe(scores):
    tracker, events, public = ByteTracker(), [], []
    for frame, score in enumerate(scores, start=1):
        public.append(trace.observed_update(
            tracker, [detection(score=score)], frame, events.append))
    return tracker, events, public


def test_actual_creation_three_hits_and_public_confirmation():
    tracker, events, public = observe([0.9, 0.9, 0.9])
    assert [[o.track_id for o in batch] for batch in public] == [[], [], [1]]
    birth = next(e for e in events if e["kind"] == "_spawn")
    assert birth["detection_row"] == 1
    assert birth["created"][0]["hits"] == 1
    assert birth["created"][0]["start_frame"] == 0
    matches = [e for e in events if e["kind"] == "_apply_match"]
    assert [e["after"]["hits"] for e in matches] == [2, 3]
    assert matches[-1]["before"]["state"] == "TENTATIVE"
    assert matches[-1]["after"]["state"] == "CONFIRMED"
    assert tracker.frame_index == 2


def test_actual_stage_mask_solver_and_one_based_source_rows():
    _, events, _ = observe([0.9] * 4)
    stage = next(e for e in events if e["kind"] == "_match"
                 and e["source_frame"] == 4 and e["stage"] == "confirmed_high")
    assert stage["detection_rows"] == [1]
    assert stage["tracks"][0]["track_id"] == 1
    assert stage["forbidden"] == [[False]]
    assert stage["proposed_rows"] == stage["proposed_columns"] == [0]
    assert stage["matches"] == [[0, 0]]
    assert stage["matrices"]["ious"] == [[1.]]
    assert stage["matrices"]["gating_d2"] == [[0.]]
    assert stage["gate_threshold"] > 0


def test_low_can_recover_confirmed_but_cannot_create_tentative():
    _, events, public = observe([0.2, 0.9, 0.9, 0.9, 0.2])
    assert [len(batch) for batch in public] == [0, 0, 0, 1, 1]
    assert not any(e["kind"] == "_spawn" and e["source_frame"] == 1 for e in events)
    low = next(e for e in events if e["kind"] == "_match" and e["source_frame"] == 5
               and e["stage"] == "confirmed_low_recovery")
    assert low["matches"] == [[0, 0]]
    assert low["matrices"]["gating_d2"] is None  # inactive, not measured zero
    assert low["gate_requested"] is False


def test_low_does_not_confirm_tentative_and_missed_tentative_is_deleted():
    _, events, public = observe([0.9, 0.2])
    assert public == [[], []]
    missed = next(e for e in events if e["kind"] == "mark_missed")
    assert missed["before"]["state"] == "TENTATIVE"
    assert missed["after"]["state"] == "DELETED"


def test_alive_is_not_public_when_unmatched():
    tracker, _, _ = observe([0.9] * 3)
    events = []
    assert trace.observed_update(tracker, [], 4, events.append) == []
    end = events[-1]
    assert end["public_ids"] == []
    assert end["tracks"][0]["state"] == "CONFIRMED"
    assert end["tracks"][0]["time_since_update"] == 1


def test_many_objects_does_not_change_frozen_synthetic_observer_limits():
    tracker, events = ByteTracker(), []
    assert trace.observed_update(tracker, [detection(20. * i) for i in range(34)],
                                 1, events.append) == []
    assert len(events[-1]["tracks"]) == 34
    from experiments.box_gate_trace import MAX_FRAMES, MAX_OBJECTS
    assert (MAX_FRAMES, MAX_OBJECTS) == (300, 32)


def test_existing_profiler_is_not_replaced():
    def profiler(*args):
        pass
    sys.setprofile(profiler)
    try:
        with pytest.raises(ValueError, match="existing profiler"):
            trace.observed_update(ByteTracker(), [], 1, lambda e: None)
        assert sys.getprofile() is profiler
    finally:
        sys.setprofile(None)


def test_observer_exception_clears_profiler():
    def fail(record):
        if record["kind"] == "_match":
            raise ValueError("intentional observation failure")
    with pytest.raises(ValueError, match="intentional observation"):
        trace.observed_update(ByteTracker(), [], 1, fail)
    assert sys.getprofile() is None


def test_nondefault_tracker_rejected():
    with pytest.raises(ValueError, match="default tracker"):
        trace.observed_update(ByteTracker(replace(TrackerConfig(), n_init=1)),
                              [], 1, lambda e: None)


@pytest.mark.parametrize("value", [np.array([np.nan]), np.zeros(256 * 256 + 1)])
def test_bad_snapshot_array_rejected(value):
    with pytest.raises(ValueError):
        trace.array(value)


class Sequence:
    length = 6

    def iter_range(self, first, last):
        for frame in range(first, last + 1):
            yield FrameData(
                frame=frame, det_xyxy=np.array([[0., 0., 10., 20.]]),
                det_scores=np.array([0.9]), gt_xyxy=np.array([[0., 0., 10., 20.]]),
                gt_ids=np.array([7]), gt_classes=np.array([1]),
                gt_conf=np.array([1.]), gt_vis=np.array([1.]))


def contents(tmp_path):
    directory = tmp_path / "baseline"
    run_once(Sequence(), directory)
    return {f"run-1/{name}": (directory / name).read_bytes() for name in (
        "raw.jsonl", "scored.jsonl", "failures.jsonl", "summary.json")}


def test_full_replay_exact_raw_scored_failures_and_clear(tmp_path):
    saved = contents(tmp_path)
    out = tmp_path / "replay"
    out.mkdir()
    result = trace.replay(Sequence(), saved, dict(source_window=[3, 4]), out)
    assert result["frame_count"] == 6 and result["raw_public_boxes"] == 4
    assert result["exact_raw_and_scored_parity"] is True
    for name in ("raw.jsonl", "scored.jsonl", "failures.jsonl"):
        assert (out / name).read_bytes() == saved[f"run-1/{name}"]
    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert {e["source_frame"] for e in events} == {3, 4}


@pytest.mark.parametrize("defect", ["input", "raw", "scored", "failures", "metrics", "length"])
def test_replay_stops_on_disagreement_not_silent_retry(tmp_path, defect):
    saved = contents(tmp_path)
    if defect in ("input", "raw", "scored"):
        name = "scored" if defect == "scored" else "raw"
        rows = [json.loads(line) for line in saved[f"run-1/{name}.jsonl"].splitlines()]
        if defect == "input":
            rows[4]["detection_scores"][0] = 0.8
        else:
            rows[4]["track_ids"][0] = 99
        saved[f"run-1/{name}.jsonl"] = "".join(encoded(r) for r in rows).encode()
    elif defect == "failures":
        saved["run-1/failures.jsonl"] += b"{}\n"
    elif defect == "metrics":
        summary = json.loads(saved["run-1/summary.json"])
        summary["metrics"]["FN"] += 1
        saved["run-1/summary.json"] = encoded(summary).encode()
    else:
        saved["run-1/raw.jsonl"] += b"{}\n"
    out = tmp_path / "replay"
    out.mkdir()
    with pytest.raises(ValueError):
        trace.replay(Sequence(), saved, dict(source_window=[3, 4]), out)
    assert not (out / "manifest.json").exists()


def test_selection_is_same_first_event_and_last_match_history():
    event = dict(event_type="id_switch", source_frame=10, gt_id=7)
    failures = "".join(encoded(dict(event_type="miss", source_frame=f, gt_id=7))
                       for f in (7, 8, 9)) + encoded(event)
    saved = {
        "run-1/summary.json": encoded(dict(first_chronological_switch=event)).encode(),
        "run-1/failures.jsonl": failures.encode(),
        "run-1/scored.jsonl": "".join(encoded(dict(source_frame=f, gt_ids=[7]))
                                      for f in range(1, 15)).encode()}
    assert trace.selection(saved)["source_window"] == [5, 13]
    assert trace.selection(saved)["last_scored_match"] == 6


def test_existing_output_refused_before_reading_baseline(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        trace.execute(tmp_path / "missing", None, None, tmp_path)
