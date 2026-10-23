"""Authored implementation fixtures ONLY, not saved-study diagnostic replays."""

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from experiments import box_gate_trace as trace
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def detections(x=0.0, score=0.9, class_id=0):
    return [Detection(np.array([x, 0.0, x + 20.0, 40.0]), score, class_id)]


def rows(observations):
    return [dict(frame=o.frame, track_id=o.track_id, xyxy=o.xyxy.tolist(),
                 score=o.score, class_id=o.class_id) for o in observations]


def run(frames, *, gate=True, selection=None):
    reference = ByteTracker(TrackerConfig(use_mahalanobis_gating=gate))
    expected = [row for batch in copy.deepcopy(frames) for row in rows(reference.update(batch))]
    observed = ByteTracker(TrackerConfig(use_mahalanobis_gating=gate))
    report = trace.observe_sequence(
        observed, frames, frames=selection or list(range(len(frames))), expected_output=expected,
    )
    # Compare internal state too; output equality alone could conceal latent drift.
    assert observed._next_id == reference._next_id
    assert observed.frame_index == reference.frame_index
    assert len(observed.tracks) == len(reference.tracks)
    for actual, wanted in zip(observed.tracks, reference.tracks, strict=True):
        for key in actual.__slots__:
            if key == "kf":
                continue
            av, wv = getattr(actual, key), getattr(wanted, key)
            if isinstance(av, np.ndarray):
                np.testing.assert_array_equal(av, wv, strict=True)
                assert av.tobytes() == wv.tobytes()
            elif key in ("history", "last_obs_state"):
                assert len(av) == len(wv)
                for a, w in zip(av, wv, strict=True):
                    np.testing.assert_array_equal(a, w, strict=True)
                    assert a.tobytes() == w.tobytes()
            else:
                assert av == wv
    return report, observed


@pytest.mark.parametrize("gate", [True, False])
def test_exact_outputs_states_and_input_immutability(gate):
    frames = [detections(f * 0.25) for f in range(10)]
    before = [[d.xyxy.copy() for d in batch] for batch in frames]
    report, tracker = run(frames, gate=gate, selection=[0, 2, 5, 9])
    assert report["exact_public_output_parity"] is True
    assert report["provenance_verified"] is False
    assert report["validation_evidence"] is False
    assert report["interpretation_allowed"] is False  # Needs the future provenance gate.
    assert {e["frame"] for e in report["events"]} == {0, 2, 5, 9}
    for f, batch in enumerate(frames):
        np.testing.assert_array_equal(batch[0].xyxy, before[f][0])
    # Snapshots do not retain mutable references to state/detection arrays.
    snapshot = json.dumps(report, sort_keys=True)
    tracker.tracks[0].mean[:] = 999
    frames[0][0].xyxy[:] = 888
    assert json.dumps(report, sort_keys=True) == snapshot
    assert sys.getprofile() is None


@pytest.mark.parametrize("gate", [True, False])
def test_actual_gates_stage_mapping_and_startup(gate):
    report, _ = run([detections() for _ in range(4)], gate=gate)
    events = report["events"]
    assert [e["before"]["stage"] for e in events if e["kind"] == "association"] == (
        list(trace.STAGES) * 4
    )
    tentative = next(e for e in events if e["kind"] == "association"
                     and e["frame"] == 1 and e["before"]["stage"] == trace.STAGES[2])
    assert tentative["before"]["detection_ordinals"] == [0]
    assert tentative["matches"] == [[0, 0]]
    assert tentative["matrices"]["ious"] == [[1.0]]
    assert (tentative["matrices"]["gating_d2"] is not None) is gate
    assert (tentative["gate_threshold"] is not None) is gate
    assert [e["public_output"] for e in events if e["kind"] == "frame_end"][:2] == [[], []]
    assert any(e["kind"] == "_spawn" for e in events)
    assert any(e["kind"] == "cost_build" and e["forbidden"] == [[False]] for e in events)
    assert any(e["kind"] == "assignment" and e["proposed_rows"] == [0] for e in events)


def test_iou_and_class_forbidden_and_rejected_solver_proposals():
    frames = [detections() for _ in range(3)] + [detections(class_id=1), detections(100.0)]
    report, _ = run(frames)
    masks = [e for e in report["events"] if e["kind"] == "cost_build"]
    assert any(e["forbidden"] == [[True]] for e in masks)
    rejected = [e for e in report["events"] if e["kind"] == "association"
                and e["matrices"]["cost"] is not None and not e["matches"]]
    assert rejected
    assert any(e["matrices"]["class_mismatch"] == [[True]] for e in rejected)


