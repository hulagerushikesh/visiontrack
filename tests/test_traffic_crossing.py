"""Hand-checked v1 event fixtures, not tracker or held-out performance results."""

from __future__ import annotations

import json
from itertools import permutations

import numpy as np
import pytest

from experiments import traffic_crossing
from experiments.traffic_crossing import (
    MAX_PREDICTED_EVENTS,
    MAX_SAMPLES,
    MAX_TRUTH_EVENTS,
    AnchorSample,
    CrossingEvent,
    extract_crossings,
    score_crossings,
)


def event(identifier=1, time=30.0, x=0.0, direction=1):
    return CrossingEvent(identifier, direction, time, x)


def path(ys, *, xs=None, frames=None, identifier=1):
    xs = [0.0] * len(ys) if xs is None else xs
    frames = list(range(len(ys))) if frames is None else frames
    return [AnchorSample(f, identifier, x, y) for f, x, y in zip(frames, xs, ys, strict=True)]


def matched_ids(result):
    return [(m["truth"]["track_id"], m["predicted"]["track_id"]) for m in result["matches"]]


@pytest.mark.parametrize(
    "ys, expected",
    [
        ([9, 11], [(1, 0.5)]),
        ([11, 9], [(-1, 0.5)]),
        ([9, 10, 10, 11], [(1, 1.0)]),
        ([11, 10, 10, 9], [(-1, 1.0)]),
        ([10, 10, 11], []),
        ([10, 9], []),
        ([9, 9], []),
        ([9, 11, 9, 11, 9], [(1, 0.5), (-1, 1.5)]),
        ([10, 11, 9], [(-1, 1.5)]),
    ],
)
def test_arrival_direction_dwelling_start_on_line_and_first_per_direction(ys, expected):
    events = extract_crossings(path(ys))
    assert [(e.direction, e.frame_time) for e in events] == expected


def test_interpolation_is_unrounded_and_x_is_interpolated_not_taken_from_endpoint():
    result = extract_crossings(path([9, 12], xs=[-2, 4], frames=[29, 30]))
    assert result == (CrossingEvent(1, 1, 29 + 1 / 3, 0.0),)


@pytest.mark.parametrize(
    "x, count", [(-6, 1), (np.nextafter(-6.0, -np.inf), 0), (np.nextafter(6.0, -np.inf), 1), (6, 0)]
)
def test_crossing_segment_is_half_open_without_epsilon(x, count):
    assert len(extract_crossings(path([9, 11], xs=[x, x]))) == count


def test_outside_roi_samples_may_interpolate_to_valid_crossing_and_are_not_clamped():
    assert extract_crossings(path([9, 11], xs=[-20, 20])) == (event(time=0.5),)
    assert extract_crossings(path([9, 11], xs=[20, 20])) == ()


def test_rejected_outside_crossing_does_not_suppress_first_later_valid_arrival():
    events = extract_crossings(path([9, 11, 9, 11], xs=[20, 20, 0, 0]))
    assert events == (event(time=2.5),)


def test_missing_frames_never_form_interpolated_crossings():
    assert extract_crossings(path([9, 11], frames=[0, 2])) == ()
    assert extract_crossings(path([9, 11, 9], frames=[0, 2, 3])) == (event(time=2.5, direction=-1),)


def test_fragmented_ids_do_not_create_a_crossing_from_two_different_tracks():
    rows = [AnchorSample(29, 7, 0, 9), AnchorSample(30, 12, 0, 11)]
    result = score_crossings([event(time=29.5)], extract_crossings(rows))
    assert result["summary"]["missed_events"] == 1
    assert result["summary"]["predicted_count"] == 0


def test_unsorted_interleaved_samples_have_deterministic_events():
    rows = path([9, 11], identifier=7) + path([11, 9], identifier=12)
    expected = (event(7, 0.5), event(12, 0.5, direction=-1))
    for order in permutations(rows):
        assert extract_crossings(order) == expected


def test_perfect_matching_does_not_require_truth_and_prediction_id_equality():
    result = score_crossings([event(1)], [event(99)])
    assert matched_ids(result) == [(1, 99)]
    summary = result["summary"]
    assert summary["event_error"] == summary["window_count_abs_error"] == 0
    assert summary["matched_count"] == summary["truth_count"] == 1
    assert summary["recall"] == 1
    assert summary["matched_time_abs_mean_frames"] == summary["matched_x_abs_mean_world"] == 0


def test_duplicate_prediction_from_different_id_is_an_extra_not_silently_deduplicated():
    result = score_crossings([event()], [event(10), event(20)])
    assert matched_ids(result) == [(1, 10)]
    assert result["unmatched_predictions"] == [
        {"track_id": 20, "direction": 1, "frame_time": 30.0, "x": 0.0}
    ]
    assert result["summary"]["extra_events"] == result["summary"]["event_error"] == 1


