"""Tunable parameters for the tracker, in one typed place."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TrackerConfig:
    """Configuration for :class:`~visiontrack.tracking.tracker.ByteTracker`.

    Defaults are sensible for ~30 fps pedestrian-scale video and match the
    synthetic scene's characteristics.
    """

    # -- association thresholds -----------------------------------------
    high_score_thresh: float = 0.5
    """Detections at/above this confidence enter the first association stage."""

    low_score_thresh: float = 0.1
    """Detections in ``[low, high)`` are used only for the recovery stage."""

    match_iou_thresh: float = 0.3
    """Minimum IoU for a first-stage (high-score) match to be accepted."""

    recovery_iou_thresh: float = 0.5
    """Minimum IoU for the second-stage (low-score) recovery match. Stricter,
    because low-score detections are less trustworthy."""

    new_track_thresh: float = 0.6
    """Only unmatched detections above this confidence spawn a new track."""

    # -- lifecycle -------------------------------------------------------
    n_init: int = 3
    """Consecutive matched frames required to confirm a tentative track."""

    max_age: int = 30
    """Frames a confirmed track may coast unmatched before deletion."""

    # -- gating ----------------------------------------------------------
    use_mahalanobis_gating: bool = True
    """Reject associations whose Mahalanobis distance exceeds the chi-square
    gate, in addition to the IoU threshold."""

    class_aware: bool = True
    """Forbid matching a track to a detection of a different class."""

    def __post_init__(self) -> None:
        if not (0 <= self.low_score_thresh <= self.high_score_thresh <= 1):
            raise ValueError("require 0 <= low_score_thresh <= high_score_thresh <= 1")
        if self.n_init < 1:
            raise ValueError("n_init must be >= 1")
        if self.max_age < 1:
            raise ValueError("max_age must be >= 1")
