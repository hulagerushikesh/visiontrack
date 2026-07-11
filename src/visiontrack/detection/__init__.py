"""Detection layer: data model, interface and interchangeable backends."""
from __future__ import annotations

from .base import Detection, Detector, detections_to_array, scores_to_array
from .synthetic import SyntheticScene, SyntheticSceneConfig

__all__ = [
    "Detection",
    "Detector",
    "detections_to_array",
    "scores_to_array",
    "SyntheticScene",
    "SyntheticSceneConfig",
]
