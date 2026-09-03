"""Discover cached sequence readers for the real-data experiments.

Both DanceTrack and SportsMOT (and any other MOT-format set) are consumed the
same way: one detection ``.npz`` per sequence under a dataset-specific cache dir,
with an optional ``.<embedder>.emb.npz`` sidecar of Re-ID embeddings. This one
helper builds the readers so the benchmark and the error-taxonomy agree on the
exact discovery rule.
"""
from __future__ import annotations

from pathlib import Path


def discover_cache_readers(cache_dir: str | Path, embedder: str = "onnx",
                           glob: str = "*.npz") -> list:
    """Return a :class:`CachedSequence` per detection cache in ``cache_dir``.

    ``glob`` selects the detection caches (e.g. ``"dancetrack*.npz"`` to scope by
    sequence-name prefix, or ``"*.npz"`` for a dataset-dedicated dir). Embedding
    sidecars (``*.emb.npz``) are skipped as primaries and attached when present.
    """
    from visiontrack.datasets.cache import CachedSequence

    readers = []
    for det in sorted(Path(cache_dir).glob(glob)):
        if det.name.endswith(".emb.npz"):
            continue
        emb = det.with_name(det.stem + f".{embedder}.emb.npz")
        readers.append(CachedSequence(det, emb_path=emb) if emb.exists()
                       else CachedSequence(det))
    return readers
