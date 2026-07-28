"""Global motion compensation (GMC) — from-scratch phase correlation.

On a moving camera the whole image translates between frames, so a track's
constant-velocity Kalman prediction (which assumes a static camera) lands in the
wrong place and association fails — BoT-SORT's motivation for GMC. This module
estimates the **global translation** between two frames and lets the tracker
shift its predictions to follow the camera.

Rather than pull in OpenCV's ORB+RANSAC affine estimator, we estimate translation
with **phase correlation**, which is a few NumPy FFTs and fits the repo's
from-scratch ethos: the normalized cross-power spectrum of two images has an
inverse-FFT that is a sharp peak at their relative shift.

Scope (stated honestly): this recovers **translation only** — the dominant term
for pans/handheld jitter, but not zoom or rotation. It is a first-order GMC, not
BoT-SORT's full affine model.
"""
from __future__ import annotations

import numpy as np

__all__ = ["estimate_translation", "hann_window"]

_EPS = 1e-8


def hann_window(shape: tuple[int, int]) -> np.ndarray:
    """2D separable Hann window — tapers image edges so the FFT's implicit
    periodicity doesn't create a spurious boundary correlation."""
    h, w = shape
    wy = np.hanning(h)[:, None]
    wx = np.hanning(w)[None, :]
    return wy * wx


def estimate_translation(
    img_prev: np.ndarray, img_curr: np.ndarray, window: np.ndarray | None = None
) -> tuple[float, float]:
    """Estimate the ``(sx, sy)`` pixel translation from ``img_prev`` to ``img_curr``.

    Both inputs are 2D grayscale float arrays of the same shape. Returns the shift
    such that ``img_curr`` is approximately ``img_prev`` translated by ``(sx, sy)``
    (``sx`` rightward, ``sy`` downward), via the phase-correlation peak.
    """
    a = np.asarray(img_prev, dtype=np.float64)
    b = np.asarray(img_curr, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("images must be 2D and the same shape")
    h, w = a.shape

    win = window if window is not None else hann_window((h, w))
    a = (a - a.mean()) * win
    b = (b - b.mean()) * win

    fa = np.fft.fft2(a)
    fb = np.fft.fft2(b)
    cross = fa * np.conj(fb)
    cross /= np.abs(cross) + _EPS          # normalize -> phase only
    corr = np.fft.ifft2(cross).real        # sharp peak at the shift

    peak = np.unravel_index(int(np.argmax(corr)), corr.shape)
    sy, sx = peak
    # Wrap peaks in the upper half back to negative shifts.
    if sy > h // 2:
        sy -= h
    if sx > w // 2:
        sx -= w
    # The cross-power peak of (prev, curr) sits at the *curr→prev* shift; negate
    # so we return the prev→curr content motion (what to add to predictions).
    return float(-sx), float(-sy)
