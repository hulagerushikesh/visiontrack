"""Hand-checked diagnostics fixtures, all development-only and no tracker runs."""

import copy
import json
from dataclasses import replace

import numpy as np
import pytest

from experiments import traffic_diagnostics as diagnostic
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_scene import generate_scene
from visiontrack.eval.mot import evaluate_sequence


@pytest.fixture(scope="module")
def scene():
    return generate_scene(split="development", scenario="solo", seed=101, condition="control")


def _perfect(scene, offset=0):
    return [
        {
            "frame": frame,
            "track_id": identity + 6,
            "xyxy": (box + np.array([offset, 0, offset, 0])).tolist(),
            "score": 0.9,
            "class_id": 0,
        }
        for frame, boxes in enumerate(scene.ideal_boxes)
        for identity, box in zip(scene.object_ids, boxes, strict=True)
    ]


def test_perfect_matches_different_local_ids_and_contact_bias(scene, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("diagnostics must never run a tracker")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    rows = _perfect(scene)
    before = copy.deepcopy(rows)
    result = diagnostic.diagnose_development(scene, rows)
    assert rows == before
    summary = result["overall"]
    assert result["iou_threshold"] == 0.5
    assert result["frame_count"] == 300
    assert summary["true_object_frames"] == summary["matched_object_frames"] == 300
    assert summary["missed_object_frames"] == summary["false_positive_rows"] == 0
    assert summary["id_switches"] == summary["fragmentations"] == 0
    assert summary["matched_object_frame_fraction"] == result["mean_matched_box_iou"] == 1
    for key in ("observation_contact_error", "matched_track_contact_error"):
        bottom = summary[key]["bottom_centre"]
        centre = summary[key]["box_centre"]
        assert bottom["sample_count"] == centre["sample_count"] == 300
        assert bottom["mean_distance_world"] == pytest.approx(0, abs=1e-12)
        assert centre["mean_distance_world"] == pytest.approx(85 / 16.25)
        assert centre["mean_signed_dy_world"] == pytest.approx(85 / 16.25)
    assert result["failures"] == []
    assert {s["matched_track_id"] for s in result["samples"]} == {7}
    assert result["heldout_tracking_executed"] is False
    json.dumps(result, allow_nan=False)


def test_no_predictions_is_missing_not_zero_position_error(scene):
    result = diagnostic.diagnose_development(scene, [])
    summary = result["overall"]
    assert summary["missed_object_frames"] == 300
    assert summary["matched_object_frames"] == 0
    assert summary["matched_object_frame_fraction"] == 0
    assert result["mean_matched_box_iou"] is None
    assert len(result["failures"]) == 300
    for error in summary["matched_track_contact_error"].values():
        assert error["sample_count"] == 0
        assert all(v is None for k, v in error.items() if k != "sample_count")
    assert summary["observation_contact_error"]["bottom_centre"]["sample_count"] == 300


def test_observation_and_tracked_contact_error_are_independent(scene):
    result = diagnostic.diagnose_development(scene, _perfect(scene, offset=6))
    summary = result["overall"]
    assert summary["matched_object_frames"] == 300
    assert summary["observation_contact_error"]["bottom_centre"][
        "mean_distance_world"
    ] == pytest.approx(0, abs=1e-12)
    tracked = summary["matched_track_contact_error"]["bottom_centre"]
    assert tracked["mean_distance_world"] == pytest.approx(0.1)
    assert tracked["mean_signed_dx_world"] == pytest.approx(0.1)


def test_false_positives_remain_unassigned_to_true_regions(scene):
    rows = _perfect(scene)
    rows += [{"frame": frame, "track_id": 99, "xyxy": [100, 100, 120, 120]} for frame in range(300)]
    result = diagnostic.diagnose_development(scene, rows)
    assert result["overall"]["false_positive_rows"] == 300
    assert result["overall"]["matched_object_frames"] == 300
    assert {name: s["false_positive_rows"] for name, s in result["by_phase"].items()} == {
        "outside_pulse_windows": 240,
        "bottom_pulse_window": 30,
        "top_pulse_window": 30,
    }
    for region in result["by_true_region"]:
        assert region["summary"]["false_positive_rows"] is None
        assert all(p["false_positive_rows"] is None for p in region["by_phase"].values())
    assert sum(f["event_type"] == "false_positive" for f in result["failures"]) == 300


@pytest.mark.parametrize("frame,phase", [(135, "bottom_pulse_window"), (210, "top_pulse_window")])
def test_id_switch_history_retained_across_phase_boundaries(scene, frame, phase):
    rows = _perfect(scene)
    for row in rows[frame:]:
        row["track_id"] = 12
    result = diagnostic.diagnose_development(scene, rows)
    assert result["overall"]["id_switches"] == 1
    assert result["by_phase"][phase]["id_switches"] == 1
    assert result["samples"][frame]["id_switch"] is True
    assert result["samples"][frame]["matched_track_id"] == 12
    assert sum(r["summary"]["id_switches"] for r in result["by_true_region"]) == 1


def test_gap_and_id_change_preserve_canonical_failures(scene):
    rows = [row for row in _perfect(scene) if row["frame"] != 134]
    for row in rows:
        if row["frame"] >= 135:
            row["track_id"] = 12
    result = diagnostic.diagnose_development(scene, rows)
    summary = result["overall"]
    assert summary["matched_object_frames"] == 299
    assert summary["missed_object_frames"] == summary["fragmentations"] == 1
    assert summary["id_switches"] == 1
    assert result["samples"][134]["matched_track_error"] is None
    assert result["samples"][135]["matched_track_id"] == 12
    assert result["by_phase"]["outside_pulse_windows"]["missed_object_frames"] == 1
    assert result["by_phase"]["bottom_pulse_window"]["id_switches"] == 1


@pytest.mark.parametrize("scenario", ["solo", "opposing", "converging"])
@pytest.mark.parametrize("condition", ["control", "perspective_only", "box_error_only", "combined"])
def test_all_regimes_partition_truth_and_keep_observation_error_separate(scenario, condition):
    scene = generate_scene(split="development", scenario=scenario, seed=101, condition=condition)
    result = diagnostic.diagnose_development(scene, _perfect(scene))
    total = 300 * len(scene.object_ids)
    assert result["overall"]["matched_object_frames"] == total
    assert sum(p["true_object_frames"] for p in result["by_phase"].values()) == total
    assert sum(r["summary"]["true_object_frames"] for r in result["by_true_region"]) == total
    for region in result["by_true_region"]:
        assert (
            sum(p["true_object_frames"] for p in region["by_phase"].values())
            == region["summary"]["true_object_frames"]
        )
    if condition in {"box_error_only", "combined"}:
        assert (
            result["by_phase"]["bottom_pulse_window"]["observation_contact_error"]["bottom_centre"][
                "mean_distance_world"
            ]
            > 0
        )
    # Hand-fed ideal outputs stay perfect even if detector observations are perturbed.
    assert result["overall"]["matched_track_contact_error"]["bottom_centre"][
        "mean_distance_world"
    ] == pytest.approx(0, abs=1e-12)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "frame,expected",
    [
        (134, 0),
        (135, 1),
        (164, 1),
        (165, 0),
        (209, 0),
        (210, 2),
        (239, 2),
        (240, 0),
    ],
)
def test_half_open_pulse_windows(frame, expected):
    spec, _ = load_frozen_protocol()
    assert diagnostic._phase(frame, spec) == diagnostic.PHASES[expected]


