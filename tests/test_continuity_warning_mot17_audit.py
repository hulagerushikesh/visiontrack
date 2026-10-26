"""Reject an altered saved triage calculation without running the real case."""
from copy import deepcopy

import pytest

from experiments.continuity_warning_mot17_audit import check_summary_independently


def test_independent_saved_triage_arithmetic_and_tamper_detection(monkeypatch):
    # A four-frame miniature uses the same arithmetic, with the module's fixed
    # full-sequence frame count replaced only in this authored unit test.
    from experiments import continuity_warning_mot17_audit as audit

    monkeypatch.setattr(audit, "FRAME_COUNT", 4)
    warnings = [dict(source_frame=i + 1, frame=i, warnings=[{}] if i == 1 else [],
                     assessment_opportunity=i > 0,
                     two_supported_previous_tracks=i > 1)
                for i in range(4)]
    failures = [dict(event_type="id_switch", source_frame=1, gt_id=1, hyp_id=2),
                dict(event_type="id_switch", source_frame=3, gt_id=2, hyp_id=3),
                dict(event_type="fragmentation", source_frame=4, gt_id=2, hyp_id=3)]
    summary = dict(warning_frames=[2], warning_frame_count=1, warning_component_count=1,
                   review_windows=[[2, 4]], review_task_count=1,
                   review_frame_count=3, review_frame_fraction=0.75,
                   assessment_opportunity_frames=3, two_supported_previous_track_frames=2,
                   events={
                       "id_switch": dict(count=2, unique_frames=2, covered_count=1,
                                         missed_count=1, covered_unique_frames=1,
                                         review_tasks_with_event=1,
                                         review_tasks_without_event=0,
                                         covered_events=[dict(source_frame=3, gt_id=2, hyp_id=3)]),
                       "fragmentation": dict(count=1, unique_frames=1, covered_count=1,
                                             missed_count=0, covered_unique_frames=1,
                                             review_tasks_with_event=1,
                                             review_tasks_without_event=0,
                                             covered_events=[dict(source_frame=4, gt_id=2,
                                                                  hyp_id=3)]),
                   })
    check_summary_independently(summary, warnings, failures)
    wrong = deepcopy(summary)
    wrong["events"]["id_switch"]["covered_count"] = 2
    with pytest.raises(ValueError, match="event arithmetic mismatch"):
        check_summary_independently(wrong, warnings, failures)
