"""Authored arithmetic and leakage controls, without any publisher dataset."""

import math

import pytest

from experiments.localization_outcome import (
    DetectionRow,
    Frame,
    ReferenceRow,
    _area,
    _frame_rows,
    _predict,
    compare,
    prepare,
)


def _frame(scene="dev-a", split="development", key="1", *, shift=0.0,
           spread=0.1, class_id="car"):
    return Frame(
        split, scene, key,
        (DetectionRow(class_id, (shift, 0, 10 + shift, 10), .8,
                      "supported" if spread is not None else "singleton_group", spread),),
        (ReferenceRow(class_id, (0, 0, 10, 10)),),
    )


def test_matching_target_and_unmatched_inventory():
    frame = Frame(
        "development", "site-1", "001",
        (DetectionRow("car", (1, 0, 11, 10), .7, "supported", .1),
         DetectionRow("bus", (40, 0, 50, 10), .6, "singleton_group", None)),
        (ReferenceRow("car", (0, 0, 10, 10)),
         ReferenceRow("car", (70, 0, 80, 10)),
         ReferenceRow("bus", (40, 0, 50, 10), False)),
    )
    rows, counts = _frame_rows(frame)
    assert len(rows) == 1
    assert rows[0].pixel_error == 1.0
    assert rows[0].error == .1
    assert rows[0].iou_error == pytest.approx(2 / 11)
    assert counts["unmatched_detections"] == 1
    assert counts["missed_references"] == 1
    assert counts["excluded_references"] == 1


def test_same_class_and_iou_gate():
    wrong_class = _frame(class_id="bus")
    wrong_class = Frame(wrong_class.split, wrong_class.scene, wrong_class.key,
                        wrong_class.detections,
                        (ReferenceRow("car", (0, 0, 10, 10)),))
    assert _frame_rows(wrong_class)[1]["matched"] == 0
    assert _frame_rows(_frame(shift=4))[1]["matched"] == 0
    assert _frame_rows(_frame(shift=3))[1]["matched"] == 1


def test_preparation_rejects_scene_leak_and_duplicate_frame():
    with pytest.raises(ValueError, match="leaks"):
        prepare([_frame(), _frame(scene="dev-a", split="test", key="2")])
    with pytest.raises(ValueError, match="duplicate"):
        prepare([_frame(), _frame()])


def test_invalid_feature_and_geometry_refused():
    with pytest.raises(ValueError, match="supported spread"):
        _frame_rows(_frame(spread=math.nan))
    with pytest.raises(ValueError, match="unsupported spread"):
        _frame_rows(Frame("test", "s", "f",
                          (DetectionRow("car", (0, 0, 10, 10), .7,
                                        "singleton_group", .1),), ()))
    with pytest.raises(ValueError, match="positive"):
        _frame_rows(Frame("test", "s", "f",
                          (DetectionRow("car", (0, 0, 0, 10), .7,
                                        "supported", .1),), ()))


def test_risk_ties_are_broken_by_input_key_not_error():
    rows, _ = _frame_rows(_frame(shift=1))
    a = rows[0]
    b = type(a)(a.scene, (a.scene, "2", 0), a.class_id, a.width,
                a.height, a.score, a.spread, .9, 9, a.iou_error)
    area, points = _area([b, a], [0.2, 0.2])
    assert points["50%"] == .1
    assert area == pytest.approx((.1 + .5) / 2)


def test_constant_spread_does_not_create_apparent_gain():
    frames = []
    for i in range(8):
        frames.append(_frame(f"dev-{i}", "development", shift=i % 4, spread=.2))
        frames.append(_frame(f"test-{i}", "test", shift=(i + 1) % 4, spread=.2))
    result = compare(frames, resamples=100, seed=7)
    assert result["counts"]["test"]["scenes"] == 8
    assert result["paired_coverage_of_all_test_detections"] == 1.0
    assert result["results"]["B2_paired"]["area"] == pytest.approx(
        result["results"]["B3_paired"]["area"])
    assert result["paired_scene_bootstrap_95pct"] is None  # fewer than 50 matches


def test_bootstrap_uses_scene_units_and_is_reproducible():
    frames = []
    for i in range(8):
        for j in range(7):
            frames.append(_frame(f"dev-{i}", "development", str(j),
                                 shift=(i + j) % 4, spread=(i + j) / 20))
            frames.append(_frame(f"test-{i}", "test", str(j),
                                 shift=(i + 2 * j) % 4, spread=(i + j) / 20))
    a = compare(frames, resamples=100, seed=11)
    b = compare(frames, resamples=100, seed=11)
    assert a == b
    assert len(a["paired_scene_bootstrap_95pct"]) == 2
    assert len(a["per_scene_paired_delta"]) == 8
    assert a["independent_truth_verified_by_this_code"] is False


def test_unpenalized_intercept_predicts_training_mean_when_features_constant():
    rows, _ = _frame_rows(_frame(shift=1))
    another, _ = _frame_rows(_frame(key="2", shift=2))
    expected = math.expm1((math.log1p(.1) + math.log1p(.2)) / 2)
    assert _predict(rows + another, rows, 3)[0] == pytest.approx(expected)


def test_test_reference_error_never_enters_prediction():
    train, _ = _frame_rows(_frame(shift=1))
    test, _ = _frame_rows(_frame(scene="test", split="test", shift=2))
    row = test[0]
    changed_truth = type(row)(row.scene, row.key, row.class_id, row.width,
                              row.height, row.score, row.spread, 100.0,
                              1000.0, row.iou_error)
    assert _predict(train, test, 3) == _predict(train, [changed_truth], 3)


def test_declared_strata_use_development_height_cuts_and_scene_units():
    frames = []
    for scene in range(8):
        for index in range(14):
            for split in ("development", "test"):
                height = (8, 10, 12, 14)[index % 4]
                shift = (scene + index + (split == "test")) % 4
                frames.append(Frame(
                    split, f"{split}-{scene}", str(index),
                    (DetectionRow("car", (shift, 0, 10 + shift, height), .8,
                                  "supported", index / 100, 3 if index % 2 else 8),),
                    (ReferenceRow("car", (0, 0, 10, height), True,
                                  "clear" if index % 2 else "partial"),),
                ))
    result = compare(frames, resamples=50, seed=17)
    assert result["predicted_height_development_quartile_cuts"] == [8, 10, 12]
    assert set(result["paired_strata"]) == {
        "class", "predicted_height_quartile", "visibility", "group_size"}
    assert result["paired_strata"]["visibility"]["clear"]["matches"] == 56
    assert result["paired_strata"]["visibility"]["partial"]["scenes"] == 8
    assert result["paired_strata"]["group_size"]["3"]["status"] == "scene-clustered"
    assert len(result["paired_strata"]["group_size"]["8+"]["scene_bootstrap_95pct"]) == 2
    assert sum(item["matches"] for item in result["paired_strata"]["group_size"].values()) == 112


def test_invalid_group_size_and_visibility_are_refused():
    frame = _frame()
    with pytest.raises(ValueError, match="group members"):
        _frame_rows(Frame(frame.split, frame.scene, frame.key,
                          (DetectionRow("car", (0, 0, 10, 10), .8, "supported", .1, 2),),
                          frame.references))
    with pytest.raises(ValueError, match="visibility"):
        _frame_rows(Frame(frame.split, frame.scene, frame.key, frame.detections,
                          (ReferenceRow("car", (0, 0, 10, 10), True, ""),)))
