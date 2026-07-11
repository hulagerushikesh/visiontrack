"""VisionTrack — an online multi-object tracker built from first principles.

Public API::

    from visiontrack import ByteTracker, TrackerConfig, Detection

    tracker = ByteTracker(TrackerConfig())
    for frame_detections in stream:          # list[Detection]
        observations = tracker.update(frame_detections)

The heavy lifting — Kalman filtering, the Hungarian assignment and the
geometry — lives in :mod:`visiontrack.core` and is implemented without any
machine-learning framework, using NumPy alone.
"""
from __future__ import annotations

from .detection.base import Detection, Detector
from .detection.synthetic import SyntheticScene, SyntheticSceneConfig
from .eval.mot import MotAccumulator, MotMetrics, evaluate_sequence
from .tracking.config import TrackerConfig
from .tracking.tracker import ByteTracker, TrackObservation

__version__ = "0.1.0"

__all__ = [
    "ByteTracker",
    "TrackerConfig",
    "TrackObservation",
    "Detection",
    "Detector",
    "SyntheticScene",
    "SyntheticSceneConfig",
    "MotAccumulator",
    "MotMetrics",
    "evaluate_sequence",
    "__version__",
]
