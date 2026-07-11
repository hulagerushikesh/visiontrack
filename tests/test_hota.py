"""Self-consistency tests for the from-scratch HOTA / IDF1 and MOT17 preprocessing.

The heavy cross-check against trackeval lives in test_hota_vs_trackeval.py;
these assert the properties any correct implementation must satisfy.
"""
import numpy as np

from visiontrack.eval.hota import compute_hota, compute_identity
from visiontrack.eval.mot17 import preprocess_frame


def _box(cx, cy, w=20, h=40):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def _perfect_frames(n=10, n_obj=3):
    """Tracker id == gt id, boxes identical -> a flawless sequence."""
    frames = []
    for t in range(n):
        ids = np.arange(1, n_obj + 1)
        boxes = np.array([_box(100 * k + t, 100) for k in range(n_obj)])
        frames.append((ids, boxes, ids.copy(), boxes.copy()))
    return frames


def test_perfect_tracking_scores_one():
    frames = _perfect_frames()
    h = compute_hota(frames)
    ident = compute_identity(frames)
    assert h.hota == 1.0
    assert h.det_a == 1.0 and h.ass_a == 1.0
    assert ident.idf1 == 1.0
    assert ident.idfp == 0 and ident.idfn == 0


def test_identity_switch_halves_idf1():
    """One gt object; tracker uses id A for the first half, id B for the second.
    IDF1 should be ~0.5 (only half the frames keep a consistent identity)."""
    n = 20
    frames = []
    for t in range(n):
        gt_ids = np.array([1])
        box = np.array([_box(100 + t, 100)])
        tr_id = np.array([10 if t < n // 2 else 20])
        frames.append((gt_ids, box, tr_id, box.copy()))
    ident = compute_identity(frames)
    assert ident.idf1 == 0.5
    # HOTA association must drop below perfect too.
    h = compute_hota(frames)
    assert h.det_a == 1.0        # every frame still detected
    assert h.ass_a < 1.0         # but association is broken
    assert h.hota < 1.0


def test_missed_and_false_positive_lower_deta():
    n = 10
    frames = []
    for _t in range(n):
        gt_ids = np.array([1, 2])
        gt_boxes = np.array([_box(100, 100), _box(300, 100)])
        # Track only object 1; add a spurious box far away.
        tr_ids = np.array([1, 99])
        tr_boxes = np.array([_box(100, 100), _box(700, 700)])
        frames.append((gt_ids, gt_boxes, tr_ids, tr_boxes))
    h = compute_hota(frames)
    ident = compute_identity(frames)
    assert 0.0 < h.det_a < 1.0
    assert ident.idfn > 0 and ident.idfp > 0


def test_hota_in_unit_interval_random():
    rng = np.random.default_rng(0)
    frames = []
    for _ in range(15):
        g = rng.integers(1, 5)
        gt_ids = rng.choice(np.arange(1, 8), size=g, replace=False)
        gt_boxes = np.array([_box(*rng.uniform(50, 500, size=2)) for _ in range(g)])
        t = rng.integers(0, 5)
        tr_ids = rng.choice(np.arange(1, 8), size=t, replace=False) if t else np.empty(0, int)
        tr_boxes = (
            np.array([_box(*rng.uniform(50, 500, size=2)) for _ in range(t)])
            if t
            else np.empty((0, 4))
        )
        frames.append((gt_ids, gt_boxes, tr_ids, tr_boxes))
    h = compute_hota(frames)
    assert 0.0 <= h.hota <= 1.0
    assert 0.0 <= h.det_a <= 1.0 and 0.0 <= h.ass_a <= 1.0


def test_mot17_preprocess_removes_tracker_matched_to_distractor():
    # gt: one pedestrian (class 1) and one distractor (class 7, static person).
    gt_boxes = np.array([_box(100, 100), _box(400, 400)])
    gt_ids = np.array([1, 2])
    gt_classes = np.array([1, 7])
    gt_conf = np.array([1.0, 1.0])
    # trackers: one on the pedestrian, one on the distractor.
    tr_boxes = np.array([_box(100, 100), _box(400, 400)])
    tr_ids = np.array([11, 12])

    g_ids, g_box, t_ids, t_box = preprocess_frame(
        gt_boxes, gt_ids, gt_classes, gt_conf, tr_boxes, tr_ids
    )
    # Scoring gt keeps only the pedestrian.
    assert g_ids.tolist() == [1]
    # Tracker matched to the distractor is removed; the one on the pedestrian stays.
    assert t_ids.tolist() == [11]


def test_mot17_preprocess_drops_zero_marked_gt():
    gt_boxes = np.array([_box(100, 100), _box(200, 200)])
    gt_ids = np.array([1, 2])
    gt_classes = np.array([1, 1])
    gt_conf = np.array([1.0, 0.0])  # second pedestrian is zero-marked (ignore)
    tr_boxes = np.array([_box(200, 200)])
    tr_ids = np.array([5])

    g_ids, _, t_ids, _ = preprocess_frame(
        gt_boxes, gt_ids, gt_classes, gt_conf, tr_boxes, tr_ids
    )
    assert g_ids.tolist() == [1]          # zero-marked gt not scored
    assert t_ids.tolist() == []           # tracker matched to it is removed