def test_mahalanobis_rejection_with_eligible_iou_is_visible():
    # Center/height unchanged; width is 30% of the predicted box. IoU is
    # eligible at exactly 0.3, while the changed aspect drives the 4D veto.
    narrow = [Detection(np.array([7.0, 0.0, 13.0, 40.0]), 0.9, 0)]
    report, _ = run([detections() for _ in range(3)] + [narrow])
    association = next(e for e in report["events"] if e["kind"] == "association"
                       and e["frame"] == 3 and e["before"]["stage"] == trace.STAGES[0])
    assert association["matrices"]["ious"][0][0] >= association["before"]["iou_threshold"]
    assert association["matrices"]["gating_d2"][0][0] > association["gate_threshold"]
    assert association["matches"] == []
    assert association["unmatched_tracks"] == [0]


def test_no_extra_gating_or_kalman_update_calls(monkeypatch):
    from visiontrack.core.kalman import KalmanBoxTracker
    counts = dict(gating_distance_batch=0, update=0)
    for name in counts:
        original = getattr(KalmanBoxTracker, name)
        def spy(self, *args, _name=name, _original=original, **kwargs):
            counts[_name] += 1
            return _original(self, *args, **kwargs)
        monkeypatch.setattr(KalmanBoxTracker, name, spy)
    frames = [detections() for _ in range(5)]
    tracker = ByteTracker()
    expected = [row for batch in copy.deepcopy(frames) for row in rows(tracker.update(batch))]
    reference_counts = counts.copy()
    counts.update(gating_distance_batch=0, update=0)
    trace.observe_sequence(ByteTracker(), frames, frames=list(range(5)), expected_output=expected)
    assert counts == reference_counts == dict(gating_distance_batch=4, update=4)


def test_low_recovery_and_original_input_ordinals():
    frames = [detections() for _ in range(3)]
    frames.append(detections(100.0) + detections(score=0.3))
    report, _ = run(frames)
    recovery = next(e for e in report["events"] if e["kind"] == "association"
                    and e["frame"] == 3 and e["before"]["stage"] == trace.STAGES[1])
    assert recovery["before"]["detection_ordinals"] == [1]
    assert recovery["matches"] == [[0, 0]]
    assert recovery["matrices"]["gating_d2"] is None
    assert recovery["gate_threshold"] is None
    assert recovery["before"]["iou_threshold"] == 0.5


def test_tentative_deletion_and_confirmed_expiry():
    report, tracker = run([detections(), []])
    deletion = next(e for e in report["events"] if e["kind"] == "mark_missed")
    assert deletion["before"]["track"]["state"] == "TENTATIVE"
    assert deletion["after"]["state"] == "DELETED"
    assert tracker.tracks == []
    report, tracker = run([detections() for _ in range(3)] + [[] for _ in range(31)])
    assert tracker.tracks == []
    assert any(e["kind"] == "mark_missed" and e["after"]["state"] == "DELETED"
               for e in report["events"])


def test_empty_sequence_of_detections_is_observable():
    report, _ = run([[], []])
    assert report["public_output"] == []
    assert all(e["matrices"]["cost"] is None for e in report["events"]
               if e["kind"] == "association")


def test_mismatch_raises_with_failed_evidence_no_permission():
    with pytest.raises(trace.ParityMismatch) as exc:
        trace.observe_sequence(ByteTracker(), [detections() for _ in range(3)],
                               frames=[0, 1, 2], expected_output=[])
    failed = exc.value.diagnostic
    assert failed["exact_public_output_parity"] is False
    assert failed["interpretation_allowed"] is False
    assert failed["actual_output_sha256"] != failed["expected_output_sha256"]
    assert failed["events"]
    assert sys.getprofile() is None


