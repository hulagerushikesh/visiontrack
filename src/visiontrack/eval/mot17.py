"""MOT17 evaluation runner: preprocessing + tracker + all three metric families.

MOT17 uses a dataset-specific preprocessing policy as well as metric formulas.
Predictions assigned to distractor classes 2/7/8/12 are removed; zero-marked
pedestrian GT is excluded from scoring but does not itself remove predictions.
V2 thresholds assignment edges first. The explicit legacy policy retains the
old broader-removal behavior for historical reproduction, not new comparisons.
Same-input metric parity and preprocessing parity are distinct checks.

This module:

1. runs the from-scratch :class:`ByteTracker` over a sequence's cached public
   detections (streaming, one frame at a time),
2. applies MOT17 preprocessing per frame,
3. feeds the cleaned per-frame ``(gt, tracker)`` pairs to CLEAR-MOT, IDF1 and
   HOTA, aggregating correctly across sequences via per-sequence id offsets.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.assignment import linear_assignment
from ..core.geometry import iou_matrix
from ..detection.mot_loader import PEDESTRIAN_CLASS
from ..tracking.config import TrackerConfig
from ..tracking.tracker import ByteTracker
from .geometry import metric_iou
from .hota import FramePair, compute_hota, compute_identity
from .mot import MotAccumulator

__all__ = [
    "preprocess_frame",
    "run_sequence",
    "evaluate_sequences",
    "evaluate_frames",
    "SequenceReport",
]

# Large per-sequence id offset so pooled sequences never share gt/tracker ids
# (pooling with unique ids == trackeval's count-level combination across seqs).
_SEQ_ID_OFFSET = 10_000_000
MOT17_PREPROCESSING = "visiontrack.mot17-preprocessing/v2"
LEGACY_MOT17_PREPROCESSING = "visiontrack.mot17-preprocessing/v1"


def preprocess_frame(
    gt_boxes: np.ndarray,
    gt_ids: np.ndarray,
    gt_classes: np.ndarray,
    gt_conf: np.ndarray,
    tr_boxes: np.ndarray,
    tr_ids: np.ndarray,
    iou_threshold: float = 0.5,
    *,
    policy: str = MOT17_PREPROCESSING,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Apply an explicit MOT17 preprocessing policy, returning scored pairs.

    Default v2 follows pinned TrackEval MOT17 rules, using our own assignment.
    Legacy v1 preserves historical overbroad ignore handling. Neither policy
    changes tracking. Do not silently combine results from different policies.
    """
    if policy == LEGACY_MOT17_PREPROCESSING:
        return _legacy_preprocess_frame(
            gt_boxes, gt_ids, gt_classes, gt_conf, tr_boxes, tr_ids, iou_threshold)
    if policy != MOT17_PREPROCESSING:
        raise ValueError(f"unknown MOT17 preprocessing policy: {policy}")
    if not np.isfinite(iou_threshold) or not 0 < iou_threshold <= 1:
        raise ValueError("IoU threshold must be finite and in (0, 1]")
    gt_boxes, tr_boxes = gt_boxes.reshape(-1, 4), tr_boxes.reshape(-1, 4)
    if not (len(gt_ids) == len(gt_boxes) == len(gt_classes) == len(gt_conf)) or \
            len(tr_ids) != len(tr_boxes):
        raise ValueError("MOT17 IDs, classes, flags and boxes must align")
    if len(np.unique(gt_ids)) != len(gt_ids) or len(np.unique(tr_ids)) != len(tr_ids):
        raise ValueError("MOT17 IDs must be unique within each frame")
    # metric_iou also validates finite coordinates on empty-sided frames.
    ious = metric_iou(gt_boxes, tr_boxes)
    scoring = (gt_classes == PEDESTRIAN_CLASS) & (gt_conf != 0)
    keep_tracker = np.ones(len(tr_ids), dtype=bool)
    if len(gt_ids) and len(tr_ids):
        if not np.isin(gt_classes, np.arange(1, 14)).all():
            raise ValueError("invalid MOT17 ground-truth class")
        scores = ious.copy()
        scores[scores < iou_threshold - np.finfo(float).eps] = 0
        rows, cols = linear_assignment(-scores)
        matched = scores[rows, cols] > np.finfo(float).eps
        distractor = np.isin(gt_classes[rows], [2, 7, 8, 12])
        keep_tracker[cols[matched & distractor]] = False
    return gt_ids[scoring], gt_boxes[scoring], tr_ids[keep_tracker], tr_boxes[keep_tracker]


