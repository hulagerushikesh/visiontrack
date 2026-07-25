"""Learned motion residual — a small MLP that corrects the constant-velocity
Kalman prediction (RQ2), implemented from scratch on NumPy.

The constant-velocity (CV) filter predicts the next centre as ``p_t + v_t``. On
near-linear pedestrian motion (MOT17) that is nearly exact; on maneuver-heavy
motion (dancers) it lags at turns and accelerations. RQ2 asks whether a tiny
learned residual on top of CV recovers that lag.

Consistent with the project's ethos, the model is **not** a framework import: a
two-layer tanh MLP with hand-written back-prop and Adam, trained and run on
NumPy, weights serialized to ``.npz``. Inference is a couple of matmuls, cheap
enough to run inside the tracker's predict step.

Convention (all centres are 2-D image coordinates):

* ``v_i = p_i - p_{i-1}`` are per-step velocities.
* CV predicts ``p_{t+1} ≈ p_t + v_t``; the **residual target** is the part CV
  misses, ``r = p_{t+1} - (p_t + v_t)``.
* Features are the last ``K`` velocities, scale-normalized by the box size ``s``
  (so the model is translation- and scale-invariant); the target is ``r / s``.
* At inference, ``p_{t+1} = (p_t + v_t) + s · model(features)``.
"""
from __future__ import annotations

import numpy as np

__all__ = ["WINDOW", "residual_features", "MLPResidual", "MotionResidual"]

WINDOW = 5  # number of past velocities fed to the model


def residual_features(centroids: np.ndarray, scale: float) -> np.ndarray:
    """Last ``WINDOW`` velocities of a centroid track, scale-normalized, flattened.

    ``centroids`` is ``(T, 2)`` with ``T >= WINDOW + 1``. Returns a ``(2*WINDOW,)``
    vector; earlier velocities are zero-padded if the track is short.
    """
    c = np.asarray(centroids, dtype=np.float64).reshape(-1, 2)
    vel = np.diff(c, axis=0)  # (T-1, 2)
    s = scale if scale > 1e-6 else 1.0
    feats = np.zeros((WINDOW, 2), dtype=np.float64)
    take = vel[-WINDOW:]
    feats[WINDOW - take.shape[0]:] = take / s
    return feats.reshape(-1)


class MLPResidual:
    """A 2-layer tanh MLP (from-scratch forward/backward + Adam), MSE regression."""

    def __init__(self, in_dim: int = 2 * WINDOW, hidden: int = 32, out_dim: int = 2,
                 seed: int = 0) -> None:
        rng = np.random.default_rng(seed)
        # He/Xavier-ish init keeps early activations in tanh's linear range.
        self.W1 = rng.normal(0, np.sqrt(1.0 / in_dim), (in_dim, hidden))
        self.b1 = np.zeros(hidden)
        self.W2 = rng.normal(0, np.sqrt(1.0 / hidden), (hidden, out_dim))
        self.b2 = np.zeros(out_dim)
        self._adam = {}

    # -- forward ---------------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, dtype=np.float64))
        h = np.tanh(X @ self.W1 + self.b1)
        return h @ self.W2 + self.b2

    # -- training --------------------------------------------------------------
    def _adam_step(self, name, param, grad, lr, t, b1=0.9, b2=0.999, eps=1e-8):
        st = self._adam.setdefault(name, {"m": np.zeros_like(param), "v": np.zeros_like(param)})
        st["m"] = b1 * st["m"] + (1 - b1) * grad
        st["v"] = b2 * st["v"] + (1 - b2) * (grad * grad)
        mhat = st["m"] / (1 - b1 ** t)
        vhat = st["v"] / (1 - b2 ** t)
        param -= lr * mhat / (np.sqrt(vhat) + eps)

    def fit(self, X: np.ndarray, Y: np.ndarray, *, epochs: int = 60, batch: int = 256,
            lr: float = 3e-3, seed: int = 0, verbose: bool = False) -> list[float]:
        X = np.asarray(X, dtype=np.float64)
        Y = np.asarray(Y, dtype=np.float64).reshape(-1, self.b2.shape[0])
        n = X.shape[0]
        rng = np.random.default_rng(seed)
        losses, step = [], 0
        for ep in range(epochs):
            order = rng.permutation(n)
            ep_loss = 0.0
            for s0 in range(0, n, batch):
                idx = order[s0:s0 + batch]
                xb, yb = X[idx], Y[idx]
                # forward (cache activations)
                z1 = xb @ self.W1 + self.b1
                h = np.tanh(z1)
                yp = h @ self.W2 + self.b2
                diff = yp - yb
                ep_loss += float((diff ** 2).sum())
                # backward (MSE, mean over batch)
                m = xb.shape[0]
                dY = (2.0 / m) * diff
                gW2 = h.T @ dY
                gb2 = dY.sum(0)
                dh = (dY @ self.W2.T) * (1 - h ** 2)  # tanh'
                gW1 = xb.T @ dh
                gb1 = dh.sum(0)
                step += 1
                self._adam_step("W1", self.W1, gW1, lr, step)
                self._adam_step("b1", self.b1, gb1, lr, step)
                self._adam_step("W2", self.W2, gW2, lr, step)
                self._adam_step("b2", self.b2, gb2, lr, step)
            losses.append(ep_loss / n)
            if verbose and (ep % 10 == 0 or ep == epochs - 1):
                print(f"  epoch {ep:3d}  mse={losses[-1]:.5f}")
        return losses

    # -- serialization ---------------------------------------------------------
    def save(self, path: str) -> None:
        np.savez(path, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2, window=WINDOW)

    @classmethod
    def load(cls, path: str) -> MLPResidual:
        with np.load(path) as z:
            m = cls(in_dim=z["W1"].shape[0], hidden=z["W1"].shape[1], out_dim=z["W2"].shape[1])
            m.W1, m.b1, m.W2, m.b2 = z["W1"], z["b1"], z["W2"], z["b2"]
        return m


class MotionResidual:
    """Inference wrapper: correct a CV centre prediction from a centroid history.

    Lazy-loaded from a weights ``.npz``; if no model is set it is a no-op, so a
    tracker with ``motion_residual_path=None`` behaves exactly as before.
    """

    def __init__(self, model: MLPResidual | None = None) -> None:
        self.model = model

    @classmethod
    def from_path(cls, path: str | None) -> MotionResidual:
        return cls(None if not path else MLPResidual.load(path))

    def correct(self, centroids: np.ndarray, scale: float) -> np.ndarray:
        """Return the residual correction (dx, dy) to add to the CV prediction.

        ``centroids`` is the recent centre history ``(T, 2)``; needs ``T >= 2``.
        Zero vector when no model or too little history.
        """
        c = np.asarray(centroids, dtype=np.float64).reshape(-1, 2)
        if self.model is None or c.shape[0] < 2:
            return np.zeros(2)
        feats = residual_features(c, scale)
        s = scale if scale > 1e-6 else 1.0
        return self.model.predict(feats)[0] * s
