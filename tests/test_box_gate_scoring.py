"""Hand-fed scoring fixtures: no new tracker comparisons or held-out inputs."""

import copy
import json
from dataclasses import fields, replace

import numpy as np
import pytest

from experiments import box_gate_scoring as scoring
from experiments.box_gate_scene import BoxGateInputs, generate_inputs
from experiments.traffic_report import CROSSING_METRICS, TRACKING_METRICS, _sha
from visiontrack.eval.mot import evaluate_sequence


@pytest.fixture(autouse=True)
def no_tracker_or_old_scene(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("scorer tests must not run a tracker, old scene or old diagnostics")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)
    monkeypatch.setattr("experiments.traffic_diagnostics._diagnose", forbidden)


@pytest.fixture(scope="module")
def scene():
    return generate_inputs(
        split="development", scenario="gate_dev_solo", seed=2001, condition="control",
    )


def perfect(scene, offset=0):
    return [
        {"frame": frame, "track_id": identity + 10,
         "xyxy": (box + np.array([offset, 0, offset, 0])).tolist(),
         "score": .9, "class_id": 0}
        for frame, boxes in enumerate(scene.ideal_boxes)
        for identity, box in zip(scene.object_ids, boxes, strict=True)
    ]


@pytest.mark.parametrize("scenario,expected_time", [
    ("gate_dev_solo", 149.5),
    ("gate_dev_separated", 299 * 6 / 14),
    ("gate_dev_close", 299 * 8 / 14),
])
@pytest.mark.parametrize("condition", ["control", "perspective_only", "box_error_only", "combined"])
def test_ideal_rows_all_development_paths_and_conditions(scenario, expected_time, condition):
    scene = generate_inputs(split="development", scenario=scenario, seed=2001, condition=condition)
    rows = perfect(scene)
    original = copy.deepcopy(rows)
    result = scoring.score_development(scene, rows)
    assert rows == original
    overall = result["diagnostics"]["overall"]
    total = 300 * len(scene.object_ids)
    assert overall["true_object_frames"] == overall["matched_object_frames"] == total
    assert overall["missed_object_frames"] == overall["false_positive_rows"] == 0
    assert overall["id_switches"] == overall["fragmentations"] == 0
    assert overall["matched_object_frame_fraction"] == 1
    assert overall["matched_track_contact_error"]["bottom_centre"][
        "mean_distance_world"
    ] == pytest.approx(0, abs=1e-12)
    bottom = result["crossing"]["bottom_centre"]
    assert bottom["summary"]["truth_count"] == len(scene.object_ids)
    assert bottom["summary"]["matched_count"] == len(scene.object_ids)
    assert bottom["summary"]["event_error"] == bottom["summary"]["window_count_abs_error"] == 0
    assert bottom["summary"]["matched_time_abs_mean_frames"] == pytest.approx(0, abs=1e-10)
    assert [e["frame_time"] for e in bottom["truth_events"]] == pytest.approx(
        [expected_time] * len(scene.object_ids),
    )
    assert sum(s["true_object_frames"] for s in result["diagnostics"]["by_phase"].values()) == total
    assert sum(
        s["summary"]["true_object_frames"] for s in result["diagnostics"]["by_true_region"]
    ) == total
    if condition in {"box_error_only", "combined"}:
        assert overall["observation_contact_error"]["bottom_centre"]["mean_distance_world"] > 0
    assert result["protocol_id"] == "visiontrack.box-gate-ablation/v1"
    assert bottom["protocol_id"] == "visiontrack.traffic-mechanism/v1"
    assert result["tracker_executed_by_scorer"] is result["heldout_opened_by_scorer"] is False
    assert "producer and variant not established" in result["row_origin"]
    json.dumps(result, allow_nan=False)


def test_endpoint_set_is_exactly_all_37_and_record_hash_is_self_excluding(scene):
    result = scoring.score_development(scene, perfect(scene))
    expected = {
        f"crossing.{anchor}.{name}"
        for anchor in ("bottom_centre", "box_centre") for name in CROSSING_METRICS
    } | {f"tracking.{name}" for name in TRACKING_METRICS} | {
        f"tracking.{source}.{anchor}.{name}"
        for source in ("observation_contact_error", "matched_track_contact_error")
        for anchor in ("bottom_centre", "box_centre")
        for name in ("sample_count", "mean_distance_world")
    }
    assert len(expected) == 37
    assert set(result["endpoints"]) == expected
    assert result["public_rows_sha256"] == _sha(perfect(scene))
    digest = result.pop("scoring_sha256")
    assert digest == _sha(result)
    result["diagnostics"]["samples"].clear()
    assert len(scoring.score_development(scene, perfect(scene))["diagnostics"]["samples"]) == 300


