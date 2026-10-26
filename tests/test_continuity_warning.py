"""Hand-authored observer and input-grid contract tests; no study tracker execution."""
import copy
import math

import numpy as np
import pytest

from experiments.continuity_warning import ContinuityObserver
from experiments.continuity_warning_scene import (
    detector_payload,
    load_recipe,
    scene,
    validate_grid,
)
from visiontrack.detection.base import Detection
from visiontrack.tracking.tracker import TrackObservation


def det(box, score=0.9, class_id=0):
    return Detection(np.array(box, dtype=np.float64), score, class_id)


def obs(frame, track_id, box, score=0.9, class_id=0):
    return TrackObservation(frame, track_id, np.array(box, dtype=np.float64),
                            score, class_id)


def started(previous):
    observer = ContinuityObserver()
    observer.inspect(0, [])
    observer.advance(0, previous)
    return observer


def test_capacity_uses_matching_not_edge_count_or_greedy_first_choice():
    observer = started([obs(0, 1, [0, 0, 10, 10]), obs(0, 2, [0, 0, 4, 10])])
    result = observer.inspect(1, [det([0, 0, 4, 10]), det([5, 0, 10, 10])])
    assert [(e["track_id"], e["row_index"]) for e in result["edges"]] == [
        (1, 0), (1, 1), (2, 0)]
    assert result["two_supported_previous_tracks"] is True
    assert result["warnings"] == []
    assert result["components"][0]["maximum_matching_cardinality"] == 2
    assert result["components"][0]["matching_witness"] == [[2, 0], [1, 1]]


def test_one_shared_row_warns_but_two_duplicate_rows_have_capacity():
    previous = [obs(0, 1, [0, 0, 10, 10]), obs(0, 2, [0, 0, 10, 10])]
    shortage = started(previous).inspect(1, [det([0, 0, 10, 10])])
    assert shortage["warnings"] == [dict(reason="insufficient_distinct_box_support",
        track_ids=[1, 2], row_indices=[0], maximum_matching_cardinality=1,
        deficit=1, matching_witness=[[1, 0]])]
    duplicate = started(previous).inspect(1, [det([0, 0, 10, 10]),
                                               det([0, 0, 10, 10])])
    assert duplicate["warnings"] == []
    assert duplicate["components"][0]["maximum_matching_cardinality"] == 2


def test_class_score_and_exact_iou_boundaries_are_explicit():
    previous = [obs(0, 3, [0, 0, 10, 10])]
    report = started(previous).inspect(1, [det([0, 0, 3, 10], score=0.1),
                                            det([0, 0, 10, 10], score=0.099),
                                            det([0, 0, 10, 10], class_id=1),
                                            det([20, 0, 30, 10])])
    assert report["eligible_count"] == 3
    assert report["edges"] == [dict(track_id=3, row_index=0, iou=0.3)]
    assert report["detections_fingerprint"]
    assert report["warnings"] == []  # one track cannot make a collision component


def test_unsupported_ids_separate_and_startup_is_no_assessment():
    observer = ContinuityObserver()
    first = observer.inspect(0, [det([0, 0, 10, 10])])
    assert first["assessment_opportunity"] is False
    assert first["warnings"] == first["components"] == []
    observer.advance(0, [obs(0, 9, [0, 0, 10, 10])])
    result = observer.inspect(1, [])
    assert result["assessment_opportunity"] is True
    assert result["unsupported_track_ids"] == [9]
    assert result["components"] == result["warnings"] == []


@pytest.mark.parametrize("invalid", [
    lambda d: setattr(d, "xyxy", np.array([0, 0, 0, 1], dtype=np.float64)),
    lambda d: setattr(d, "xyxy", np.array([0, 0, np.nan, 1], dtype=np.float64)),
    lambda d: setattr(d, "xyxy", np.array([0, 0, 1, 1], dtype=np.float32)),
    lambda d: setattr(d, "score", float("nan")),
    lambda d: setattr(d, "class_id", True),
    lambda d: setattr(d, "feature", np.array([1.0])),
])
def test_invalid_detection_fails_explicitly(invalid):
    detection = det([0, 0, 1, 1])
    invalid(detection)
    with pytest.raises(ValueError):
        ContinuityObserver().inspect(0, [detection])


@pytest.mark.parametrize("field,value", [("track_id", True), ("track_id", 0),
                                          ("class_id", 0.5), ("score", -0.1),
                                          ("frame", 3)])
def test_invalid_public_snapshot_fails(field, value):
    public = obs(0, 1, [0, 0, 10, 10])
    setattr(public, field, value)
    observer = ContinuityObserver()
    observer.inspect(0, [])
    with pytest.raises(ValueError):
        observer.advance(0, [public])


