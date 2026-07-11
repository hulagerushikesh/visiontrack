"""Adapter exposing cached detections through the :class:`Detector` interface.

The :class:`~visiontrack.tracking.tracker.ByteTracker` consumes ``list[Detection]``
directly, so cached MOT17 detections could be fed to it straight from a
:class:`~visiontrack.datasets.cache.CachedSequence`. This adapter additionally
satisfies the structural :class:`Detector` protocol — ``detect(frame)`` ignores
the (absent) image and returns the next frame's cached boxes — so cached data is
a first-class detector wherever the abstraction is expected, without touching
the synthetic path.
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from .base import Detection

__all__ = ["CachedDetections"]


class CachedDetections:
    """Wrap a frame-indexed detection source as a sequential ``Detector``.

    Parameters
    ----------
    source:
        Anything with a ``frame(idx)`` method returning an object exposing
        ``detections() -> list[Detection]`` (e.g. ``CachedSequence`` or
        ``MOT17Sequence``), plus ``__len__``.
    first, last:
        Optional inclusive 1-indexed frame range (defaults to the whole source).
    """

    def __init__(self, source, first: int | None = None, last: int | None = None) -> None:
        self._source = source
        self.first = 1 if first is None else first
        self.last = len(source) if last is None else last
        self._cursor = self.first

    def detect(self, frame: np.ndarray | None = None) -> list[Detection]:
        """Return the next frame's cached detections (image argument ignored)."""
        if self._cursor > self.last:
            return []
        dets = self._source.frame(self._cursor).detections()
        self._cursor += 1
        return dets

    def reset(self) -> None:
        self._cursor = self.first

    def __iter__(self) -> Iterator[list[Detection]]:
        for idx in range(self.first, self.last + 1):
            yield self._source.frame(idx).detections()

    def __len__(self) -> int:
        return self.last - self.first + 1
