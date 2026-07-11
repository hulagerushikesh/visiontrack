"""A Kalman filter for bounding-box tracking.

This is a from-scratch implementation of the linear Kalman filter used by
SORT / DeepSORT, kept deliberately explicit so the estimation math is
auditable rather than hidden behind a library.

State (8-dim), constant-velocity model::

    x = [cx, cy, a, h, vcx, vcy, va, vh]

where ``(cx, cy)`` is the box centre, ``a`` its aspect ratio ``w / h`` and
``h`` its height. The velocities are the per-frame derivatives of the first
four components. The measurement space is the 4-dim ``xyah`` box.

Two design choices are worth calling out because they matter in practice:

* **Height-scaled noise.** The process and measurement noise standard
  deviations are proportional to the object's height. A pedestrian near the
  camera (large ``h``) is expected to move more pixels/frame than one far
  away, so a fixed-variance filter would be simultaneously too tight for the
  near object and too loose for the far one. Scaling by ``h`` makes the
  filter roughly scale-invariant.
* **Gating via Mahalanobis distance.** Association is not done on raw pixel
  error but on the Mahalanobis distance in innovation space, which accounts
  for the filter's own uncertainty. Freshly-created or long-occluded tracks
  have large covariance and are therefore allowed a larger search radius.

The implementation is vectorized across tracks: ``predict`` and
``project`` accept ``(N, 8)`` / ``(N, 8, 8)`` batches so the whole track set
is advanced in a handful of NumPy calls.
"""
from __future__ import annotations

import numpy as np

__all__ = ["KalmanBoxTracker", "chi2_gating_threshold"]

# 0.95 quantile of the chi-square distribution for N degrees of freedom.
# Used as a gating threshold on the Mahalanobis distance in measurement space.
_CHI2_INV_95 = {
    1: 3.8415,
    2: 5.9915,
    3: 7.8147,
    4: 9.4877,
    5: 11.070,
    6: 12.592,
    7: 14.067,
    8: 15.507,
    9: 16.919,
}


def chi2_gating_threshold(dof: int = 4) -> float:
    """Return the 95% chi-square gating threshold for ``dof`` measurements."""
    return _CHI2_INV_95[dof]