def test_duplicate_track_id_and_temporal_errors_fail_then_reset():
    observer = ContinuityObserver()
    with pytest.raises(ValueError, match="nonconsecutive"):
        observer.inspect(1, [])
    observer.inspect(0, [])
    with pytest.raises(ValueError, match="nonconsecutive"):
        observer.inspect(0, [])
    with pytest.raises(ValueError, match="duplicate public"):
        observer.advance(0, [obs(0, 1, [0, 0, 1, 1]), obs(0, 1, [2, 0, 3, 1])])
    observer.advance(0, [])
    with pytest.raises(ValueError, match="nonconsecutive"):
        observer.inspect(2, [])
    observer.reset()
    assert observer.inspect(0, [])["previous_count"] == 0


def test_inputs_copied_and_row_permutation_is_only_an_index_remap():
    public = [obs(0, 2, [0, 0, 10, 10]), obs(0, 1, [20, 0, 30, 10])]
    detections = [det([0, 0, 10, 10]), det([20, 0, 30, 10])]
    original_public = [row.xyxy.copy() for row in public]
    original_detections = [row.xyxy.copy() for row in detections]
    observer = started(public)
    public[0].xyxy[:] = 100
    report = observer.inspect(1, detections)
    assert [(e["track_id"], e["row_index"]) for e in report["edges"]] == [(1, 1), (2, 0)]
    permuted = started([obs(0, 2, original_public[0]), obs(0, 1, original_public[1])])
    other = permuted.inspect(1, detections[::-1])
    assert [(e["track_id"], e["row_index"]) for e in other["edges"]] == [(1, 0), (2, 1)]
    for current, original in zip(detections, original_detections, strict=True):
        np.testing.assert_array_equal(current.xyxy, original)


def test_translation_and_positive_uniform_scale_preserve_topology():
    base_tracks = [[0, 0, 10, 10], [0, 0, 10, 10]]
    base_rows = [[0, 0, 10, 10]]
    def run(scale, shift):
        def transform(box):
            return [x * scale + (shift if i % 2 == 0 else -shift)
                    for i, x in enumerate(box)]
        o = started([obs(0, i + 1, transform(box)) for i, box in enumerate(base_tracks)])
        return o.inspect(1, [det(transform(box)) for box in base_rows])
    first, second = run(1, 0), run(3, 100)
    assert first["warnings"][0]["deficit"] == second["warnings"][0]["deficit"] == 1
    assert [edge["iou"] for edge in first["edges"]] == [edge["iou"] for edge in
                                                         second["edges"]] == [1.0, 1.0]


def test_complete_authored_grid_and_semantic_nonidentifiability():
    spec = load_recipe()
    assert validate_grid(spec) == dict(cells=27, unique_detector_payloads=16,
                                       frames_per_cell=96)
    for duration in (3, 9, 33):
        crossing = scene(spec, duration, "crossing_distinct")
        assert crossing == scene(spec, duration, "unchanged_control")
        for first, second in (("missing_second", "exit_new_entrant"),
                              ("coincident_two", "duplicate_single")):
            a, b = scene(spec, duration, first), scene(spec, duration, second)
            assert detector_payload(a) == detector_payload(b)
            assert [r["truth"] for r in a] != [r["truth"] for r in b]
        union = scene(spec, duration, "shared_union")
        at_36 = union[36]
        assert at_36["detections"] == [dict(xyxy=[160.0, 152.0, 230.0, 208.0],
                                            score=0.9, class_id=0)]
        assert [r["reference_id"] for r in scene(spec, duration,
            "exit_new_entrant")[36 + duration]["truth"]] == [1, 3]
        assert len(scene(spec, duration, "duplicate_single")[36]["truth"]) == 1
    grid = scene(spec, 3, "scale_pulse_pair")
    assert grid[36]["truth"][0]["xyxy"] == [153.0, 54.0, 195.0, 138.0]
    assert copy.deepcopy(grid)[36]["detections"] == grid[36]["detections"]


def test_all_authored_boxes_have_independently_checked_scalar_geometry():
    spec = load_recipe()
    for duration in (3, 9, 33):
        for family in [entry["name"] for entry in spec["families"]]:
            for row in scene(spec, duration, family):
                for item in row["detections"] + row["truth"]:
                    x1, y1, x2, y2 = item["xyxy"]
                    assert all(math.isfinite(value) for value in (x1, y1, x2, y2))
                    assert (x2 - x1) * (y2 - y1) > 0
                assert len({item["reference_id"] for item in row["truth"]}) == len(row["truth"])
    crossing = scene(spec, 3, "crossing_distinct")
    assert crossing[50]["truth"][0]["xyxy"] == crossing[50]["truth"][1]["xyxy"]
    turn = scene(spec, 3, "motion_turn_pair")
    assert turn[38]["detections"][0]["xyxy"] == [157.0, 68.0, 185.0, 124.0]
    coincident = scene(spec, 3, "coincident_two")
    assert coincident[35]["detections"][0] == coincident[35]["detections"][1]
    assert len(coincident[36]["detections"]) == 1
