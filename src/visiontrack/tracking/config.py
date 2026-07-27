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

    # -- association cost (the ablation surface, see tracking/cost.py) ----
    w_iou: float = 1.0
    """Weight of the motion (IoU/GIoU) term in the association cost."""

    w_app: float = 0.0
    """Weight of the appearance (re-ID cosine) term. 0 disables it (RQ1)."""

    w_unc: float = 0.0
    """Weight of the soft Kalman-uncertainty term. 0 disables it (RQ3)."""

    use_giou: bool = False
    """Use ``1 − GIoU`` instead of ``1 − IoU`` for the motion term."""

    appearance_ema_alpha: float = 0.9
    """EMA memory for a track's appearance gallery (higher = smoother)."""

    kf_noise_scale: float = 1.0
    """Scale on the Kalman filter's position/velocity noise. <1 shrinks the
    covariance (a more *confident* filter, tighter gate). Used to calibrate the
    filter, which on real MOT17 is badly under-confident (RQ3)."""

    motion_residual_path: str | None = None
    """Path to a from-scratch learned motion-residual ``.npz`` (RQ2). When set,
    the predicted centre is corrected by the residual before association. ``None``
    keeps the pure constant-velocity Kalman prediction (behaviour unchanged)."""

    # -- observation-centric mechanics (OC-SORT, H1.2) -------------------
    w_ocm: float = 0.0
    """Weight of the observation-centric momentum term (OC-SORT's OCM). 0 disables
    it. Like the other soft terms it only *ranks* feasible (in-gate) pairs."""

    ocm_delta_t: int = 3
    """Frame span used to estimate a track's observed velocity direction for OCM."""

    use_oru: bool = False
    """Observation-centric re-update (OC-SORT's ORU): on re-match after an
    occlusion gap, rebuild the track state along a virtual trajectory between the
    last and new observations. ``False`` keeps the plain Kalman update."""

    def __post_init__(self) -> None:
        if not (0 <= self.low_score_thresh <= self.high_score_thresh <= 1):
            raise ValueError("require 0 <= low_score_thresh <= high_score_thresh <= 1")
        if self.n_init < 1:
            raise ValueError("n_init must be >= 1")
        if self.max_age < 1:
            raise ValueError("max_age must be >= 1")
        if min(self.w_iou, self.w_app, self.w_unc, self.w_ocm) < 0:
            raise ValueError("cost weights must be non-negative")
        if self.ocm_delta_t < 1:
            raise ValueError("ocm_delta_t must be >= 1")

    def cost_weights(self):
        """Return the :class:`~visiontrack.tracking.cost.CostWeights` view."""
        from .cost import CostWeights

        return CostWeights(
            w_iou=self.w_iou, w_app=self.w_app, w_unc=self.w_unc,
            w_ocm=self.w_ocm, use_giou=self.use_giou,
        )
