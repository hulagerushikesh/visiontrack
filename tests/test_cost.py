"""Tests for the factored association cost (the ablation surface)."""
import numpy as np
import pytest

from visiontrack.core.geometry import iou_matrix
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.cost import (
    CostWeights,
    appearance_distance,
    build_association_cost,
    motion_distance,
    uncertainty_distance,
)
from visiontrack.tracking.tracker import ByteTracker


def _boxes(*xywh):
    out = []
    for x, y, w, h in xywh:
        out.append([x, y, x + w, y + h])
    return np.array(out, dtype=float)


def test_defaults_reproduce_one_minus_iou():
    """With default weights the cost must equal the v1 `1 - IoU` construction
    (forbidden pairs pushed above max_cost)."""
    tb = _boxes((0, 0, 10, 10), (100, 100, 10, 10))
    db = _boxes((1, 1, 10, 10), (300, 300, 10, 10))
    ious = iou_matrix(tb, db)
    iou_thresh = 0.3

    cost, max_cost = build_association_cost(ious, CostWeights(), iou_thresh)

    expected = 1.0 - ious
    forbidden = ious < iou_thresh
    expected = np.where(forbidden, (1.0 - iou_thresh) + 1.0, expected)
    np.testing.assert_array_equal(cost, expected)
    assert max_cost == pytest.approx(1.0 - iou_thresh)


def test_appearance_distance_bounds():
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[1.0, 0.0], [-1.0, 0.0]])
    d = appearance_distance(a, b)
    # identical -> 0, orthogonal -> 1, opposite -> 2
    assert d[0, 0] == pytest.approx(0.0)
    assert d[1, 0] == pytest.approx(1.0)
    assert d[0, 1] == pytest.approx(2.0)


def test_appearance_normalizes_unnormalized_inputs():
    a = np.array([[3.0, 0.0]])        # magnitude 3
    b = np.array([[10.0, 0.0]])       # magnitude 10, same direction
    assert appearance_distance(a, b)[0, 0] == pytest.approx(0.0)


def test_uncertainty_distance_normalization():
    d2 = np.array([[0.0, 4.7435, 9.487, 20.0]])
    u = uncertainty_distance(d2, gate_thresh=9.4877)
    assert u[0, 0] == pytest.approx(0.0)
    assert u[0, 1] == pytest.approx(0.5, abs=1e-3)
    assert u[0, 2] == pytest.approx(1.0, abs=1e-3)
    assert u[0, 3] == 1.0  # clipped


def test_appearance_term_adds_only_when_weight_positive():
    ious = np.array([[0.9]])
    app = np.array([[1.0]])
    off, _ = build_association_cost(ious, CostWeights(w_app=0.0), 0.3, appearance=app)
    on, _ = build_association_cost(ious, CostWeights(w_app=0.5), 0.3, appearance=app)
    assert off[0, 0] == pytest.approx(1.0 - 0.9)
    assert on[0, 0] == pytest.approx((1.0 - 0.9) + 0.5 * 1.0)


def test_giou_motion_differs_for_disjoint_boxes():
    tb = _boxes((0, 0, 10, 10))
    db = _boxes((30, 0, 10, 10))  # disjoint
    m_iou = motion_distance(tb, db, use_giou=False)
    m_giou = motion_distance(tb, db, use_giou=True)
    assert m_iou[0, 0] == pytest.approx(1.0)   # IoU 0 -> cost 1
    assert m_giou[0, 0] > 1.0                   # GIoU negative -> cost > 1


def test_config_cost_weights_view():
    cfg = TrackerConfig(w_app=0.4, w_unc=0.2, use_giou=True)
    w = cfg.cost_weights()
    assert (w.w_iou, w.w_app, w.w_unc, w.use_giou) == (1.0, 0.4, 0.2, True)
    assert w.appearance_on and w.uncertainty_on


def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        TrackerConfig(w_app=-0.1)


def _linear_det(t, x0=100.0, vx=5.0, w=40.0, h=80.0, score=0.9):
    cx, cy = x0 + vx * t, 100.0
    return Detection(xyxy=[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], score=score, class_id=0)


def test_appearance_hook_inert_without_features():
    """w_app>0 but no embeddings present -> tracker behaves exactly like the
    baseline (the appearance term is skipped)."""
    base_ids, app_ids = [], []
    base = ByteTracker(TrackerConfig())
    withapp = ByteTracker(TrackerConfig(w_app=0.5))
    for t in range(15):
        for o in base.update([_linear_det(t)]):
            base_ids.append(o.track_id)
        for o in withapp.update([_linear_det(t)]):
            app_ids.append(o.track_id)
    assert base_ids == app_ids


def test_uncertainty_weight_runs_end_to_end():
    tracker = ByteTracker(TrackerConfig(w_unc=0.3))
    seen = set()
    for t in range(15):
        for o in tracker.update([_linear_det(t)]):
            seen.add(o.track_id)
    assert len(seen) == 1  # still tracks the single object with one id
