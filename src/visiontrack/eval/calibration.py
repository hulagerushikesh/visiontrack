"""Kalman-filter calibration analysis (RQ3).

Before *trusting* the Kalman covariance as a soft association cost, we should
check it is **calibrated**: is the filter's claimed uncertainty consistent with
reality? For a correct linear-Gaussian filter, the squared Mahalanobis distance
between a prediction and the next measurement follows a **χ² distribution with
``dof`` degrees of freedom** (``dof = 4`` here — the measurement is ``xyah``).
Its mean should be ``dof``; systematically larger means the filter is
*overconfident* (covariance too small), smaller means *underconfident*.

We measure this directly on real ground-truth trajectories: step the filter
along each GT track and record the innovation χ² at every frame. The empirical
distribution is compared to χ²(dof) with a reliability (Q–Q) curve, and a scalar
**calibration factor** ``mean(d²)/dof`` summarises the mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.geometry import xyxy_to_xyah
from ..core.kalman import KalmanBoxTracker
from ..detection.mot_loader import PEDESTRIAN_CLASS

__all__ = ["gt_trajectories", "innovation_chi2_samples", "reliability_curve", "CalibrationResult"]


def gt_trajectories(reader, first: int, last: int) -> dict[int, list[tuple[int, np.ndarray]]]:
    """Collect scoring (pedestrian, considered) GT tracks as ``id → [(frame, xyah)]``."""
    traj: dict[int, list[tuple[int, np.ndarray]]] = {}
    for idx in range(first, last + 1):
        fd = reader.frame(idx)
        if fd.gt_ids.size == 0:
            continue
        mask = (fd.gt_classes == PEDESTRIAN_CLASS) & (fd.gt_conf >= 1.0)
        if not mask.any():
            continue
        xyah = xyxy_to_xyah(fd.gt_xyxy[mask])
        for i, gid in enumerate(fd.gt_ids[mask].tolist()):
            traj.setdefault(int(gid), []).append((idx, xyah[i]))
    return traj


def innovation_chi2_samples(reader, first: int, last: int, noise_scale: float = 1.0) -> np.ndarray:
    """Squared Mahalanobis innovations of a CV Kalman filter along GT tracks.

    For each ground-truth trajectory the filter is initialised on the first
    box, then for each subsequent *consecutive* frame we predict and record the
    χ² distance to the true measurement before updating. Gaps reinitialise the
    filter. ``noise_scale`` scales the filter's noise (``<1`` = more confident),
    letting you probe what scale calibrates it. Returns a 1-D array of χ² values.
    """
    kf = KalmanBoxTracker(
        std_weight_position=(1.0 / 20.0) * noise_scale,
        std_weight_velocity=(1.0 / 160.0) * noise_scale,
    )
    samples: list[float] = []
    for obs in gt_trajectories(reader, first, last).values():
        obs.sort(key=lambda t: t[0])
        mean, cov = kf.initiate(obs[0][1])
        prev = obs[0][0]
        for frame, z in obs[1:]:
            if frame != prev + 1:
                mean, cov = kf.initiate(z)  # gap -> restart
                prev = frame
                continue
            mean, cov = kf.predict(mean, cov)
            d2 = kf.gating_distance(mean, cov, z[None])[0]
            samples.append(float(d2))
            mean, cov = kf.update(mean, cov, z)
            prev = frame
    return np.asarray(samples, dtype=np.float64)


@dataclass(slots=True)
class CalibrationResult:
    theoretical: np.ndarray   # χ²(dof) quantiles
    empirical: np.ndarray     # matching empirical quantiles of the samples
    calibration_factor: float  # mean(d²) / dof  (1.0 == perfectly calibrated)
    dof: int
    n: int

    @property
    def overconfident(self) -> bool:
        return self.calibration_factor > 1.0


def reliability_curve(d2: np.ndarray, dof: int = 4, n_points: int = 50) -> CalibrationResult:
    """Q–Q reliability curve of innovation χ² against the χ²(dof) reference."""
    from scipy.stats import chi2

    d2 = np.asarray(d2, dtype=np.float64)
    qs = np.linspace(0.02, 0.98, n_points)
    empirical = np.quantile(d2, qs) if d2.size else np.zeros_like(qs)
    theoretical = chi2.ppf(qs, dof)
    factor = float(d2.mean() / dof) if d2.size else 0.0
    return CalibrationResult(theoretical, empirical, factor, dof, int(d2.size))
