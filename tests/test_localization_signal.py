"""Authored arithmetic and refusal controls, not evidence of traffic accuracy."""

import json
from dataclasses import replace

import numpy as np
import pytest

from experiments.localization_signal import audit_capture
from visiontrack.detection.proposal_capture import ProposalCapture, ProposalRecord


def record(index, box, *, winner=0, size=3, class_id=0, output=None):
    return ProposalRecord(
        proposal_index=index,
        xyxy=box,
        objectness=0.9,
        class_score=0.9,
        score=0.81,
        class_id=class_id,
        status="returned" if output is not None else "nms_suppressed",
        group_winner_index=winner,
        group_size=size,
        captured_group_size=size,
        output_index=output,
    )


def capture(records, *, total=None, returned=1):
    return ProposalCapture(
        max_proposals=4096,
        total_proposals=len(records) if total is None else total,
        raw_shape=(len(records), 6),
        transposed=False,
        grid_decode_applied=False,
        input_size=32,
        strides=(8, 16, 32),
        scale=1.0,
        conf_threshold=0.25,
        iou_threshold=0.45,
        class_filter=None,
        confidence_filtered_count=0,
        nms_suppressed_count=len(records) - returned,
        nms_kept_count=returned,
        class_filtered_count=0,
        returned_count=returned,
        records=tuple(records),
    )


def group(shift=0):
    # All anchors have y=10 and x=5,7,9, so the median distance is 2.
    return [
        record(0, (shift, 0, shift + 10, 10), output=0),
        record(1, (shift + 2, 0, shift + 12, 10)),
        record(2, (shift + 4, 0, shift + 14, 10)),
    ]


def test_spread_arithmetic_and_compact_receipt():
    result = audit_capture(capture(group()))
    row = result.rows[0]
    assert result.frame_status == "complete"
    assert (row.status, row.group_size, row.same_class_count) == ("supported", 3, 3)
    assert row.spread == pytest.approx(0.2)
    assert row.mixed_class_fraction == 0
    encoded = json.dumps(result.to_dict(), allow_nan=False)
    assert "xyxy" not in encoded and "objectness" not in encoded


def test_coherent_bias_and_real_displacement_are_not_detected_by_spread():
    # References and previous locations are intentionally *not* given to the
    # extractor. Both counterexamples retain the same apparently good feature.
    reference_anchor = (5, 10)
    previous_anchor = (5, 10)
    correct = audit_capture(capture(group())).rows[0]
    displaced = audit_capture(capture(group(100))).rows[0]
    assert correct.spread == displaced.spread == pytest.approx(0.2)
    assert abs((100 + 5) - reference_anchor[0]) == 100
    assert abs((100 + 5) - previous_anchor[0]) == 100


def test_singleton_and_too_few_same_class_members_refuse():
    one = [record(0, (0, 0, 10, 10), size=1, output=0)]
    assert audit_capture(capture(one)).rows[0].status == "singleton_group"
    two = group()[:2]
    two = [replace(r, group_size=2, captured_group_size=2) for r in two]
    assert audit_capture(capture(two)).rows[0].status == "few_same_class"
    mixed = group()
    mixed[2] = replace(mixed[2], class_id=1)
    row = audit_capture(capture(mixed)).rows[0]
    assert (row.status, row.same_class_count, row.mixed_class_fraction) == (
        "few_same_class",
        2,
        pytest.approx(1 / 3),
    )


def test_mixed_class_diagnostic_does_not_enter_spread():
    mixed = group() + [record(3, (100, 0, 110, 10), size=4, class_id=1)]
    mixed = [replace(r, group_size=4, captured_group_size=4) for r in mixed]
    row = audit_capture(capture(mixed)).rows[0]
    assert (row.status, row.group_size, row.same_class_count) == ("supported", 4, 3)
    assert row.mixed_class_fraction == pytest.approx(0.25)
    assert row.spread == pytest.approx(0.2)


