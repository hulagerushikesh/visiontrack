import numpy as np
import pytest

from visiontrack.core import geometry as g


def test_roundtrip_conversions():
    box = np.array([10.0, 20.0, 50.0, 100.0])  # xyxy
    np.testing.assert_allclose(g.xywh_to_xyxy(g.xyxy_to_xywh(box)), box)
    np.testing.assert_allclose(g.cxcywh_to_xyxy(g.xyxy_to_cxcywh(box)), box)
    np.testing.assert_allclose(g.xyah_to_xyxy(g.xyxy_to_xyah(box)), box)


def test_xyah_semantics():
    # 40 wide, 80 tall -> aspect 0.5, centre (30, 60).
    box = np.array([10.0, 20.0, 50.0, 100.0])
    xyah = g.xyxy_to_xyah(box)
    np.testing.assert_allclose(xyah, [30.0, 60.0, 0.5, 80.0])


def test_batch_shapes_preserved():
    boxes = np.array([[0, 0, 10, 10], [5, 5, 15, 25]], dtype=float)
    out = g.xyxy_to_xyah(boxes)
    assert out.shape == (2, 4)
    single = g.xyxy_to_xyah(boxes[0])
    assert single.shape == (4,)


def test_iou_identical_and_disjoint():
    a = np.array([[0, 0, 10, 10]], dtype=float)
    assert g.iou_matrix(a, a)[0, 0] == pytest.approx(1.0)
    b = np.array([[100, 100, 110, 110]], dtype=float)
    assert g.iou_matrix(a, b)[0, 0] == pytest.approx(0.0)


def test_iou_half_overlap():
    a = np.array([[0, 0, 2, 2]], dtype=float)          # area 4
    b = np.array([[1, 0, 3, 2]], dtype=float)          # area 4, overlap 2
    # intersection 2, union 6 -> 1/3
    assert g.iou_matrix(a, b)[0, 0] == pytest.approx(1 / 3)


def test_iou_empty_inputs():
    a = np.zeros((0, 4))
    b = np.ones((3, 4))
    assert g.iou_matrix(a, b).shape == (0, 3)
    assert g.iou_matrix(b, a).shape == (3, 0)


def test_giou_bounds_and_disjoint_gradient():
    a = np.array([[0, 0, 10, 10]], dtype=float)
    # Disjoint boxes: IoU is 0 but GIoU stays negative and distance-aware.
    far = np.array([[100, 100, 110, 110]], dtype=float)
    near = np.array([[11, 0, 21, 10]], dtype=float)
    giou_far = g.giou_matrix(a, far)[0, 0]
    giou_near = g.giou_matrix(a, near)[0, 0]
    assert -1.0 <= giou_far < giou_near <= 1.0


def test_clip_boxes():
    box = np.array([-5.0, -5.0, 105.0, 205.0])
    clipped = g.clip_boxes(box, 100, 200)
    np.testing.assert_allclose(clipped, [0, 0, 100, 200])
