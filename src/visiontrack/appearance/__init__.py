"""Appearance / re-ID: embedders and the per-track EMA gallery (RQ1)."""
from __future__ import annotations

from .embedder import (
    ColorHistogramEmbedder,
    Embedder,
    IdentityEmbedder,
    SpatialColorHistogramEmbedder,
    make_embedder,
)
from .gallery import normalize, update_gallery

__all__ = [
    "Embedder",
    "ColorHistogramEmbedder",
    "SpatialColorHistogramEmbedder",
    "IdentityEmbedder",
    "make_embedder",
    "update_gallery",
    "normalize",
]