def test_empty_predictions_have_misses_and_undefined_localization_not_zero():
    summary = score_crossings([event()], [])["summary"]
    assert summary["event_error"] == summary["missed_events"] == 1
    assert summary["recall"] == 0
    assert summary["matched_time_abs_mean_frames"] is None
    assert summary["matched_x_abs_mean_world"] is None


@pytest.mark.parametrize("predictions", [[], [event()]])
def test_no_truth_recall_is_undefined_not_perfect(predictions):
    result = score_crossings([], predictions)
    assert result["summary"]["recall"] is None
    assert result["summary"]["matched_time_abs_mean_frames"] is None
    assert result["summary"]["event_error"] == len(predictions)
    json.dumps(result, allow_nan=False)


def test_opposite_direction_miss_and_extra_cannot_cancel_in_total():
    result = score_crossings([event()], [event(direction=-1)])
    summary = result["summary"]
    assert summary["missed_events"] == summary["extra_events"] == 1
    assert summary["event_error"] == summary["window_count_abs_error"] == 2
    assert summary["matched_count"] == 0


@pytest.mark.parametrize("boundary", range(30, 300, 30))
def test_exact_window_boundary_belongs_to_later_window_and_nearby_match_keeps_window_error(
    boundary,
):
    prior = np.nextafter(float(boundary), -np.inf)
    result = score_crossings([event(time=prior)], [event(10, time=boundary)])
    match = result["matches"][0]
    assert match["truth_window"] == boundary // 30 - 1
    assert match["predicted_window"] == boundary // 30
    assert result["summary"]["event_error"] == 0
    assert result["summary"]["matched_wrong_window_events"] == 1
    assert result["summary"]["window_count_abs_error"] == 2


@pytest.mark.parametrize(
    "time, x, matched",
    [
        (60, 1, 1),
        (np.nextafter(60.0, np.inf), 1, 0),
        (60, np.nextafter(1.0, np.inf), 0),
        (0, -1, 1),
        (30, 2, 0),
    ],
)
def test_matching_tolerances_are_inclusive_with_no_epsilon(time, x, matched):
    summary = score_crossings([event()], [event(10, time=time, x=x)])["summary"]
    assert summary["matched_count"] == matched
    assert summary["event_error"] == 2 * (1 - matched)


def test_maximum_cardinality_is_more_important_than_closest_greedy_match():
    truth = [event(1, 20), event(2, 40)]
    predicted = [event(10, 25), event(20, 0)]
    assert matched_ids(score_crossings(truth, predicted)) == [(1, 20), (2, 10)]


def test_total_time_error_has_priority_over_x_error_or_lexicographic_ids():
    truth = [event(1, 20, 0), event(2, 22, 1)]
    predicted = [event(10, 21, 1), event(20, 23, 0)]
    result = score_crossings(truth, predicted)
    assert matched_ids(result) == [(1, 10), (2, 20)]
    assert result["summary"]["matched_time_abs_mean_frames"] == 1
    assert result["summary"]["matched_x_abs_mean_world"] == 1


def test_total_x_error_has_priority_over_lexicographic_ids_when_time_ties():
    truth = [event(1, 20, 0), event(2, 20, 1)]
    predicted = [event(10, 21, 1), event(20, 21, 0)]
    assert matched_ids(score_crossings(truth, predicted)) == [(1, 20), (2, 10)]


def test_exact_ties_choose_lexicographic_id_pairs_independent_of_input_order():
    truth = [event(1, 20), event(2, 20)]
    predicted = [event(10, 21), event(20, 21)]
    results = [score_crossings(t, p) for t in permutations(truth) for p in permutations(predicted)]
    assert all(result == results[0] for result in results)
    assert matched_ids(results[0]) == [(1, 10), (2, 20)]


def test_one_prediction_cannot_match_two_truth_events():
    result = score_crossings([event(1), event(2)], [event(10)])
    assert result["summary"]["matched_count"] == 1
    assert result["summary"]["missed_events"] == 1
    assert matched_ids(result) == [(1, 10)]


def test_same_local_id_can_have_one_event_in_each_direction():
    events = [event(7, 30), event(7, 50, direction=-1)]
    result = score_crossings(events, events)
    assert result["summary"]["matched_count"] == 2
    assert result["summary"]["event_error"] == 0


