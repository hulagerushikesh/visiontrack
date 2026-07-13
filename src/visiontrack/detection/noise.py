"""Detector-noise injection for the RQ3 high-noise regime.

RQ3 asks whether folding calibrated Kalman uncertainty into the association
cost (a soft cost, not just a hard gate) helps *when detections are noisy*. To
create that regime on real data we perturb the public detections: jitter boxes,
randomly drop some (missed detections), and add spurious false positives — all
seeded for reproducibility.

:class:`PerturbedSequence` wraps any sequence reader and applies the noise
per-frame, exposing the same streaming interface so the evaluator and tracker
are unchanged. Ground truth is never perturbed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Detection
from .mot_loader import FrameData

__all__ = ["NoiseConfig", "perturb_detections", "PerturbedSequence"]


@dataclass(slots=True)
class NoiseConfig:
    """Detector-noise parameters."""

    jitter_std: float = 8.0        # px std added to each box corner
    drop_prob: float = 0.15        # probability a real detection is dropped
    fp_rate: float = 1.0           # expected false positives per frame (Poisson)
    fp_score: tuple[float, float] = (0.3, 0.7)
    score_jitter: float = 0.1      # std of additive score noise


def _fix_box(b: np.ndarray) -> np.ndarray:
    x1, x2 = sorted((b[0], b[2]))
    y1, y2 = sorted((b[1], b[3]))
    if x2 - x1 < 1:
        x2 = x1 + 1
    if y2 - y1 < 1:
        y2 = y1 + 1
    return np.array([x1, y1, x2, y2])


def perturb_detections(
    dets: list[Detection],
    rng: np.random.Generator,
    cfg: NoiseConfig,
    width: float,
    height: float,
) -> list[Detection]:
    """Return a noisy copy of ``dets``: jittered + dropped + spurious boxes."""
    out: list[Detection] = []
    for d in dets:
        if rng.random() < cfg.drop_prob:
            continue
        box = _fix_box(d.xyxy + rng.normal(0, cfg.jitter_std, size=4))
        score = float(np.clip(d.score + rng.normal(0, cfg.score_jitter), 0.0, 1.0))
        out.append(Detection(xyxy=box, score=score, class_id=d.class_id))

    for _ in range(int(rng.poisson(cfg.fp_rate))):
        cx, cy = rng.uniform([0, 0], [width, height])
        w = rng.uniform(30, 120)
        h = w * rng.uniform(1.5, 3.0)
        box = _fix_box(np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]))
        out.append(Detection(xyxy=box, score=float(rng.uniform(*cfg.fp_score)), class_id=0))
    return out


class PerturbedSequence:
    """Wrap a sequence reader and inject detector noise, deterministically.

    Per-frame randomness is derived from ``[seed, frame_idx]`` so a given
    ``(seed, frame)`` always yields the same perturbation regardless of access
    order. Ground truth passes through untouched.
    """

    def __init__(self, base, cfg: NoiseConfig, seed: int = 0) -> None:
        self.base = base
        self.cfg = cfg
        self.seed = seed
        self.name = getattr(base, "name", "seq")
        self.width = getattr(base, "width", None) or getattr(base.info, "width", 0)
        self.height = getattr(base, "height", None) or getattr(base.info, "height", 0)

    def __len__(self) -> int:
        return len(self.base)

    def frame(self, idx: int) -> FrameData:
        fd = self.base.frame(idx)
        rng = np.random.default_rng([self.seed, idx])
        noisy = perturb_detections(fd.detections(), rng, self.cfg, self.width, self.height)
        if noisy:
            det_xyxy = np.stack([d.xyxy for d in noisy])
            det_scores = np.array([d.score for d in noisy])
        else:
            det_xyxy = np.empty((0, 4))
            det_scores = np.empty((0,))
        return FrameData(
            frame=idx,
            det_xyxy=det_xyxy,
            det_scores=det_scores,
            gt_xyxy=fd.gt_xyxy,
            gt_ids=fd.gt_ids,
            gt_classes=fd.gt_classes,
            gt_conf=fd.gt_conf,
            gt_vis=fd.gt_vis,
            det_features=None,
        )

    def iter_range(self, first: int, last: int):
        for idx in range(first, last + 1):
            yield self.frame(idx)

    def __iter__(self):
        for idx in range(1, len(self.base) + 1):
            yield self.frame(idx)
