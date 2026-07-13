"""Per-track appearance gallery — an exponential moving average of embeddings.

A track's identity appearance shouldn't be the last frame's embedding (noisy,
occlusion-corrupted) nor the first frame's (stale). DeepSORT's answer, used
here, is an **exponential moving average**: each matched detection nudges the
track's stored embedding, so it tracks slow appearance change while smoothing
per-frame noise. The gallery is kept L2-normalized so cosine distance is a dot
product.
"""
from __future__ import annotations

import numpy as np

__all__ = ["update_gallery", "normalize"]

_EPS = 1e-12


def normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector (no-op-safe for zero vectors)."""
    vec = np.asarray(vec, dtype=np.float64)
    n = np.linalg.norm(vec)
    return vec / n if n > _EPS else vec


def update_gallery(old: np.ndarray | None, new: np.ndarray, alpha: float = 0.9) -> np.ndarray:
    """EMA-update a track's appearance embedding with a new detection embedding.

    ``feature ← α · old + (1 − α) · new`` (α is the *memory*: higher = smoother,
    slower to adapt). Returns the L2-normalized result. On the first update
    (``old is None``) the new embedding is adopted directly.
    """
    new = np.asarray(new, dtype=np.float64)
    if old is None:
        return normalize(new)
    blended = alpha * np.asarray(old, dtype=np.float64) + (1.0 - alpha) * new
    return normalize(blended)
