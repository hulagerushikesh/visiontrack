"""Dataset plumbing: frozen splits and the compact on-disk detection cache.

These modules deliberately live outside ``core`` and import heavier helpers
(pandas is never required; only numpy). The cache is what lets the raw ~5GB of
MOT17 frames be deleted after a one-time precompute — all tracking experiments
read only the cache.
"""
from __future__ import annotations

from .cache import CachedSequence, save_sequence_cache
from .splits import Split, load_split, video_base_id

__all__ = ["CachedSequence", "save_sequence_cache", "Split", "load_split", "video_base_id"]