def test_empty_predictions_keep_undefined_timing_and_position(scene):
    result = scoring.score_development(scene, [])
    e = result["endpoints"]
    assert e["tracking.missed_object_frames"] == 300
    assert e["tracking.matched_object_frames"] == e["tracking.false_positive_rows"] == 0
    assert e["crossing.bottom_centre.event_error"] == 1
    assert e["crossing.bottom_centre.window_count_abs_error"] == 1
    assert e["crossing.bottom_centre.recall"] == 0
    for anchor in ("bottom_centre", "box_centre"):
        assert e[f"crossing.{anchor}.matched_time_abs_mean_frames"] is None
        assert e[f"crossing.{anchor}.matched_x_abs_mean_world"] is None
        assert e[f"tracking.matched_track_contact_error.{anchor}.sample_count"] == 0
        assert e[f"tracking.matched_track_contact_error.{anchor}.mean_distance_world"] is None
    assert result["diagnostics"]["mean_matched_box_iou"] is None


def test_crossing_shift_into_next_window_does_not_cancel_count_errors(scene):
    rows = perfect(scene)
    # Y grows by 14/299 world units per frame; affine v falls by
    # 16.25 times that. This exact pixel shift delays the crossing two frames.
    pixel_shift = 16.25 * (14 / 299) * 2
    for row in rows:
        row["xyxy"][1] += pixel_shift
        row["xyxy"][3] += pixel_shift
    result = scoring.score_development(scene, rows)
    bottom = result["crossing"]["bottom_centre"]["summary"]
    assert bottom["matched_count"] == 1
    assert bottom["event_error"] == 0
    assert bottom["matched_time_abs_mean_frames"] == pytest.approx(2)
    assert bottom["matched_wrong_window_events"] == 1
    assert bottom["window_count_abs_error"] == 2  # One missing + one extra window.
    assert result["endpoints"]["tracking.id_switches"] == 0


@pytest.mark.parametrize("gap,switch,misses,fragments,switches", [
    (False, False, 0, 0, 0), (True, False, 1, 1, 0),
    (False, True, 0, 0, 1), (True, True, 1, 1, 1),
])
def test_gap_and_identity_change_at_crossing_are_not_repaired(
    scene, gap, switch, misses, fragments, switches,
):
    rows = [row for row in perfect(scene) if not gap or row["frame"] != 149]
    if switch:
        for row in rows:
            if row["frame"] >= 150:
                row["track_id"] = 42
    result = scoring.score_development(scene, rows)
    e = result["endpoints"]
    assert e["tracking.missed_object_frames"] == misses
    assert e["tracking.fragmentations"] == fragments
    assert e["tracking.id_switches"] == switches
    assert e["crossing.bottom_centre.event_error"] == int(gap or switch)
    assert e["crossing.bottom_centre.window_count_abs_error"] == int(gap or switch)
    canonical = evaluate_sequence(
        [(np.array(scene.object_ids), boxes) for boxes in scene.ideal_boxes],
        [(
            np.array([r["track_id"] for r in rows if r["frame"] == f]),
            np.array([r["xyxy"] for r in rows if r["frame"] == f]).reshape(-1, 4),
        ) for f in range(300)],
    )
    assert canonical.id_switches == switches
    assert canonical.false_negatives == misses
    assert canonical.fragmentations == fragments