def test_swapped_windows_can_preserve_aggregate_counts_but_not_event_timing():
    truth = [event(1, 29.5, 0), event(2, 30.5, 3)]
    predicted = [event(10, 30.5, 0), event(20, 29.5, 3)]
    result = score_crossings(truth, predicted)
    assert matched_ids(result) == [(1, 10), (2, 20)]
    assert result["summary"]["event_error"] == 0
    assert result["summary"]["window_count_abs_error"] == 0
    assert result["summary"]["matched_wrong_window_events"] == 2
    assert result["summary"]["matched_time_abs_mean_frames"] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frame": -1},
        {"frame": 1.5},
        {"frame": True},
        {"track_id": -1},
        {"track_id": False},
        {"x": np.nan},
        {"y": np.inf},
        {"x": True},
        {"x": "0"},
    ],
)
def test_invalid_samples_are_rejected(kwargs):
    with pytest.raises(ValueError):
        AnchorSample(**(dict(frame=0, track_id=1, x=0, y=9) | kwargs))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"direction": 0},
        {"direction": True},
        {"direction": 1.0},
        {"frame_time": np.nan},
        {"x": np.inf},
        {"track_id": 1.5},
    ],
)
def test_invalid_event_records_are_rejected(kwargs):
    with pytest.raises(ValueError):
        CrossingEvent(**(dict(track_id=1, direction=1, frame_time=30, x=0) | kwargs))


@pytest.mark.parametrize("kwargs", [{"frame_time": -1}, {"frame_time": 300}, {"x": -7}, {"x": 6}])
def test_out_of_domain_events_are_rejected_not_dropped(kwargs):
    bad = CrossingEvent(**(dict(track_id=1, direction=1, frame_time=30, x=0) | kwargs))
    for truth, predicted in (([bad], []), ([], [bad])):
        with pytest.raises(ValueError, match="outside"):
            score_crossings(truth, predicted)


def test_duplicate_frame_id_and_outside_frame_are_rejected():
    with pytest.raises(ValueError, match="duplicate sample"):
        extract_crossings([AnchorSample(0, 1, 0, 9)] * 2)
    with pytest.raises(ValueError, match="outside"):
        extract_crossings([AnchorSample(300, 1, 0, 9)])


def test_duplicate_id_direction_events_require_extraction_before_scoring():
    for truth, predicted in (([event(), event()], []), ([], [event(), event()])):
        with pytest.raises(ValueError, match="duplicate event"):
            score_crossings(truth, predicted)


def test_finite_samples_with_overflowing_interpolation_fail_instead_of_fabricating_event():
    for rows in (path([-1e308, 1e308]), path([9, 11], xs=[-1e308, 1e308])):
        with pytest.raises(ValueError, match="nonfinite crossing"):
            extract_crossings(rows)


def test_capacity_limits_fail_closed_instead_of_truncating_inputs():
    with pytest.raises(ValueError, match="capacity"):
        extract_crossings(AnchorSample(0, i, 0, 9) for i in range(MAX_SAMPLES + 1))
    with pytest.raises(ValueError, match="capacity"):
        score_crossings([event(i) for i in range(MAX_TRUTH_EVENTS + 1)], [])
    with pytest.raises(ValueError, match="capacity"):
        score_crossings([], [event(i) for i in range(MAX_PREDICTED_EVENTS + 1)])


def test_wrong_record_types_fail_clearly():
    with pytest.raises(ValueError, match="AnchorSample"):
        extract_crossings([{}])
    with pytest.raises(ValueError, match="CrossingEvent"):
        score_crossings([{}], [])


def test_frozen_protocol_failure_stops_both_entry_points(monkeypatch):
    def changed():
        raise ValueError("frozen artifact changed")

    monkeypatch.setattr(traffic_crossing, "load_frozen_protocol", changed)
    for operation in (lambda: extract_crossings([]), lambda: score_crossings([], [])):
        with pytest.raises(ValueError, match="frozen artifact changed"):
            operation()


def test_scorer_runs_no_tracker_rng_or_scene_generator(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("scorer fixture checks cannot execute tracking or generate study inputs")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)
    monkeypatch.setattr(np.random, "PCG64", forbidden)
    assert (
        score_crossings([event()], extract_crossings(path([9, 11])))["summary"]["matched_count"]
        == 1
    )


def test_result_is_json_safe_detached_and_contains_frozen_provenance():
    result = score_crossings([event()], [event(10)])
    assert result["protocol_id"] == "visiontrack.traffic-mechanism/v1"
    assert len(result["protocol_hashes"]) == 2
    assert result["rules"]["max_match_time_error_frames"] == 30
    json.dumps(result, allow_nan=False)
    result["rules"]["world_y"] = -999
    assert score_crossings([], [])["rules"]["world_y"] == 10
