"""Explicit metric semantics; legacy support is for old artifacts, not new claims."""
from __future__ import annotations

LEGACY_EVALUATOR = "visiontrack.metrics/v1"
EVALUATOR = "visiontrack.metrics/v2"


def legacy_evaluate_frames(frames):
    from ._legacy_hota import compute_hota, compute_identity
    from ._legacy_mot import MotAccumulator

    accumulator = MotAccumulator(iou_threshold=0.5)
    for frame in frames:
        accumulator.update(*frame)
    return {**accumulator.result().as_dict(), **compute_identity(frames).as_dict(),
            **compute_hota(frames).as_dict()}


def accumulator_for(evaluator):
    if evaluator == LEGACY_EVALUATOR:
        from ._legacy_mot import MotAccumulator
    elif evaluator == EVALUATOR:
        from .mot import MotAccumulator
    else:
        raise ValueError("unsupported metric evaluator")
    return MotAccumulator(iou_threshold=0.5)