def _legacy_preprocess_frame(
    gt_boxes: np.ndarray, gt_ids: np.ndarray, gt_classes: np.ndarray,
    gt_conf: np.ndarray, tr_boxes: np.ndarray, tr_ids: np.ndarray,
    iou_threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Historical v1 body retained verbatim; broad removal is not v2 policy."""
    gt_boxes = gt_boxes.reshape(-1, 4)
    tr_boxes = tr_boxes.reshape(-1, 4)

    scoring = (gt_classes == PEDESTRIAN_CLASS) & (gt_conf >= 1.0)
    ignore = ~scoring  # distractors, zero-marked, and any non-pedestrian class

    keep_tracker = np.ones(tr_boxes.shape[0], dtype=bool)

    # Match tracker boxes to the FULL gt set; a tracker matched to an ignore gt
    # is dropped. Matching against the union means a tracker overlapping a real
    # pedestrian is preferentially bound to it and thus preserved.
    if tr_boxes.shape[0] and gt_boxes.shape[0]:
        ious = iou_matrix(tr_boxes, gt_boxes)  # (T, G)
        cost = 1.0 - ious
        rows, cols = linear_assignment(cost)
        for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
            if ious[r, c] >= iou_threshold and ignore[c]:
                keep_tracker[r] = False

    return (
        gt_ids[scoring],
        gt_boxes[scoring],
        tr_ids[keep_tracker],
        tr_boxes[keep_tracker],
    )


def run_sequence(
    seq,
    cfg: TrackerConfig,
    first: int,
    last: int,
    camera_shifts=None,
) -> list[FramePair]:
    """Track a sequence's ``[first, last]`` frames and return preprocessed pairs.

    ``seq`` is any reader with ``iter_range(first, last)`` yielding
    :class:`~visiontrack.detection.mot_loader.FrameData` (a live
    :class:`MOT17Sequence` or a :class:`CachedSequence`).

    ``camera_shifts`` optionally supplies per-frame ``(sx, sy)`` global camera
    translations (RQ4 GMC), indexed by position within ``[first, last]``; passed
    to the tracker when ``cfg.use_gmc`` is set.
    """
    tracker = ByteTracker(cfg)
    frames: list[FramePair] = []
    for i, fd in enumerate(seq.iter_range(first, last)):
        shift = camera_shifts[i] if camera_shifts is not None and i < len(camera_shifts) else None
        observations = tracker.update(fd.detections(), camera_shift=shift)
        if observations:
            tr_ids = np.array([o.track_id for o in observations], dtype=np.int64)
            tr_boxes = np.stack([o.xyxy for o in observations], axis=0)
        else:
            tr_ids = np.empty((0,), dtype=np.int64)
            tr_boxes = np.empty((0, 4))
        frames.append(
            preprocess_frame(
                fd.gt_xyxy, fd.gt_ids, fd.gt_classes, fd.gt_conf, tr_boxes, tr_ids
            )
        )
    return frames


def evaluate_frames(frames: list[FramePair]) -> dict[str, float]:
    """Compute CLEAR-MOT + IDF1 + HOTA over already-preprocessed frames.

    ``frames`` is a list of ``(gt_ids, gt_boxes, tracker_ids, tracker_boxes)``
    with ``xyxy`` boxes. Dataset-agnostic — used for both MOT17 and synthetic
    evaluation.
    """
    acc = MotAccumulator(iou_threshold=0.5)
    for g_ids, g_box, t_ids, t_box in frames:
        acc.update(g_ids, g_box, t_ids, t_box)
    clear = acc.result().as_dict()
    ident = compute_identity(frames).as_dict()
    hota = compute_hota(frames).as_dict()
    return {**clear, **ident, **hota}


# Backwards-compatible internal alias.
_metrics_from_frames = evaluate_frames


@dataclass(slots=True)
class SequenceReport:
    name: str
    metrics: dict[str, float]


def evaluate_sequences(
    readers: list,
    cfg: TrackerConfig,
    split,
    subset: str,
    per_sequence: bool = True,
) -> tuple[dict[str, float], list[SequenceReport]]:
    """Track and score a list of sequence readers on a subset of a split.

    Returns ``(overall_metrics, per_sequence_reports)``. Overall metrics pool
    all frames with per-sequence id offsets, which is the correct count-level
    aggregation across sequences (as trackeval's COMBINED_SEQ does).
    """
    pooled: list[FramePair] = []
    reports: list[SequenceReport] = []

    for si, seq in enumerate(readers):
        first, last = split.range_for(seq.name, subset)
        frames = run_sequence(seq, cfg, first, last)
        if per_sequence:
            reports.append(SequenceReport(seq.name, _metrics_from_frames(frames)))

        offset = (si + 1) * _SEQ_ID_OFFSET
        for g_ids, g_box, t_ids, t_box in frames:
            g_off = g_ids + offset if g_ids.size else g_ids
            t_off = t_ids + offset if t_ids.size else t_ids
            pooled.append((g_off, g_box, t_off, t_box))

    overall = _metrics_from_frames(pooled)
    return overall, reports
