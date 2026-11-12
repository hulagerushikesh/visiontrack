"""Check the development screen's intentionally non-unique overlap semantics."""

from types import SimpleNamespace

from experiments.lta_detector_agreement import _frame_agreement


def test_any_box_overlap_is_not_misreported_as_unique_matching():
    boxes = [
        {"category": "car", "bbox_xywh": [0, 0, 20, 30]},
        {"category": "car", "bbox_xywh": [0, 0, 20, 30]},
        {"category": "truck", "bbox_xywh": [0, 0, 20, 30]},
    ]
    one_car = [SimpleNamespace(class_id=2, xyxy=(0, 0, 20, 30))]
    result = _frame_agreement(boxes, one_car, {0}, 0.2)
    assert result["all"]["supplied_boxes"] == 3
    assert result["all"]["returned_detections"] == 1
    assert result["all"]["boxes_with_overlap"] == 2
    assert result["all"]["boxes_with_supported_overlap"] == 2
    assert result["class:truck"]["boxes_with_overlap"] == 0
    assert result["height:under_10px"]["supplied_boxes"] == 3
    assert result["all"]["images_without_supported_overlap"] == 0