def test_exact_region_boundaries_and_empty_stratum():
    spec, _ = load_frozen_protocol()
    regions = spec["diagnostics"]["regions_y"]
    for index, bounds in enumerate(regions):
        assert diagnostic._region(bounds[0], regions) == index
        assert diagnostic._region(np.nextafter(bounds[1], -np.inf), regions) == index
    assert diagnostic._region(20, regions) == 2
    for value in (-1, np.nextafter(20, np.inf), float("nan")):
        with pytest.raises(ValueError):
            diagnostic._region(value, regions)
    empty = diagnostic._summary([], None)
    assert empty["matched_object_frame_fraction"] is None
    assert empty["false_positive_rows"] is None
    assert empty["matched_track_contact_error"]["bottom_centre"]["mean_distance_world"] is None


def test_matches_public_evaluator_including_misses_and_false_positives(scene):
    rows = [row for row in _perfect(scene) if row["frame"] % 10]
    rows += [
        {"frame": frame, "track_id": 99, "xyxy": [100, 100, 120, 120]} for frame in range(0, 300, 7)
    ]
    gt = [(np.array(scene.object_ids), boxes) for boxes in scene.ideal_boxes]
    hyp = []
    for frame in range(300):
        current = [r for r in rows if r["frame"] == frame]
        hyp.append(
            (
                np.array([r["track_id"] for r in current]),
                np.array([r["xyxy"] for r in current]).reshape(-1, 4),
            )
        )
    metrics = evaluate_sequence(gt, hyp, iou_threshold=0.5)
    summary = diagnostic.diagnose_development(scene, rows)["overall"]
    assert summary["matched_object_frames"] == metrics.true_positives
    assert summary["missed_object_frames"] == metrics.false_negatives
    assert summary["false_positive_rows"] == metrics.false_positives
    assert summary["fragmentations"] == metrics.fragmentations
    assert summary["id_switches"] == metrics.id_switches


