import numpy as np

from visiontrack.eval.mot import MotAccumulator, evaluate_sequence


def _box(cx, cy, w=20, h=40):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def test_perfect_tracking_scores_one():
    acc = MotAccumulator(iou_threshold=0.5)
    for t in range(10):
        gt_ids = np.array([1, 2])
        boxes = np.array([_box(100 + t, 100), _box(300, 200 + t)])
        acc.update(gt_ids, boxes, gt_ids, boxes)  # hypotheses == ground truth
    m = acc.result()
    assert m.mota == 1.0
    assert m.motp == 1.0
    assert m.id_switches == 0
    assert m.false_positives == 0 and m.false_negatives == 0
    assert m.mostly_tracked == 2


def test_false_positive_counted():
    acc = MotAccumulator()
    gt_ids = np.array([1])
    gt_boxes = np.array([_box(100, 100)])
    hyp_ids = np.array([1, 2])
    hyp_boxes = np.array([_box(100, 100), _box(500, 500)])  # extra FP
    acc.update(gt_ids, gt_boxes, hyp_ids, hyp_boxes)
    m = acc.result()
    assert m.false_positives == 1
    assert m.true_positives == 1


def test_miss_counted():
    acc = MotAccumulator()
    gt_ids = np.array([1, 2])
    gt_boxes = np.array([_box(100, 100), _box(300, 300)])
    hyp_ids = np.array([1])
    hyp_boxes = np.array([_box(100, 100)])  # object 2 missed
    acc.update(gt_ids, gt_boxes, hyp_ids, hyp_boxes)
    m = acc.result()
    assert m.false_negatives == 1


def test_identity_switch_detected():
    acc = MotAccumulator(iou_threshold=0.5)
    gt_ids = np.array([1])
    # Frame 0: GT 1 -> hyp 7
    acc.update(gt_ids, np.array([_box(100, 100)]), np.array([7]), np.array([_box(100, 100)]))
    # Frame 1: same GT now covered by a different hypothesis id -> 1 switch
    acc.update(gt_ids, np.array([_box(102, 100)]), np.array([9]), np.array([_box(102, 100)]))
    m = acc.result()
    assert m.id_switches == 1


def test_preserved_correspondence_avoids_switch_on_crossing():
    """When two equally-good hypotheses are available, the previous
    correspondence is preserved, so a valid track does not switch id."""
    acc = MotAccumulator(iou_threshold=0.3)
    # Frame 0: GT1->hypA, GT2->hypB
    acc.update(
        np.array([1, 2]),
        np.array([_box(100, 100), _box(140, 100)]),
        np.array([10, 20]),
        np.array([_box(100, 100), _box(140, 100)]),
    )
    # Frame 1: boxes overlap heavily but ids stay put -> no switch.
    acc.update(
        np.array([1, 2]),
        np.array([_box(118, 100), _box(122, 100)]),
        np.array([10, 20]),
        np.array([_box(118, 100), _box(122, 100)]),
    )
    assert acc.result().id_switches == 0


def test_evaluate_sequence_helper():
    frames_gt = [(np.array([1]), np.array([_box(10 * t, 50)])) for t in range(5)]
    frames_hyp = [(np.array([1]), np.array([_box(10 * t, 50)])) for t in range(5)]
    m = evaluate_sequence(frames_gt, frames_hyp)
    assert m.mota == 1.0
