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


def test_equal_optimum_box_matches_are_counted_as_ambiguous():
    same_box = (0, 0, 10, 10)
    frame = Frame(
        "development", "site-1", "001",
        tuple(DetectionRow("car", same_box, .8, "supported", .1) for _ in range(2)),
        tuple(ReferenceRow("car", same_box) for _ in range(2)),
    )
    rows, counts = _frame_rows(frame)
    assert len(rows) == 2
    assert counts["ambiguous_matches"] == 2
    assert counts["ambiguous_frames"] == 1
    assert all(row.match_ambiguous for row in rows)
    assert {row.key for row in rows} == {
        ("site-1", "001", 0), ("site-1", "001", 1),
    }

    separated = Frame(
        "development", "site-1", "002",
        (DetectionRow("car", same_box, .8, "supported", .1),
         DetectionRow("car", (8, 0, 18, 10), .8, "supported", .1)),
        (ReferenceRow("car", same_box), ReferenceRow("car", (8, 0, 18, 10))),
    )
    separated_rows, separated_counts = _frame_rows(separated)
    assert separated_counts["ambiguous_matches"] == 0
    assert all(not row.match_ambiguous for row in separated_rows)


def test_unambiguous_sensitivity_refits_on_clean_matches_only():
    duplicate = (0, 0, 10, 10)
    frames = []
    for split in ("development", "test"):
        frames.append(_frame(f"{split}-clean", split, shift=1))
        frames.append(Frame(
            split, f"{split}-ties", "1",
            tuple(DetectionRow("car", duplicate, .8, "supported", .1)
                  for _ in range(2)),
            tuple(ReferenceRow("car", duplicate) for _ in range(2)),
        ))
    result = compare(frames, resamples=10)
    sensitivity = result["unambiguous_paired_sensitivity"]
    assert result["counts"]["test"]["ambiguous_matches"] == 2
    assert result["results"]["B2_paired"]["matches"] == 3
    assert sensitivity["development_matches"] == 1
    assert sensitivity["test_matches"] == 1
    assert sensitivity["test_scenes"] == 1
    assert sensitivity["excluded_ambiguous_development_matches"] == 2
    assert sensitivity["excluded_ambiguous_test_matches"] == 2
    assert sensitivity["excluded_unseen_class_test_matches"] == 0
    assert sensitivity["status"] == "descriptive"
    assert sensitivity["B2_area"] == sensitivity["B3_area"] == pytest.approx(.1)


def test_unambiguous_sensitivity_reports_when_no_clean_matches_remain():
    duplicate = (0, 0, 10, 10)
    frames = [Frame(
        split, split, "1",
        tuple(DetectionRow("car", duplicate, .8, "supported", .1)
              for _ in range(2)),
        tuple(ReferenceRow("car", duplicate) for _ in range(2)),
    ) for split in ("development", "test")]
    result = compare(frames, resamples=10)
    sensitivity = result["unambiguous_paired_sensitivity"]
    assert sensitivity["development_matches"] == sensitivity["test_matches"] == 0
    assert sensitivity["status"].startswith("unavailable")
    assert "B3_area" not in sensitivity


def test_preparation_rejects_scene_leak_and_duplicate_frame():
    with pytest.raises(ValueError, match="leaks"):
        prepare([_frame(), _frame(scene="dev-a", split="test", key="2")])
    with pytest.raises(ValueError, match="duplicate"):
        prepare([_frame(), _frame()])


def test_source_image_hashes_refuse_cross_split_duplicate_content():
    image_hash = "a" * 64
    dev = _frame()
    test = _frame("test-a", "test")
    dev = Frame(dev.split, dev.scene, dev.key, dev.detections, dev.references,
                image_hash)
    test = Frame(test.split, test.scene, test.key, test.detections, test.references,
                 image_hash)
    with pytest.raises(ValueError, match="source image leaks"):
        compare([dev, test], resamples=10, require_image_hashes=True)


def test_source_image_hashes_must_be_complete_and_well_formed_when_used():
    dev = _frame()
    test = _frame("test-a", "test")
    hashed = Frame(dev.split, dev.scene, dev.key, dev.detections, dev.references,
                   "a" * 64)
    with pytest.raises(ValueError, match="every frame needs"):
        prepare([dev, test], require_image_hashes=True)
    with pytest.raises(ValueError, match="every frame or none"):
        prepare([hashed, test])
    malformed = Frame(dev.split, dev.scene, dev.key, dev.detections,
                      dev.references, "A" * 64)
    with pytest.raises(ValueError, match="64 lowercase hex"):
        prepare([malformed, Frame(test.split, test.scene, test.key,
                                  test.detections, test.references, "b" * 64)])


def test_source_hashes_allow_distinct_frames_and_report_check_scope():
    dev = _frame()
    test = _frame("test-a", "test")
    frames = [
        Frame(dev.split, dev.scene, dev.key, dev.detections, dev.references,
              "a" * 64),
        Frame(test.split, test.scene, test.key, test.detections, test.references,
              "b" * 64),
    ]
    result = compare(frames, resamples=10, require_image_hashes=True)
    assert result["supplied_image_hash_split_checked"] is True
    assert compare([dev, test], resamples=10)["supplied_image_hash_split_checked"] is False


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


def test_paired_report_keeps_scenes_with_no_detection_or_supported_match():
    missing = _frame("test-no-detections", "test")
    missing = Frame(missing.split, missing.scene, missing.key, (), missing.references)
    unmatched = _frame("test-unmatched", "test", shift=4)
    unsupported = _frame("test-unsupported", "test", spread=None)
    result = compare([
        _frame(), _frame("test-paired", "test"), missing, unmatched, unsupported,
    ], resamples=10)
    scenes = result["paired_scene_coverage"]
    assert len(scenes) == result["counts"]["test"]["scenes"] == 4
    assert scenes["test-no-detections"]["status"] == "no_detections"
    assert scenes["test-no-detections"]["eligible_references"] == 1
    assert scenes["test-unmatched"]["detections"] == 1
    assert scenes["test-unmatched"]["matched"] == 0
    assert scenes["test-unsupported"]["matched"] == 1
    assert scenes["test-unsupported"]["paired_matches"] == 0
    assert scenes["test-paired"]["paired_matches"] == 1
    assert result["test_scenes_without_paired_matches"] == [
        "test-no-detections", "test-unmatched", "test-unsupported",
    ]
    assert set(result["per_scene_paired_delta"]) == {"test-paired"}


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
