"""The association cost — factored into an ablation surface.

Every research question in this project reduces to *what goes into the cost
matrix* that the Hungarian solver minimizes. This module factors that cost so
each contribution is an independent, weighted term:

    cost = w_iou · motion   ⊕   w_app · appearance   ⊕   w_unc · uncertainty

with a **hard gate** (minimum IoU, class match, and optionally the Kalman
Mahalanobis distance) that forbids impossible pairings regardless of the terms.

* **motion** — ``1 − IoU`` (or ``1 − GIoU``), the v1 geometry cost.
* **appearance** — cosine distance between re-ID embeddings (RQ1). Inert until
  embeddings exist (Phase 3); the weight defaults to 0.
* **uncertainty** — a normalized Kalman Mahalanobis distance folded *into* the
  cost rather than used only as a hard gate (RQ3). Weight defaults to 0.

The design contract for this phase: **with ``w_app = w_unc = 0`` and
``use_giou = False`` (the defaults), the cost is bit-identical to the v1
``1 − IoU`` construction**, so the refactor is provably behavior-preserving.
The solver (``core.assignment``) is untouched.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.geometry import giou_matrix, iou_matrix

__all__ = [
    "CostWeights",
    "motion_distance",
    "appearance_distance",
    "uncertainty_distance",
    "build_association_cost",
]

_EPS = 1e-9


@dataclass(slots=True)
class CostWeights:
    """Weights and switches defining the factored association cost."""

    w_iou: float = 1.0
    w_app: float = 0.0
    w_unc: float = 0.0
    use_giou: bool = False

    @property
    def appearance_on(self) -> bool:
        return self.w_app > 0.0

    @property
    def uncertainty_on(self) -> bool:
        return self.w_unc > 0.0


def motion_distance(
    track_boxes: np.ndarray, det_boxes: np.ndarray, use_giou: bool = False
) -> np.ndarray:
    """``(T, D)`` motion cost: ``1 − IoU`` (default) or ``1 − GIoU``."""
    if use_giou:
        return 1.0 - giou_matrix(track_boxes, det_boxes)
    return 1.0 - iou_matrix(track_boxes, det_boxes)


def appearance_distance(track_features: np.ndarray, det_features: np.ndarray) -> np.ndarray:
    """``(T, D)`` cosine distance between appearance embeddings, in ``[0, 2]``.

    Rows/cols are L2-normalized defensively so callers need not pre-normalize.
    """
    tf = np.asarray(track_features, dtype=np.float64).reshape(len(track_features), -1)
    df = np.asarray(det_features, dtype=np.float64).reshape(len(det_features), -1)
    tf = tf / np.maximum(np.linalg.norm(tf, axis=1, keepdims=True), _EPS)
    df = df / np.maximum(np.linalg.norm(df, axis=1, keepdims=True), _EPS)
    cosine = tf @ df.T
    return 1.0 - cosine


def uncertainty_distance(gating_d2: np.ndarray, gate_thresh: float) -> np.ndarray:
    """``(T, D)`` soft uncertainty cost from squared Mahalanobis distances.

    Normalizes the (chi-square) gating distance to ``[0, 1]`` by the gate
    threshold, so a pair right at the gate contributes ~1 and a pair centred on
    the prediction contributes ~0. This turns the hard gate into a graded cost.
    """
    return np.clip(np.asarray(gating_d2, dtype=np.float64) / max(gate_thresh, _EPS), 0.0, 1.0)


def build_association_cost(
    ious: np.ndarray,
    weights: CostWeights,
    iou_thresh: float,
    *,
    motion: np.ndarray | None = None,
    class_mismatch: np.ndarray | None = None,
    gating_d2: np.ndarray | None = None,
    gate_thresh: float | None = None,
    appearance: np.ndarray | None = None,
    uncertainty: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    """Assemble the gated, weighted ``(T, D)`` cost matrix for ``associate``.

    Parameters
    ----------
    ious:
        Precomputed ``(T, D)`` IoU matrix (drives the acceptance gate).
    weights:
        The term weights / switches.
    iou_thresh:
        Minimum IoU for a pair to be eligible; sets ``max_cost``.
    motion:
        Optional precomputed motion cost (e.g. GIoU-based). Defaults to
        ``1 − ious``.
    class_mismatch:
        Optional ``(T, D)`` bool mask of forbidden class pairings.
    gating_d2, gate_thresh:
        Optional squared Mahalanobis distances and the gate threshold; pairs
        beyond the gate are forbidden.
    appearance, uncertainty:
        Optional ``(T, D)`` term matrices, added only when their weight > 0.

    Returns
    -------
    (cost, max_cost):
        ``cost`` with forbidden pairs pushed above ``max_cost`` so the solver
        rejects them.
    """
    ious = np.asarray(ious, dtype=np.float64)
    base_motion = motion if motion is not None else (1.0 - ious)

    cost = weights.w_iou * base_motion
    max_cost = weights.w_iou * (1.0 - iou_thresh)

    if weights.appearance_on and appearance is not None:
        cost = cost + weights.w_app * appearance
    if weights.uncertainty_on and uncertainty is not None:
        cost = cost + weights.w_unc * uncertainty

    forbidden = ious < iou_thresh
    if class_mismatch is not None:
        forbidden = forbidden | class_mismatch
    if gating_d2 is not None and gate_thresh is not None:
        forbidden = forbidden | (np.asarray(gating_d2) > gate_thresh)

    cost = np.where(forbidden, max_cost + 1.0, cost)
    return cost, max_cost
