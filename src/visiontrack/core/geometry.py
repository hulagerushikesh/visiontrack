"""Bounding-box geometry: representations, conversions and overlap metrics.

Three box parametrizations are used throughout the codebase. Keeping the
conversions in one place (and vectorized) avoids the classic tracking bugs
where a corner box is fed into code expecting a centre box.

    xyxy   -> (x1, y1, x2, y2)        two corners
    xywh   -> (x1, y1, w,  h)         top-left corner + size (COCO/detector style)
    cxcywh -> (cx, cy, w,  h)         centre + size
    xyah   -> (cx, cy, a,  h)         centre + aspect-ratio (w/h) + height

``xyah`` is the measurement space of the Kalman filter (see ``core.kalman``);
aspect ratio is tracked instead of width because it is far more stable than
width under scale changes and is what SORT/DeepSORT use.

All functions accept either a single box ``(4,)`` or a batch ``(N, 4)`` and
return matching leading dimensions.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "xyxy_to_xywh",
    "xywh_to_xyxy",
    "xyxy_to_cxcywh",
    "cxcywh_to_xyxy",
    "xyxy_to_xyah",
    "xyah_to_xyxy",
    "box_area",
    "iou_matrix",
    "giou_matrix",
    "clip_boxes",
]

_EPS = 1e-7


def _atleast_2d(boxes: np.ndarray) -> tuple[np.ndarray, bool]:
    arr = np.asarray(boxes, dtype=np.float64)
    if arr.ndim == 1:
        return arr[None, :], True
    return arr, False


def xyxy_to_xywh(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    out = np.empty_like(b)
    out[:, 0] = b[:, 0]
    out[:, 1] = b[:, 1]
    out[:, 2] = b[:, 2] - b[:, 0]
    out[:, 3] = b[:, 3] - b[:, 1]
    return out[0] if squeeze else out


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    out = np.empty_like(b)
    out[:, 0] = b[:, 0]
    out[:, 1] = b[:, 1]
    out[:, 2] = b[:, 0] + b[:, 2]
    out[:, 3] = b[:, 1] + b[:, 3]
    return out[0] if squeeze else out


def xyxy_to_cxcywh(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    out = np.empty_like(b)
    out[:, 0] = (b[:, 0] + b[:, 2]) * 0.5
    out[:, 1] = (b[:, 1] + b[:, 3]) * 0.5
    out[:, 2] = b[:, 2] - b[:, 0]
    out[:, 3] = b[:, 3] - b[:, 1]
    return out[0] if squeeze else out


def cxcywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    out = np.empty_like(b)
    hw = b[:, 2] * 0.5
    hh = b[:, 3] * 0.5
    out[:, 0] = b[:, 0] - hw
    out[:, 1] = b[:, 1] - hh
    out[:, 2] = b[:, 0] + hw
    out[:, 3] = b[:, 1] + hh
    return out[0] if squeeze else out


def xyxy_to_xyah(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    w = b[:, 2] - b[:, 0]
    h = b[:, 3] - b[:, 1]
    out = np.empty_like(b)
    out[:, 0] = (b[:, 0] + b[:, 2]) * 0.5
    out[:, 1] = (b[:, 1] + b[:, 3]) * 0.5
    out[:, 2] = w / np.maximum(h, _EPS)
    out[:, 3] = h
    return out[0] if squeeze else out


def xyah_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    h = b[:, 3]
    w = b[:, 2] * h
    out = np.empty_like(b)
    out[:, 0] = b[:, 0] - w * 0.5
    out[:, 1] = b[:, 1] - h * 0.5
    out[:, 2] = b[:, 0] + w * 0.5
    out[:, 3] = b[:, 1] + h * 0.5
    return out[0] if squeeze else out


def box_area(boxes: np.ndarray) -> np.ndarray:
    b, squeeze = _atleast_2d(boxes)
    area = np.clip(b[:, 2] - b[:, 0], 0, None) * np.clip(b[:, 3] - b[:, 1], 0, None)
    return area[0] if squeeze else area


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between two sets of ``xyxy`` boxes.

    Returns an ``(N, M)`` matrix where entry ``(i, j)`` is IoU of ``a[i]``
    with ``b[j]``. Empty inputs yield a correctly-shaped empty/zero matrix.
    """
    a = np.asarray(a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 4)
    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)

    area_a = box_area(a)[:, None]
    area_b = box_area(b)[None, :]

    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(rb - lt, 0, None)
    inter = wh[..., 0] * wh[..., 1]

    union = area_a + area_b - inter
    return inter / np.maximum(union, _EPS)


def giou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise Generalized IoU (range ``[-1, 1]``).

    GIoU is a distance-aware overlap: unlike IoU it keeps a useful gradient
    even for disjoint boxes, which makes it a better association cost when
    detections and predictions do not yet overlap.
    """
    a = np.asarray(a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 4)
    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)

    area_a = box_area(a)[:, None]
    area_b = box_area(b)[None, :]

    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(rb - lt, 0, None)
    inter = wh[..., 0] * wh[..., 1]
    union = area_a + area_b - inter
    iou = inter / np.maximum(union, _EPS)

    enc_lt = np.minimum(a[:, None, :2], b[None, :, :2])
    enc_rb = np.maximum(a[:, None, 2:], b[None, :, 2:])
    enc_wh = np.clip(enc_rb - enc_lt, 0, None)
    enc_area = enc_wh[..., 0] * enc_wh[..., 1]

    return iou - (enc_area - union) / np.maximum(enc_area, _EPS)


def clip_boxes(boxes: np.ndarray, width: float, height: float) -> np.ndarray:
    """Clip ``xyxy`` boxes to the image bounds ``[0, width] x [0, height]``."""
    b, squeeze = _atleast_2d(boxes)
    out = b.copy()
    out[:, 0::2] = np.clip(out[:, 0::2], 0, width)
    out[:, 1::2] = np.clip(out[:, 1::2], 0, height)
    return out[0] if squeeze else out
