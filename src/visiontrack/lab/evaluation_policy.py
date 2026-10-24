"""Explicit evaluation contracts without reinterpreting historical Lab artifacts."""
from __future__ import annotations

from typing import Any

from ..eval.mot17 import LEGACY_MOT17_PREPROCESSING, MOT17_PREPROCESSING

LEGACY_LAB_PREPROCESSING = "visiontrack.eval.mot17.preprocess_frame"


def preprocessing_for(artifact: dict[str, Any]) -> str:
    """Resolve only known schema/policy pairs; old function names mean v1."""
    version = artifact["schema_version"]
    expected = MOT17_PREPROCESSING if version == 3 else LEGACY_LAB_PREPROCESSING
    if artifact["preprocessing"] != expected:
        raise ValueError("unsupported metric preprocessing for this schema version")
    # Failure extraction and these metric contracts support the fixed 0.5
    # CLEAR/identity threshold only. Do not silently score a declared alternative.
    threshold = artifact["iou_threshold"]
    if type(threshold) not in (int, float) or threshold != 0.5:
        raise ValueError("unsupported metric iou_threshold; expected 0.5")
    return MOT17_PREPROCESSING if version == 3 else LEGACY_MOT17_PREPROCESSING
