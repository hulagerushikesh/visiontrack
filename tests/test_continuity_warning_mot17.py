"""Hand-worked triage and replay-boundary checks, without study tracking."""
import numpy as np
import pytest

from experiments.continuity_warning_mot17 import (
    check_frame_input,
    check_frame_output,
    review_windows,
    triage_summary,
)
from visiontrack.detection.base import Detection
from visiontrack.tracking.tracker import TrackObservation


def record(frame, *, warn=False, opportunity=True, two_supported=True):
    return dict(frame=frame, warnings=[{"reason": "test"}] if warn else [],
                assessment_opportunity=opportunity,
                two_supported_previous_tracks=two_supported)


def event(kind, source_frame, gt_id=1):
    return dict(event_type=kind, source_frame=source_frame, frame_index=source_frame - 1,
                gt_id=gt_id, hyp_id=2)


def test_overlapping_adjacent_and_boundary_windows_are_one_review_task():
    assert review_windows([2, 4, 8, 10], 10) == [[2, 6], [8, 10]]
    assert review_windows([], 10) == []
    assert review_windows([10], 10) == [[10, 10]]


@pytest.mark.parametrize("frames", [[2, 2], [0], [11], [4, 2]])
def test_invalid_warning_frame_set_fails_closed(frames):
    with pytest.raises(ValueError, match="invalid warning frames"):
        review_windows(frames, 10)


def test_triage_retains_all_warnings_and_missed_events_without_false_alert_claim():
    warnings = [record(i, warn=i in {1, 3, 8},
                       opportunity=i != 0, two_supported=i not in {0, 4})
                for i in range(10)]
    failures = [event("id_switch", 4), event("id_switch", 7),
                event("id_switch", 10, gt_id=2), event("fragmentation", 10)]
    summary = triage_summary(warnings, failures, 10)
    assert summary["warning_frames"] == [2, 4, 9]
    assert summary["review_windows"] == [[2, 6], [9, 10]]
    assert summary["review_frame_count"] == 7
    assert summary["review_task_count"] == 2
    assert summary["assessment_opportunity_frames"] == 9
    assert summary["two_supported_previous_track_frames"] == 8
    assert summary["events"]["id_switch"]["covered_count"] == 2
    assert summary["events"]["id_switch"]["missed_count"] == 1
    assert summary["events"]["id_switch"]["review_tasks_with_event"] == 2
    assert summary["events"]["fragmentation"]["covered_count"] == 1
    assert summary["independent_physical_labels"] is False
    assert "false_positive" not in summary


def test_no_warning_and_no_event_is_zero_coverage_not_perfect_accuracy():
    summary = triage_summary([record(i, warn=False) for i in range(3)], [], 3)
    assert summary["warning_frame_count"] == summary["review_frame_count"] == 0
    assert summary["events"]["id_switch"]["count"] == 0
    assert summary["events"]["id_switch"]["covered_count"] == 0


def test_reordered_frame_or_event_outside_sequence_is_rejected():
    with pytest.raises(ValueError, match="reordered"):
        triage_summary([record(1), record(0)], [], 2)
    with pytest.raises(ValueError, match="event outside"):
        triage_summary([record(0)], [event("id_switch", 2)], 1)


def test_replay_boundary_requires_exact_cached_inputs_and_public_outputs():
    box = np.array([1., 2., 5., 8.])
    det = Detection(box.copy(), score=0.25, class_id=0)
    obs = TrackObservation(frame=0, track_id=7, xyxy=box.copy(), score=0.25, class_id=0)
    saved = dict(source_frame=1, detections_xyxy=[box.tolist()], detection_scores=[0.25],
                 track_ids=[7], track_xyxy=[box.tolist()])
    check_frame_input(1, [det], saved)
    check_frame_output(1, [obs], saved)
    with pytest.raises(ValueError, match="detection drift"):
        check_frame_input(1, [Detection(box.copy(), score=0.26, class_id=0)], saved)
    with pytest.raises(ValueError, match="public output mismatch"):
        check_frame_output(1, [TrackObservation(frame=0, track_id=8, xyxy=box.copy(),
                                                score=0.25, class_id=0)], saved)
    with pytest.raises(ValueError, match="appearance or class"):
        check_frame_input(1, [Detection(box.copy(), score=0.25, class_id=1)], saved)
