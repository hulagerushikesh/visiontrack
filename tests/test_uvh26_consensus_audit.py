"""Check correspondence semantics without downloading publisher data."""

from experiments.uvh26_consensus_audit import _pairs


def _box(x, category):
    return {"bbox": [x, 0.0, 10.0, 10.0], "category_id": category}


def test_consensus_matching_is_class_blind_and_rejects_distant_boxes():
    mv = [_box(0.0, 1), _box(30.0, 5)]
    st = [_box(30.0, 6), _box(0.0, 2), _box(60.0, 1)]
    assert _pairs(mv, st) == [(0, 1, 1.0), (1, 0, 1.0)]


def test_consensus_matching_uses_iou_threshold_and_empty_input():
    assert _pairs([_box(0.0, 1)], [_box(4.0, 1)]) == []
    assert _pairs([], [_box(0.0, 1)]) == []
