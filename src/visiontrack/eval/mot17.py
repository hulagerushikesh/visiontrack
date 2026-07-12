"""MOT17 evaluation runner: preprocessing + tracker + all three metric families.

The subtlety in MOT17 scoring is **not** the metrics — it is the preprocessing.
Ground truth contains *distractor* classes (person-on-vehicle, static person,
distractor, reflection) and *zero-marked* boxes that must not count against a
tracker: a predicted box matched to one of them is silently removed rather than
penalised as a false positive. Getting this exactly right is what lets our
from-scratch HOTA/IDF1 agree with ``trackeval`` (see the cross-check test).

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


def preprocess_frame(
    gt_boxes: np.ndarray,
    gt_ids: np.ndarray,
    gt_classes: np.ndarray,
    gt_conf: np.ndarray,
    tr_boxes: np.ndarray,
    tr_ids: np.ndarray,
    iou_threshold: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Apply MOT17 distractor/ignore handling to one frame.

    Returns ``(gt_score_ids, gt_score_boxes, tracker_keep_ids,
    tracker_keep_boxes)`` where scoring GT is pedestrian + considered, and
    tracker boxes matched to an ignore GT (distractor class or zero-marked)
    have been removed.
    """
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
) -> list[FramePair]:
    """Track a sequence's ``[first, last]`` frames and return preprocessed pairs.

    ``seq`` is any reader with ``iter_range(first, last)`` yielding
    :class:`~visiontrack.detection.mot_loader.FrameData` (a live
    :class:`MOT17Sequence` or a :class:`CachedSequence`).
    """
    tracker = ByteTracker(cfg)
    frames: list[FramePair] = []
    for fd in seq.iter_range(first, last):
        observations = tracker.update(fd.detections())
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