def test_heldout_rejected_before_evaluator(monkeypatch):
    scene = generate_scene(split="heldout", scenario="offcentre", seed=1001, condition="control")
    monkeypatch.setattr("visiontrack.eval.mot.MotAccumulator", lambda **k: pytest.fail("heldout"))
    with pytest.raises(ValueError, match="development"):
        diagnostic.diagnose_development(scene, [])


@pytest.mark.parametrize(
    "row",
    [
        {"frame": -1, "track_id": 7, "xyxy": [1, 1, 2, 2]},
        {"frame": 300, "track_id": 7, "xyxy": [1, 1, 2, 2]},
        {"frame": False, "track_id": 7, "xyxy": [1, 1, 2, 2]},
        {"frame": 0, "track_id": True, "xyxy": [1, 1, 2, 2]},
        {"frame": 0, "track_id": 0, "xyxy": [1, 1, 2, 2]},
        {"frame": 0, "track_id": 2**63, "xyxy": [1, 1, 2, 2]},
        {"frame": 0, "track_id": 7, "xyxy": [1, 1, float("nan"), 2]},
        {"frame": 0, "track_id": 7, "xyxy": [-1, 1, 2, 2]},
        {"frame": 0, "track_id": 7, "xyxy": [1, 1, 1, 2]},
    ],
)
def test_invalid_rows_rejected(scene, row):
    with pytest.raises(ValueError):
        diagnostic.diagnose_development(scene, [row])


def test_duplicate_and_over_capacity_rows_rejected(scene, monkeypatch):
    row = _perfect(scene)[0]
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic.diagnose_development(scene, [row, row])
    monkeypatch.setattr(diagnostic, "MAX_ROWS", 0)
    with pytest.raises(ValueError, match="bounded"):
        diagnostic.diagnose_development(scene, [row])


def test_incomplete_or_nonfinite_scene_rejected(scene):
    with pytest.raises(ValueError, match="incomplete"):
        diagnostic.diagnose_development(replace(scene, ideal_boxes=scene.ideal_boxes[:-1]), [])
    with pytest.raises(ValueError, match="nonfinite"):
        diagnostic.diagnose_development(
            replace(scene, world_contacts=np.full_like(scene.world_contacts, np.nan)), []
        )


def test_integrity_failure_prevents_scoring(scene, monkeypatch):
    def changed():
        raise ValueError("frozen artifact changed")

    monkeypatch.setattr(diagnostic, "load_frozen_protocol", changed)
    with pytest.raises(ValueError, match="artifact changed"):
        diagnostic.diagnose_development(scene, [])
