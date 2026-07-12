"""ByteTrack-style multi-object tracker.

The tracker ties the pieces together into the standard tracking-by-detection
loop: *predict* every track forward with the Kalman filter, *associate*
detections to tracks by solving a gated linear-assignment problem, then
*update / create / delete* tracks according to the lifecycle rules.

The association follows the key idea of ByteTrack: rather than throwing away
low-confidence detections, run a **two-stage** match.

1. **High-score stage.** Confident detections are matched to all active
   tracks using an IoU cost, gated by both a minimum IoU and (optionally) the
   Kalman Mahalanobis distance.
2. **Recovery stage.** Tracks still unmatched are given a second chance
   against the *low*-confidence detections. Objects under partial occlusion
   often survive only as weak detections; recovering them here is what keeps
   IDs stable through crowds — the single biggest win over plain SORT.

Tentative (unconfirmed) tracks are matched last and only against leftover
high-score detections, so noise cannot bootstrap a stable identity.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.assignment import associate
from ..core.geometry import iou_matrix, xyxy_to_xyah
from ..core.kalman import KalmanBoxTracker, chi2_gating_threshold
from ..detection.base import Detection, detections_to_array
from .config import TrackerConfig
from .cost import (
    appearance_distance,
    build_association_cost,
    motion_distance,
    uncertainty_distance,
)
from .track import Track

__all__ = ["ByteTracker", "TrackObservation"]


@dataclass(slots=True)
class TrackObservation:
    """One confirmed track's box at one frame — the tracker's public output."""

    frame: int
    track_id: int
    xyxy: np.ndarray
    score: float
    class_id: int


class ByteTracker:
    """Online multi-object tracker.

    Usage::

        tracker = ByteTracker()
        for detections in stream:
            observations = tracker.update(detections)
    """

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self.cfg = config or TrackerConfig()
        self.kf = KalmanBoxTracker()
        self._weights = self.cfg.cost_weights()
        self.tracks: list[Track] = []
        self._next_id = 1
        self._frame = -1
        self._gate = chi2_gating_threshold(dof=4)

    # -- public API -------------------------------------------------------
    def update(self, detections: list[Detection]) -> list[TrackObservation]:
        """Advance the tracker by one frame and return confirmed observations."""
        self._frame += 1

        for track in self.tracks:
            track.predict()

        high = [d for d in detections if d.score >= self.cfg.high_score_thresh]
        low = [
            d
            for d in detections
            if self.cfg.low_score_thresh <= d.score < self.cfg.high_score_thresh
        ]

        confirmed = [t for t in self.tracks if t.is_confirmed]
        tentative = [t for t in self.tracks if t.is_tentative]

        # -- Stage 1: confirmed tracks vs high-score detections ----------
        matches, un_tracks_idx, un_high_idx = self._match(
            confirmed, high, self.cfg.match_iou_thresh, gate=True
        )
        for ti, di in matches:
            self._apply_match(confirmed[ti], high[di])
        remaining_confirmed = [confirmed[i] for i in un_tracks_idx]

        # -- Stage 2: recover remaining confirmed tracks with low dets ---
        matches2, un_tracks2_idx, _ = self._match(
            remaining_confirmed, low, self.cfg.recovery_iou_thresh, gate=False
        )
        for ti, di in matches2:
            self._apply_match(remaining_confirmed[ti], low[di])
        lost_confirmed = [remaining_confirmed[i] for i in un_tracks2_idx]

        # -- Stage 3: tentative tracks vs leftover high-score dets -------
        leftover_high = [high[i] for i in un_high_idx]
        matches3, un_tent_idx, un_high2_idx = self._match(
            tentative, leftover_high, self.cfg.match_iou_thresh, gate=True
        )
        for ti, di in matches3:
            self._apply_match(tentative[ti], leftover_high[di])
        lost_tentative = [tentative[i] for i in un_tent_idx]

        # -- lifecycle bookkeeping ---------------------------------------
        for track in lost_confirmed + lost_tentative:
            track.mark_missed()

        for di in un_high2_idx:
            det = leftover_high[di]
            if det.score >= self.cfg.new_track_thresh:
                self._spawn(det)

        self.tracks = [t for t in self.tracks if not t.is_deleted]
        return self._observations()

    def reset(self) -> None:
        """Clear all state (start a fresh sequence)."""
        self.tracks.clear()
        self._next_id = 1
        self._frame = -1

    @property
    def frame_index(self) -> int:
        return self._frame

    # -- association helpers ---------------------------------------------
    def _match(
        self,
        tracks: list[Track],
        dets: list[Detection],
        iou_thresh: float,
        gate: bool,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Gated IoU association between ``tracks`` and ``dets``.

        Returns ``(matches, unmatched_track_idx, unmatched_det_idx)`` where
        ``matches`` is a ``(k, 2)`` array of ``(track_index, det_index)``.
        """
        if not tracks or not dets:
            return (
                np.empty((0, 2), dtype=np.int64),
                np.arange(len(tracks), dtype=np.int64),
                np.arange(len(dets), dtype=np.int64),
            )

        track_boxes = np.stack([t.to_xyxy() for t in tracks])
        det_boxes = detections_to_array(dets)
        ious = iou_matrix(track_boxes, det_boxes)  # (T, D)

        weights = self._weights

        # Motion term: GIoU only when requested, else the plain 1 - IoU that
        # build_association_cost would default to (kept None to stay identical).
        motion = (
            motion_distance(track_boxes, det_boxes, use_giou=True)
            if weights.use_giou
            else None
        )

        # Forbidden class pairings (-1 == class-agnostic, matches anything).
        class_mismatch = None
        if self.cfg.class_aware:
            det_classes = np.array([d.class_id for d in dets])
            track_classes = np.array([t.class_id for t in tracks])
            class_mismatch = (
                (track_classes[:, None] != det_classes[None, :])
                & (track_classes[:, None] != -1)
                & (det_classes[None, :] != -1)
            )

        # Kalman gating distances — needed to gate, and/or for the soft
        # uncertainty term when it is switched on.
        gating_d2 = None
        gate_thresh = None
        want_gate = gate and self.cfg.use_mahalanobis_gating
        if want_gate or weights.uncertainty_on:
            det_xyah = xyxy_to_xyah(det_boxes)
            gating_d2 = np.stack(
                [self.kf.gating_distance(t.mean, t.covariance, det_xyah) for t in tracks]
            )
            if want_gate:
                gate_thresh = self._gate

        uncertainty = (
            uncertainty_distance(gating_d2, self._gate)
            if weights.uncertainty_on and gating_d2 is not None
            else None
        )

        # Appearance term (RQ1) — inert until tracks/detections carry
        # embeddings; kept as a hook so the surface is complete.
        appearance = self._appearance_matrix(tracks, dets) if weights.appearance_on else None

        cost, max_cost = build_association_cost(
            ious,
            weights,
            iou_thresh,
            motion=motion,
            class_mismatch=class_mismatch,
            gating_d2=gating_d2,
            gate_thresh=gate_thresh,
            appearance=appearance,
            uncertainty=uncertainty,
        )
        return associate(cost, max_cost)

    def _appearance_matrix(self, tracks, dets):
        """Appearance cost hook. Returns ``(T, D)`` cosine distances if both
        sides carry embeddings, else ``None`` (the term is then skipped).

        The per-track appearance gallery lands in Phase 3; until then tracks
        have no feature and this returns ``None``.
        """
        track_feats = [getattr(t, "feature", None) for t in tracks]
        det_feats = [d.feature for d in dets]
        if any(f is None for f in track_feats) or any(f is None for f in det_feats):
            return None
        return appearance_distance(np.stack(track_feats), np.stack(det_feats))

    def _apply_match(self, track: Track, det: Detection) -> None:
        track.update(det.xyxy, det.class_id, det.score)

    def _spawn(self, det: Detection) -> None:
        self.tracks.append(
            Track(
                track_id=self._next_id,
                detection_xyxy=det.xyxy,
                kf=self.kf,
                class_id=det.class_id,
                score=det.score,
                n_init=self.cfg.n_init,
                max_age=self.cfg.max_age,
                start_frame=self._frame,
            )
        )
        self._next_id += 1

    def _observations(self) -> list[TrackObservation]:
        out: list[TrackObservation] = []
        for t in self.tracks:
            # Report confirmed tracks, and confirmed tracks that are briefly
            # coasting (still fresh) so downstream consumers see continuity.
            if t.is_confirmed and t.time_since_update == 0:
                out.append(
                    TrackObservation(
                        frame=self._frame,
                        track_id=t.track_id,
                        xyxy=t.to_xyxy(),
                        score=t.score,
                        class_id=t.class_id,
                    )
                )
        return out
