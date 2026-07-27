"""CLEAR-MOT evaluation metrics.

A tracker is only as good as it measures. This module implements the standard
multi-object-tracking metrics (Bernardin & Stiefelhagen, 2008) so results are
comparable and regressions are catchable in CI:

* **MOTA** — Multi-Object Tracking Accuracy, ``1 - (FN + FP + IDSW) / GT``.
  A single number penalising misses, false positives and identity switches.
* **MOTP** — Multi-Object Tracking Precision: average localisation IoU of the
  true-positive matches. Measures *how well* matched boxes align.
* **IDSW** — identity switches: a ground-truth object handed a different track
  id than it previously carried.
* **MT / ML** — mostly-tracked / mostly-lost trajectories (covered >80% / <20%
  of their life).

The per-frame correspondence follows CLEAR-MOT exactly: existing GT↔hypothesis
pairs are preserved when still geometrically valid (this is what makes IDSW
meaningful), and only the remainder is re-solved with Hungarian matching.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..core.assignment import linear_assignment
from ..core.geometry import iou_matrix

__all__ = ["MotMetrics", "MotAccumulator", "evaluate_sequence"]


@dataclass(slots=True)
class MotMetrics:
    """Aggregated tracking metrics for one sequence."""

    num_frames: int
    num_gt: int
    true_positives: int
    false_positives: int
    false_negatives: int
    id_switches: int
    mota: float
    motp: float
    precision: float
    recall: float
    mostly_tracked: int
    mostly_lost: int
    partially_tracked: int
    num_unique_gt: int

    def as_dict(self) -> dict[str, float]:
        return {
            "frames": self.num_frames,
            "gt_boxes": self.num_gt,
            "unique_gt": self.num_unique_gt,
            "TP": self.true_positives,
            "FP": self.false_positives,
            "FN": self.false_negatives,
            "IDSW": self.id_switches,
            "MOTA": round(self.mota, 4),
            "MOTP": round(self.motp, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "MT": self.mostly_tracked,
            "PT": self.partially_tracked,
            "ML": self.mostly_lost,
        }

    def __str__(self) -> str:  # pragma: no cover - presentation only
        d = self.as_dict()
        return (
            f"MOTA={d['MOTA']:.3f}  MOTP={d['MOTP']:.3f}  "
            f"IDSW={d['IDSW']}  FP={d['FP']}  FN={d['FN']}  "
            f"P={d['precision']:.3f}  R={d['recall']:.3f}  "
            f"MT={d['MT']} PT={d['PT']} ML={d['ML']}"
        )


class MotAccumulator:
    """Streaming CLEAR-MOT accumulator; feed one frame at a time."""

    def __init__(self, iou_threshold: float = 0.5, on_switch=None) -> None:
        self.iou_threshold = iou_threshold
        # Optional hook fired on each identity switch, for error-taxonomy
        # analysis. Signature: on_switch(frame, gt_id, prev_hyp, new_hyp,
        # gt_index, gt_ids, gt_boxes). Default None -> zero behaviour change.
        self._on_switch = on_switch
        self._tp = 0
        self._fp = 0
        self._fn = 0
        self._idsw = 0
        self._iou_sum = 0.0
        self._frames = 0
        self._num_gt = 0

        # Persistent GT -> last matched hypothesis id, for switch detection.
        self._last_hyp: dict[int, int] = {}
        # Per-GT life stats for MT/ML.
        self._gt_total: dict[int, int] = defaultdict(int)
        self._gt_matched: dict[int, int] = defaultdict(int)

    def update(
        self,
        gt_ids: np.ndarray,
        gt_boxes: np.ndarray,
        hyp_ids: np.ndarray,
        hyp_boxes: np.ndarray,
    ) -> None:
        """Register one frame of ground truth and hypotheses (``xyxy`` boxes)."""
        gt_ids = np.asarray(gt_ids, dtype=np.int64).reshape(-1)
        hyp_ids = np.asarray(hyp_ids, dtype=np.int64).reshape(-1)
        gt_boxes = np.asarray(gt_boxes, dtype=np.float64).reshape(-1, 4)
        hyp_boxes = np.asarray(hyp_boxes, dtype=np.float64).reshape(-1, 4)

        self._frames += 1
        self._num_gt += len(gt_ids)
        for g in gt_ids:
            self._gt_total[int(g)] += 1

        n_gt, n_hyp = len(gt_ids), len(hyp_ids)
        matched_gt: set[int] = set()
        matched_hyp: set[int] = set()
        frame_matches: list[tuple[int, int, float]] = []  # (gt_row, hyp_col, iou)

        ious = iou_matrix(gt_boxes, hyp_boxes) if n_gt and n_hyp else np.zeros((n_gt, n_hyp))

        # 1) Preserve existing correspondences that are still valid. This is
        #    what prevents spurious identity switches when two objects cross.
        gt_row = {int(g): i for i, g in enumerate(gt_ids)}
        hyp_col = {int(h): j for j, h in enumerate(hyp_ids)}
        for g, prev_h in self._last_hyp.items():
            gi = gt_row.get(g)
            hj = hyp_col.get(prev_h)
            if gi is None or hj is None:
                continue
            if gi in matched_gt or hj in matched_hyp:
                continue
            if ious[gi, hj] >= self.iou_threshold:
                matched_gt.add(gi)
                matched_hyp.add(hj)
                frame_matches.append((gi, hj, ious[gi, hj]))

        # 2) Hungarian-match the remaining GTs and hypotheses.
        free_gt = [i for i in range(n_gt) if i not in matched_gt]
        free_hyp = [j for j in range(n_hyp) if j not in matched_hyp]
        if free_gt and free_hyp:
            sub = ious[np.ix_(free_gt, free_hyp)]
            # Maximise IoU == minimise (1 - IoU); forbid sub-threshold pairs.
            cost = 1.0 - sub
            rows, cols = linear_assignment(cost)
            for r, c in zip(rows, cols, strict=False):
                if sub[r, c] >= self.iou_threshold:
                    gi, hj = free_gt[r], free_hyp[c]
                    matched_gt.add(gi)
                    matched_hyp.add(hj)
                    frame_matches.append((gi, hj, sub[r, c]))

        # 3) Tally TP / FP / FN, switches and localisation error.
        for gi, hj, iou in frame_matches:
            g = int(gt_ids[gi])
            h = int(hyp_ids[hj])
            self._tp += 1
            self._iou_sum += iou
            self._gt_matched[g] += 1
            prev = self._last_hyp.get(g)
            if prev is not None and prev != h:
                self._idsw += 1
                if self._on_switch is not None:
                    self._on_switch(
                        self._frames - 1, g, prev, h, gi, gt_ids, gt_boxes
                    )
            self._last_hyp[g] = h

        self._fp += n_hyp - len(matched_hyp)
        self._fn += n_gt - len(matched_gt)

    def result(self) -> MotMetrics:
        tp, fp, fn = self._tp, self._fp, self._fn
        gt = self._num_gt
        mota = 1.0 - (fn + fp + self._idsw) / gt if gt else 0.0
        motp = self._iou_sum / tp if tp else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0

        mt = pt = ml = 0
        for g, total in self._gt_total.items():
            ratio = self._gt_matched.get(g, 0) / total if total else 0.0
            if ratio >= 0.8:
                mt += 1
            elif ratio < 0.2:
                ml += 1
            else:
                pt += 1

        return MotMetrics(
            num_frames=self._frames,
            num_gt=gt,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            id_switches=self._idsw,
            mota=mota,
            motp=motp,
            precision=precision,
            recall=recall,
            mostly_tracked=mt,
            mostly_lost=ml,
            partially_tracked=pt,
            num_unique_gt=len(self._gt_total),
        )


def evaluate_sequence(
    frames_gt: list[tuple[np.ndarray, np.ndarray]],
    frames_hyp: list[tuple[np.ndarray, np.ndarray]],
    iou_threshold: float = 0.5,
) -> MotMetrics:
    """Evaluate aligned per-frame ``(ids, boxes)`` ground truth vs hypotheses."""
    if len(frames_gt) != len(frames_hyp):
        raise ValueError("ground-truth and hypothesis frame counts differ")
    acc = MotAccumulator(iou_threshold=iou_threshold)
    for (gt_ids, gt_boxes), (hyp_ids, hyp_boxes) in zip(frames_gt, frames_hyp, strict=False):
        acc.update(gt_ids, gt_boxes, hyp_ids, hyp_boxes)
    return acc.result()
