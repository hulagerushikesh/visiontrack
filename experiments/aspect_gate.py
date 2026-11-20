"""Development candidate: a motion gate that ignores box aspect ratio.

The default gate tests all four box quantities (centre x, centre y, aspect
ratio, height) against the Kalman prediction. Its aspect-ratio noise is a fixed
0.1, sized for upright pedestrians. On RoundaboutHD, about nine in ten
IoU-passing pairs that the gate blocked failed on aspect ratio alone: turning
vehicles change shape faster than that noise allows. This candidate keeps the
gate on position and height (3 degrees of freedom, chi-square 95% = 7.8147) and
leaves the filter itself unchanged.

It is an experiment-only variant. The library default and TrackerConfig are
untouched, so traces, experiment IDs and the C++ parity contract do not move.
See docs/ASPECT_GATE_DEVELOPMENT.md.
"""
from __future__ import annotations

import numpy as np

from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

GATE_DIMS = (0, 1, 3)  # cx, cy, h — aspect ratio (index 2) excluded
GATE_3DOF = 7.8147
VARIANTS = ("gate_on", "gate_off", "aspect_free_gate")


class AspectFreeGateKalman(KalmanBoxTracker):
    """Same filter; gating distance computed over centre and height only."""

    def gating_distance_batch(self, means, covariances, measurements):
        dims = list(GATE_DIMS)
        proj_mean, proj_cov = self.project(means, covariances)
        meas = np.asarray(measurements, dtype=np.float64).reshape(-1, self.ndim)[:, dims]
        proj_mean = proj_mean[:, dims]
        proj_cov = proj_cov[:, dims][:, :, dims]
        chol = np.linalg.cholesky(proj_cov)
        d = meas[None, :, :] - proj_mean[:, None, :]
        z = np.linalg.solve(chol, np.transpose(d, (0, 2, 1)))
        return np.sum(z * z, axis=1)


def make_tracker(variant: str, config: TrackerConfig | None = None) -> ByteTracker:
    """Build a tracker for one of VARIANTS on top of ``config`` (default config)."""
    from dataclasses import replace

    base = config or TrackerConfig()
    if variant == "gate_on":
        return ByteTracker(base)
    if variant == "gate_off":
        return ByteTracker(replace(base, use_mahalanobis_gating=False))
    if variant == "aspect_free_gate":
        tracker = ByteTracker(base)
        scale = base.kf_noise_scale
        tracker.kf = AspectFreeGateKalman(
            std_weight_position=(1.0 / 20.0) * scale,
            std_weight_velocity=(1.0 / 160.0) * scale,
        )
        tracker._gate = GATE_3DOF
        return tracker
    raise ValueError(f"unknown variant: {variant!r}")