def test_adjacent_objects_can_be_indistinguishable_to_group_feature():
    # A suppression group is not proof that members describe one object.
    potentially_distinct_objects = group()
    row = audit_capture(capture(potentially_distinct_objects)).rows[0]
    assert row.status == "supported" and row.spread == pytest.approx(0.2)


def test_truncated_frame_refuses_all_outputs_even_if_first_group_is_complete():
    first = group()
    second = record(3, (20, 0, 30, 10), winner=3, size=1, output=1)
    result = audit_capture(capture(first + [second], total=5, returned=2))
    assert result.frame_status == "frame_truncated"
    assert [row.status for row in result.rows] == ["frame_truncated"] * 2
    assert all(row.spread is None for row in result.rows)


def test_missing_winner_and_incomplete_group_refuse():
    records = group()
    records[0] = replace(records[0], status="class_filtered", output_index=None)
    assert audit_capture(capture(records)).rows[0].status == "missing_winner"
    records = group()
    records[2] = replace(records[2], status="confidence_filtered", group_winner_index=None)
    assert audit_capture(capture(records)).rows[0].status == "incomplete_group"


def test_interleaved_groups_keep_each_winner_and_refusal_separate():
    first = group()
    second = [
        record(3, (20, 0, 30, 10), winner=3, output=1),
        record(4, (22, 0, 32, 10), winner=3),
        record(5, (24, 0, 34, 10), winner=3),
    ]
    second[2] = replace(second[2], group_winner_index=None)
    single = record(6, (40, 0, 50, 10), winner=6, size=1, output=2)
    records = [first[0], second[0], first[1], second[1], first[2], second[2], single]
    rows = audit_capture(capture(records, returned=3)).rows
    assert [row.status for row in rows] == [
        "supported",
        "incomplete_group",
        "singleton_group",
    ]
    assert rows[0].spread == pytest.approx(0.2)
    assert rows[1].spread is None and rows[2].spread is None


@pytest.mark.parametrize("box", [(0, 0, 10, 0), (0, 0, float("nan"), 10), (0, 0, float("inf"), 10)])
def test_invalid_geometry_refuses_without_nonfinite_receipt(box):
    records = group()
    records[2] = replace(records[2], xyxy=box)
    result = audit_capture(capture(records))
    assert result.rows[0].status == "invalid_geometry"
    json.dumps(result.to_dict(), allow_nan=False)


def test_corrupt_capture_indices_fail_closed():
    records = group()
    records[1] = replace(records[1], proposal_index=0)
    with pytest.raises(ValueError, match="proposal index"):
        audit_capture(capture(records))
    records = group()
    records[2] = replace(records[2], output_index=0, status="returned")
    with pytest.raises(ValueError, match="duplicate returned"):
        audit_capture(capture(records))
    records = group()
    records[0] = replace(records[0], output_index=1)
    with pytest.raises(ValueError, match="outside capture count"):
        audit_capture(capture(records))
    with pytest.raises(ValueError, match="inconsistent capture counts"):
        audit_capture(capture(group(), total=2))


def test_real_decoder_capture_is_compatible_and_detections_unchanged():
    from types import SimpleNamespace

    from visiontrack.detection.yolox_onnx import YoloxDetector

    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name="images")]

        def run(self, _names, _feed):
            return [raw]

    raw = np.zeros((3, 6), dtype=np.float64)
    raw[:, :5] = [[12, 12, 10, 10, 0.9], [13, 12, 10, 10, 0.8], [14, 12, 10, 10, 0.7]]
    raw[:, 5] = 1
    detector = YoloxDetector("unused", input_size=32, session=Session())
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    ordinary = detector.detect(image)
    captured, proposal_capture = detector.detect_with_proposals(image, max_proposals=3)
    assert [(d.xyxy.tolist(), d.score, d.class_id) for d in captured] == [
        (d.xyxy.tolist(), d.score, d.class_id) for d in ordinary
    ]
    assert len(captured) == 1
    row = audit_capture(proposal_capture).rows[0]
    assert row.status == "supported" and row.group_size == 3
    assert row.spread == pytest.approx(0.1)
