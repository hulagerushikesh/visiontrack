"""Evaluation: CLEAR-MOT, IDF1 and HOTA metrics for measuring tracker quality."""
from __future__ import annotations

from .calibration import CalibrationResult, innovation_chi2_samples, reliability_curve
from .hota import HotaResult, IdentityResult, compute_hota, compute_identity
from .mot import MotAccumulator, MotMetrics, evaluate_sequence
from .stats import Comparison, Summary, compare, summarize

__all__ = [
    "MotAccumulator",
    "MotMetrics",
    "evaluate_sequence",
    "compute_hota",
    "compute_identity",
    "HotaResult",
    "IdentityResult",
    "Summary",
    "Comparison",
    "summarize",
    "compare",
    "innovation_chi2_samples",
    "reliability_curve",
    "CalibrationResult",
]