class KalmanBoxTracker:
    """Batched constant-velocity Kalman filter over ``xyah`` boxes.

    A single instance is shared by the whole tracker; it holds no per-track
    state itself. Each track carries its own ``(8,) mean`` and ``(8, 8)
    covariance`` and passes them into these methods. This keeps the filter
    stateless and trivially testable.
    """

    ndim = 4  # measurement dimensionality (cx, cy, a, h)

    def __init__(
        self,
        std_weight_position: float = 1.0 / 20.0,
        std_weight_velocity: float = 1.0 / 160.0,
    ) -> None:
        self._std_weight_position = std_weight_position
        self._std_weight_velocity = std_weight_velocity

        # Constant-velocity transition matrix F (8x8): position += velocity.
        self._F = np.eye(2 * self.ndim)
        for i in range(self.ndim):
            self._F[i, self.ndim + i] = 1.0

        # Measurement matrix H (4x8): we observe position, not velocity.
        self._H = np.eye(self.ndim, 2 * self.ndim)

    # -- initialization ---------------------------------------------------
    def initiate(self, measurement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Create a track state from an initial ``xyah`` measurement.

        Velocity is initialised to zero with a deliberately large variance
        (we have no velocity evidence yet), while position variance is tied
        to the box height.
        """
        measurement = np.asarray(measurement, dtype=np.float64)
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.concatenate([mean_pos, mean_vel])

        h = measurement[3]
        std = np.array(
            [
                2 * self._std_weight_position * h,
                2 * self._std_weight_position * h,
                1e-2,
                2 * self._std_weight_position * h,
                10 * self._std_weight_velocity * h,
                10 * self._std_weight_velocity * h,
                1e-5,
                10 * self._std_weight_velocity * h,
            ]
        )
        covariance = np.diag(np.square(std))
        return mean, covariance

    # -- prediction -------------------------------------------------------
    def _process_noise(self, heights: np.ndarray) -> np.ndarray:
        """Process-noise covariance ``Q`` for each track, shape ``(N, 8, 8)``."""
        spw, svw = self._std_weight_position, self._std_weight_velocity
        std = np.stack(
            [
                spw * heights,
                spw * heights,
                np.full_like(heights, 1e-2),
                spw * heights,
                svw * heights,
                svw * heights,
                np.full_like(heights, 1e-5),
                svw * heights,
            ],
            axis=1,
        )
        q = np.square(std)  # (N, 8)
        return q[:, :, None] * np.eye(2 * self.ndim)[None, :, :]

    def predict(
        self, mean: np.ndarray, covariance: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Advance one or many track states by one time step.

        Accepts either single ``(8,) / (8, 8)`` arrays or batched
        ``(N, 8) / (N, 8, 8)`` arrays and returns matching shapes.
        """
        single = mean.ndim == 1
        m = np.atleast_2d(mean)
        p = covariance[None] if single else covariance

        heights = m[:, 3]
        q = self._process_noise(heights)

        m = m @ self._F.T
        p = self._F[None] @ p @ self._F.T[None] + q

        if single:
            return m[0], p[0]
        return m, p

    # -- measurement projection ------------------------------------------
    def project(
        self, mean: np.ndarray, covariance: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project state distribution into measurement space (``xyah``).

        Returns the projected mean ``(N, 4)`` and innovation covariance
        ``S = H P Hᵀ + R`` of shape ``(N, 4, 4)``.
        """
        single = mean.ndim == 1
        m = np.atleast_2d(mean)
        p = covariance[None] if single else covariance

        heights = m[:, 3]
        std = np.stack(
            [
                self._std_weight_position * heights,
                self._std_weight_position * heights,
                np.full_like(heights, 1e-1),
                self._std_weight_position * heights,
            ],
            axis=1,
        )
        r = np.square(std)[:, :, None] * np.eye(self.ndim)[None]  # measurement noise

        proj_mean = m @ self._H.T
        proj_cov = self._H[None] @ p @ self._H.T[None] + r

        if single:
            return proj_mean[0], proj_cov[0]
        return proj_mean, proj_cov

    # -- correction -------------------------------------------------------
    def update(
        self, mean: np.ndarray, covariance: np.ndarray, measurement: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Correct a single track state with a new ``xyah`` measurement.

        Uses the Joseph-form covariance update, which stays symmetric and
        positive semi-definite under floating-point error far better than the
        naive ``(I - K H) P`` form.
        """
        proj_mean, proj_cov = self.project(mean, covariance)

        # Kalman gain K = P Hᵀ S⁻¹, solved rather than inverted for stability.
        pht = covariance @ self._H.T                     # (8, 4)
        kalman_gain = np.linalg.solve(proj_cov, pht.T).T  # (8, 4)

        innovation = np.asarray(measurement, dtype=np.float64) - proj_mean
        new_mean = mean + kalman_gain @ innovation

        ikh = np.eye(2 * self.ndim) - kalman_gain @ self._H
        r = self._measurement_noise(mean[3])
        new_cov = ikh @ covariance @ ikh.T + kalman_gain @ r @ kalman_gain.T
        # Enforce exact symmetry to counter accumulated rounding error.
        new_cov = 0.5 * (new_cov + new_cov.T)
        return new_mean, new_cov

    def _measurement_noise(self, height: float) -> np.ndarray:
        std = np.array(
            [
                self._std_weight_position * height,
                self._std_weight_position * height,
                1e-1,
                self._std_weight_position * height,
            ]
        )
        return np.diag(np.square(std))

    # -- gating -----------------------------------------------------------
    def gating_distance(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurements: np.ndarray,
    ) -> np.ndarray:
        """Squared Mahalanobis distance from a track to each measurement.

        ``measurements`` is ``(M, 4)`` in ``xyah``. Returns ``(M,)``. Distances
        above :func:`chi2_gating_threshold` should be treated as impossible
        associations.
        """
        proj_mean, proj_cov = self.project(mean, covariance)
        measurements = np.asarray(measurements, dtype=np.float64).reshape(-1, self.ndim)

        # Solve L z = d via Cholesky for a numerically stable quadratic form.
        chol = np.linalg.cholesky(proj_cov)
        d = measurements - proj_mean                      # (M, 4)
        z = np.linalg.solve(chol, d.T)                    # (4, M)
        return np.sum(z * z, axis=0)                      # (M,)
