"""Evaluation-only box IoU without the tracker's small-area denominator floor."""
import numpy as np


def metric_iou(left, right):
    left = np.asarray(left, dtype=np.float64).reshape(-1, 4)
    right = np.asarray(right, dtype=np.float64).reshape(-1, 4)
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("metric boxes must be finite")
    size_left = left[:, 2:] - left[:, :2]
    size_right = right[:, 2:] - right[:, :2]
    area_left = np.prod(size_left, axis=1)
    area_right = np.prod(size_right, axis=1)
    extent = np.maximum(0, np.minimum(left[:, None, 2:], right[None, :, 2:])
                        - np.maximum(left[:, None, :2], right[None, :, :2]))
    intersection = np.prod(extent, axis=2)
    union = area_left[:, None] + area_right[None, :] - intersection
    eps = np.finfo(np.float64).eps
    valid = ((size_left > 0).all(axis=1)[:, None]
             & (size_right > 0).all(axis=1)[None, :]
             & (area_left[:, None] > eps) & (area_right[None, :] > eps) & (union > eps))
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=valid)