def test_profiler_restored_after_callback_error(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("injected observer failure")
    monkeypatch.setattr(trace._Observer, "__call__", broken)
    with pytest.raises(RuntimeError, match="observer failure"):
        trace.observe_sequence(ByteTracker(), [detections()], frames=[0], expected_output=[])
    assert sys.getprofile() is None


def test_tracker_error_restores_profiler(monkeypatch):
    def broken(*args):
        raise RuntimeError("injected tracker failure")
    monkeypatch.setattr(ByteTracker, "_observations", broken)
    with pytest.raises(RuntimeError, match="tracker failure"):
        trace.observe_sequence(ByteTracker(), [detections()], frames=[0], expected_output=[])
    assert sys.getprofile() is None


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_existing_hooks_not_replaced(hook):
    setter, getter = getattr(sys, "set" + hook), getattr(sys, "get" + hook)
    def existing(*args):
        return existing
    setter(existing)
    try:
        with pytest.raises(ValueError, match="existing profiler"):
            trace.observe_sequence(ByteTracker(), [[]], frames=[0], expected_output=[])
        assert getter() is existing
    finally:
        setter(None)


@pytest.mark.parametrize("frames", [[], [True], [1, 0], [0, 0], [-1], [2], tuple([0])])
def test_invalid_selected_frames_before_update(frames):
    tracker = ByteTracker()
    with pytest.raises(ValueError, match="selected frames"):
        trace.observe_sequence(tracker, [[], []], frames=frames, expected_output=[])
    assert tracker.frame_index == -1


@pytest.mark.parametrize("change", ["used", "config", "feature", "duplicate", "nan", "oversize"])
def test_invalid_context_before_update(change):
    tracker, frames = ByteTracker(), [detections()]
    if change == "used":
        tracker.update([])
    elif change == "config":
        tracker.cfg.w_unc = 1.0
    elif change == "feature":
        frames[0][0].feature = np.ones(2)
    elif change == "duplicate":
        frames[0].append(frames[0][0])
    elif change == "nan":
        frames[0][0].xyxy[0] = float("nan")
    else:
        frames *= 301
    before = tracker.frame_index
    with pytest.raises(ValueError):
        trace.observe_sequence(tracker, frames, frames=[0], expected_output=[])
    assert tracker.frame_index == before


def test_main_thread_only():
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(trace.observe_sequence, ByteTracker(), [[]],
                             frames=[0], expected_output=[])
        with pytest.raises(ValueError, match="main-thread"):
            result.result()


def test_event_and_track_budget_fail_loudly(monkeypatch):
    monkeypatch.setattr(trace, "MAX_EVENTS", 1)
    with pytest.raises(ValueError, match="event budget"):
        trace.observe_sequence(ByteTracker(), [[]], frames=[0], expected_output=[])
    assert sys.getprofile() is None


def test_oversized_detection_list_refused_before_update():
    tracker = ByteTracker()
    with pytest.raises(ValueError, match="bounded distinct"):
        trace.observe_sequence(tracker, [[detections()[0] for _ in range(33)]],
                               frames=[0], expected_output=[])
    assert tracker.frame_index == -1


def test_track_growth_budget_also_checked_on_last_unselected_frame():
    frames = [
        [detections(i * 40.0, class_id=0 if f < 3 else 1)[0] for i in range(32)]
        for f in range(4)
    ]
    # The 32 confirmed old tracks survive while 32 new tentative tracks spawn.
    with pytest.raises(ValueError, match="track budget"):
        trace.observe_sequence(ByteTracker(), frames, frames=[0], expected_output=[])
    assert sys.getprofile() is None


def test_missing_stages_fail_closed(monkeypatch):
    monkeypatch.setattr(ByteTracker, "update", lambda self, detections: [])
    with pytest.raises(ValueError, match="incomplete observed frame"):
        trace.observe_sequence(ByteTracker(), [[]], frames=[0], expected_output=[])
    assert sys.getprofile() is None


@pytest.mark.parametrize("value", [np.array([float("inf")]), np.zeros((33, 33))])
def test_array_guard(value):
    with pytest.raises(ValueError, match="trace array"):
        trace._array(value)


def test_expected_nonfinite_value_refused_before_update():
    tracker = ByteTracker()
    with pytest.raises(ValueError):
        trace.observe_sequence(tracker, [[]], frames=[0], expected_output=[dict(x=float("nan"))])
    assert tracker.frame_index == -1


def test_exact_json_parity_does_not_tolerate_numeric_type_drift():
    tracker = ByteTracker()
    frames = [detections() for _ in range(3)]
    expected = [row for batch in copy.deepcopy(frames) for row in rows(tracker.update(batch))]
    expected[0]["track_id"] = float(expected[0]["track_id"])
    with pytest.raises(trace.ParityMismatch):
        trace.observe_sequence(ByteTracker(), frames, frames=[2], expected_output=expected)


def test_fixed_selection_covers_both_boundaries_and_shared_extra():
    frames = trace.selected_frames([127.29480328576642, 134.31310297954988, 149.5])
    assert set(range(4)) <= set(frames)
    assert set(range(126, 130)) <= set(frames)
    assert set(range(133, 168)) <= set(frames)
    assert set(range(208, 243)) <= set(frames)
    assert frames == sorted(set(frames))
    assert frames == trace.selected_frames([149.5, 127.29480328576642, 134.31310297954988])


@pytest.mark.parametrize("times", [[True], [float("nan")], [float("inf")], [-1], [300], "149"])
def test_bad_crossing_selection(times):
    with pytest.raises(ValueError):
        trace.selected_frames(times)


def test_selection_overflow_never_silently_truncated():
    with pytest.raises(ValueError, match="frame budget"):
        trace.selected_frames(list(range(300)))
