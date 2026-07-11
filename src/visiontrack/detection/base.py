"""Detection data model and the detector interface.

The tracker is deliberately decoupled from *how* boxes are produced. Anything
that yields per-frame :class:`Detection` lists — a YOLO ONNX model, a classical
detector, a dataset loader, or the synthetic generator used in tests — can be
plugged in behind :class:`Detector`.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass(slots=True)
class Detection:
    """A single detected object in one frame.

    Attributes
    ----------
    xyxy:
        Box as ``(x1, y1, x2, y2)`` in pixel coordinates.
    score:
        Detector confidence in ``[0, 1]``.
    class_id:
        Integer class label (``-1`` if class-agnostic).
    feature:
        Optional appearance embedding (e.g. a re-ID vector). Reserved for
        appearance-based association; the motion tracker ignores it.
    """

    xyxy: np.ndarray
    score: float = 1.0
    class_id: int = -1
    feature: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.xyxy = np.asarray(self.xyxy, dtype=np.float64).reshape(4)
        if self.xyxy[2] < self.xyxy[0] or self.xyxy[3] < self.xyxy[1]:
            raise ValueError(f"degenerate box (x2<x1 or y2<y1): {self.xyxy}")

    @property
    def width(self) -> float:
        return float(self.xyxy[2] - self.xyxy[0])

    @property
    def height(self) -> float:
        return float(self.xyxy[3] - self.xyxy[1])


def detections_to_array(dets: Sequence[Detection]) -> np.ndarray:
    """Stack detection boxes into an ``(N, 4)`` array (empty-safe)."""
    if not dets:
        return np.empty((0, 4), dtype=np.float64)
    return np.stack([d.xyxy for d in dets], axis=0)


def scores_to_array(dets: Sequence[Detection]) -> np.ndarray:
    if not dets:
        return np.empty((0,), dtype=np.float64)
    return np.array([d.score for d in dets], dtype=np.float64)


class Detector(Protocol):
    """Structural interface for a per-frame object detector."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Return detections for a single image frame (``H x W x 3``)."""
        ...


def iter_frame_detections(
    detector: Detector, frames: Iterable[np.ndarray]
) -> Iterable[list[Detection]]:
    """Convenience generator: run ``detector`` over an iterable of frames."""
    for frame in frames:
        yield detector.detect(frame)
