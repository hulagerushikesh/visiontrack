"""HOTA and IDF1 — from scratch.

These are the two modern, association-aware tracking metrics that MOTA misses:

* **IDF1** (Ristani et al., 2016) scores *identity consistency*. It finds the
  globally optimal one-to-one matching between ground-truth identities and
  predicted identities over the whole sequence, then reports the F1 of the
  identity-true-positive frame count. A tracker that detects everything but
  swaps ids constantly scores high MOTA and low IDF1.

* **HOTA** (Luiten et al., 2021) is the current field standard. It explicitly
  factorises into **detection accuracy (DetA)** and **association accuracy
  (AssA)** and geometrically averages them, ``HOTA = √(DetA · AssA)``, itself
  averaged over localisation thresholds α ∈ {0.05, …, 0.95}. This balances "did
  you find the objects" against "did you keep their identities", which MOTA
  does not.

Both are implemented here directly (only ``core.geometry`` for IoU and
``core.assignment`` for the matchings — our own solvers) and are cross-checked
against ``trackeval`` in the test-suite. Input to every function is a list over
frames of ``(gt_ids, gt_boxes, tr_ids, tr_boxes)`` with **global integer ids**
and ``xyxy`` boxes, already preprocessed for the dataset's ignore rules.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.assignment import linear_assignment
from ..core.geometry import iou_matrix

__all__ = [
    "FramePair",
    "HotaResult",
    "IdentityResult",
    "compute_hota",
    "compute_identity",
    "HOTA_ALPHAS",
]

# Localisation thresholds HOTA averages over (0.05 … 0.95), matching trackeval.
HOTA_ALPHAS = np.round(np.arange(0.05, 0.96, 0.05), 2)
_EPS = 1e-9

# One frame's aligned data: (gt_ids, gt_xyxy, tracker_ids, tracker_xyxy).
FramePair = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def _remap_ids(frames: list[FramePair]) -> tuple[dict[int, int], dict[int, int]]:
    """Map arbitrary gt/tracker ids to contiguous ``[0, N)`` indices."""
    gt_ids: set[int] = set()
    tr_ids: set[int] = set()
    for g_ids, _, t_ids, _ in frames:
        gt_ids.update(int(i) for i in g_ids.tolist())
        tr_ids.update(int(i) for i in t_ids.tolist())
    gt_map = {gid: k for k, gid in enumerate(sorted(gt_ids))}
    tr_map = {tid: k for k, tid in enumerate(sorted(tr_ids))}
    return gt_map, tr_map


@dataclass(slots=True)
class HotaResult:
    hota: float
    det_a: float
    ass_a: float
    det_re: float
    det_pr: float
    ass_re: float
    ass_pr: float
    per_alpha: np.ndarray  # HOTA at each α

    def as_dict(self) -> dict[str, float]:
        return {
            "HOTA": round(self.hota, 4),
            "DetA": round(self.det_a, 4),
            "AssA": round(self.ass_a, 4),
            "DetRe": round(self.det_re, 4),
            "DetPr": round(self.det_pr, 4),
            "AssRe": round(self.ass_re, 4),
            "AssPr": round(self.ass_pr, 4),
        }


@dataclass(slots=True)
class IdentityResult:
    idf1: float
    idp: float
    idr: float
    idtp: int
    idfp: int
    idfn: int

    def as_dict(self) -> dict[str, float]:
        return {
            "IDF1": round(self.idf1, 4),
            "IDP": round(self.idp, 4),
            "IDR": round(self.idr, 4),
            "IDTP": self.idtp,
            "IDFP": self.idfp,
            "IDFN": self.idfn,
        }


def _accumulate_globals(
    frames: list[FramePair], gt_map: dict[int, int], tr_map: dict[int, int]
) -> tuple[np.ndarray, np.ndarray, list[tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    """Per-id appearance counts and per-frame (gt_rows, tr_cols, iou) triples."""
    n_gt, n_tr = len(gt_map), len(tr_map)
    gt_count = np.zeros(n_gt)
    tr_count = np.zeros(n_tr)
    per_frame: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    for g_ids, g_box, t_ids, t_box in frames:
        gr = np.array([gt_map[int(i)] for i in g_ids.tolist()], dtype=np.int64)
        tc = np.array([tr_map[int(i)] for i in t_ids.tolist()], dtype=np.int64)
        gt_count[gr] += 1
        tr_count[tc] += 1
        if gr.size and tc.size:
            iou = iou_matrix(g_box, t_box)
        else:
            iou = np.zeros((gr.size, tc.size))
        per_frame.append((gr, tc, iou))
    return gt_count, tr_count, per_frame


def compute_hota(frames: list[FramePair], alphas: np.ndarray = HOTA_ALPHAS) -> HotaResult:
    """Compute HOTA and its components over a sequence of aligned frames."""
    gt_map, tr_map = _remap_ids(frames)
    n_gt, n_tr = len(gt_map), len(tr_map)
    gt_count, tr_count, per_frame = _accumulate_globals(frames, gt_map, tr_map)

    # Global alignment score = association-IoU between every (gt, tracker) id,
    # accumulated over the whole sequence. Used to bias per-frame matching so a
    # detection is assigned to the identity it *usually* co-occurs with.
    potential = np.zeros((n_gt, n_tr))
    for gr, tc, iou in per_frame:
        if gr.size and tc.size:
            np.add.at(potential, (gr[:, None], tc[None, :]), iou)
    denom = gt_count[:, None] + tr_count[None, :] - potential
    global_align = potential / np.maximum(denom, _EPS)

    hotas, det_as, ass_as = [], [], []
    det_res, det_prs, ass_res, ass_prs = [], [], [], []

    for alpha in alphas:
        matches_count = np.zeros((n_gt, n_tr))
        tp = 0
        n_gt_dets = 0
        n_tr_dets = 0
        for gr, tc, iou in per_frame:
            n_gt_dets += gr.size
            n_tr_dets += tc.size
            if gr.size == 0 or tc.size == 0:
                continue
            mask = iou >= alpha - _EPS
            score = global_align[np.ix_(gr, tc)] * mask
            # Maximise total alignment score -> minimise the negation.
            rows, cols = linear_assignment(-score)
            for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
                if mask[r, c]:
                    tp += 1
                    matches_count[gr[r], tc[c]] += 1
        fn = n_gt_dets - tp
        fp = n_tr_dets - tp

        det_a = tp / max(tp + fn + fp, _EPS)
        det_re = tp / max(tp + fn, _EPS)
        det_pr = tp / max(tp + fp, _EPS)

        # Association: for each true-positive (g,t) pairing, its Ass-IoU is the
        # overlap of the two identities' trajectories.
        ass_denom = gt_count[:, None] + tr_count[None, :] - matches_count
        ass_iou = matches_count / np.maximum(ass_denom, _EPS)
        if tp > 0:
            recall_term = matches_count / np.maximum(gt_count[:, None], _EPS)
            precision_term = matches_count / np.maximum(tr_count[None, :], _EPS)
            ass_a = float((matches_count * ass_iou).sum() / tp)
            ass_re = float((matches_count * recall_term).sum() / tp)
            ass_pr = float((matches_count * precision_term).sum() / tp)
        else:
            ass_a = ass_re = ass_pr = 0.0

        hotas.append(float(np.sqrt(det_a * ass_a)))
        det_as.append(det_a)
        ass_as.append(ass_a)
        det_res.append(det_re)
        det_prs.append(det_pr)
        ass_res.append(ass_re)
        ass_prs.append(ass_pr)

    return HotaResult(
        hota=float(np.mean(hotas)),
        det_a=float(np.mean(det_as)),
        ass_a=float(np.mean(ass_as)),
        det_re=float(np.mean(det_res)),
        det_pr=float(np.mean(det_prs)),
        ass_re=float(np.mean(ass_res)),
        ass_pr=float(np.mean(ass_prs)),
        per_alpha=np.array(hotas),
    )


def compute_identity(frames: list[FramePair], iou_threshold: float = 0.5) -> IdentityResult:
    """Compute IDF1/IDP/IDR via globally optimal identity assignment."""
    gt_map, tr_map = _remap_ids(frames)
    n_gt, n_tr = len(gt_map), len(tr_map)
    gt_count, tr_count, per_frame = _accumulate_globals(frames, gt_map, tr_map)

    # Co-occurrence: frames where gt id g and tracker id t overlap at ≥ threshold.
    potential = np.zeros((n_gt, n_tr))
    for gr, tc, iou in per_frame:
        if gr.size and tc.size:
            hit = (iou >= iou_threshold).astype(np.float64)
            np.add.at(potential, (gr[:, None], tc[None, :]), hit)

    total_gt = float(gt_count.sum())
    total_tr = float(tr_count.sum())

    if n_gt == 0 and n_tr == 0:
        return IdentityResult(1.0, 1.0, 1.0, 0, 0, 0)

    # Ristani's bipartite formulation on a (G+T)×(G+T) cost matrix: real
    # gt↔tracker matches in the top-left block, plus unmatched "sinks" whose
    # cost is the identity's full length. BIG forbids illegal pairings.
    size = n_gt + n_tr
    big = float(total_gt + total_tr + 1.0)
    cost = np.full((size, size), big)
    if n_gt and n_tr:
        cost[:n_gt, :n_tr] = gt_count[:, None] + tr_count[None, :] - 2.0 * potential
    # gt-unmatched sinks (top-right diagonal = IDFN of leaving g unmatched)
    for g in range(n_gt):
        cost[g, n_tr + g] = gt_count[g]
    # tracker-unmatched sinks (bottom-left diagonal = IDFP of leaving t unmatched)
    for t in range(n_tr):
        cost[n_gt + t, t] = tr_count[t]
    # bottom-right block: sink-to-sink, free
    cost[n_gt:, n_tr:] = 0.0

    rows, cols = linear_assignment(cost)
    idtp = 0.0
    for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
        if r < n_gt and c < n_tr:
            idtp += potential[r, c]

    idfn = total_gt - idtp
    idfp = total_tr - idtp
    idp = idtp / max(idtp + idfp, _EPS)
    idr = idtp / max(idtp + idfn, _EPS)
    idf1 = 2 * idtp / max(2 * idtp + idfp + idfn, _EPS)
    return IdentityResult(
        idf1=float(idf1),
        idp=float(idp),
        idr=float(idr),
        idtp=int(round(idtp)),
        idfp=int(round(idfp)),
        idfn=int(round(idfn)),
    )
