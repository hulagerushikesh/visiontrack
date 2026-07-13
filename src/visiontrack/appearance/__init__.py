"""Appearance / re-ID: embedders and the per-track EMA gallery (RQ1)."""
from __future__ import annotations

from .embedder import ColorHistogramEmbedder, Embedder, IdentityEmbedder
from .gallery import normalize, update_gallery

__all__ = [
    "Embedder",
    "ColorHistogramEmbedder",
    "IdentityEmbedder",
    "update_gallery",
    "normalize",
]