def test_false_positive_strata_and_conditional_error_are_not_conflated(scene):
    rows = perfect(scene, offset=6)
    rows += [
        {"frame": f, "track_id": 99, "xyxy": [10., 10., 30., 30.], "score": .9, "class_id": 0}
        for f in range(300)
    ]
    result = scoring.score_development(scene, rows)
    d = result["diagnostics"]
    assert d["overall"]["false_positive_rows"] == 300
    assert d["overall"]["matched_object_frames"] == 300
    assert d["overall"]["observation_contact_error"]["bottom_centre"][
        "mean_distance_world"
    ] == pytest.approx(0, abs=1e-12)
    assert d["overall"]["matched_track_contact_error"]["bottom_centre"][
        "mean_distance_world"
    ] == pytest.approx(.1)
    assert {k: v["false_positive_rows"] for k, v in d["by_phase"].items()} == {
        "outside_pulse_windows": 240, "bottom_pulse_window": 30, "top_pulse_window": 30,
    }
    assert all(r["summary"]["false_positive_rows"] is None for r in d["by_true_region"])
    assert result["endpoints"][
        "crossing.bottom_centre.matched_x_abs_mean_world"
    ] == pytest.approx(.1)


@pytest.mark.parametrize("frame,phase", [(135, "bottom_pulse_window"), (210, "top_pulse_window")])
def test_id_switch_history_not_reset_for_phase_strata(scene, frame, phase):
    rows = perfect(scene)
    for row in rows[frame:]:
        row["track_id"] = 42
    d = scoring.score_development(scene, rows)["diagnostics"]
    assert d["overall"]["id_switches"] == 1
    assert d["by_phase"][phase]["id_switches"] == 1
    assert sum(r["summary"]["id_switches"] for r in d["by_true_region"]) == 1


@pytest.mark.parametrize("name", [f.name for f in fields(BoxGateInputs)])
def test_every_forged_input_field_is_rejected(scene, name):
    value = getattr(scene, name)
    if isinstance(value, np.ndarray):
        changed = value.copy()
        changed.flat[0] += 1
    elif name == "object_ids":
        changed = (True,)  # Python equality to (1,) alone would miss this.
    elif isinstance(value, tuple):
        changed = ()
    elif type(value) is str:
        changed = "forged"
    elif type(value) is int:
        changed = -1
    else:
        changed = False
    with pytest.raises(ValueError):
        scoring.score_development(replace(scene, **{name: changed}), [])


def test_heldout_rejected_before_any_input_generation(scene, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("held-out input generation is not allowed in scorer")

    monkeypatch.setattr(scoring, "generate_inputs", forbidden)
    for value in (replace(scene, split="heldout", scenario="gate_test_solo", seed=4001), object()):
        with pytest.raises(ValueError, match="development BoxGateInputs"):
            scoring.score_development(value, [])


@pytest.mark.parametrize("patch", [
    {"frame": True}, {"frame": 300}, {"frame": 1.5},
    {"track_id": False}, {"track_id": 0}, {"track_id": 2**63},
    {"xyxy": [10., 10., 10., 20.]}, {"xyxy": [0., 0., np.nan, 20.]},
    {"xyxy": [True, 10., 20., 20.]}, {"xyxy": [-1., 0., 20., 20.]},
    {"score": True}, {"score": np.inf}, {"score": -.1}, {"score": 1.1},
    {"class_id": True}, {"class_id": 1}, {"ground_truth_id": 1},
])
def test_invalid_public_rows_fail_instead_of_becoming_metrics(scene, patch):
    row = perfect(scene)[0]
    row.update(patch)
    with pytest.raises(ValueError):
        scoring.score_development(scene, [row])


def test_duplicate_missing_unbounded_or_nonlist_rows_fail(scene):
    row = perfect(scene)[0]
    missing = dict(row)
    missing.pop("score")
    for rows in ([row, row], [missing], [None], [row] * 100_001, (), None):
        with pytest.raises(ValueError):
            scoring.score_development(scene, rows)


def test_baseline_source_checked_before_and_after_scoring(scene, monkeypatch):
    def fail(*args):
        raise ValueError("source drift")

    monkeypatch.setattr(scoring, "_verify_tree", fail)
    with pytest.raises(ValueError, match="source drift"):
        scoring.score_development(scene, [])
    values = iter([{"sha256": "before"}, {"sha256": "after"}])
    monkeypatch.setattr(scoring, "_verify_tree", lambda *args: next(values))
    with pytest.raises(ValueError, match="source changed"):
        scoring.score_development(scene, [])


def test_source_import_origin_guard_is_applied(scene, monkeypatch):
    def fail():
        raise ValueError("wrong import")

    monkeypatch.setattr(scoring, "_check_import_origins", fail)
    with pytest.raises(ValueError, match="wrong import"):
        scoring.score_development(scene, [])
