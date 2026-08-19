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
        scale = self.cfg.kf_noise_scale
        self.kf = KalmanBoxTracker(
            std_weight_position=(1.0 / 20.0) * scale,
            std_weight_velocity=(1.0 / 160.0) * scale,
        )
        self._weights = self.cfg.cost_weights()
        self.tracks: list[Track] = []
        self._next_id = 1
        self._frame = -1
        self._gate = chi2_gating_threshold(dof=4)
        # RQ2: optional learned motion residual (lazy — no-op when path is None).
        from .motion.residual import MotionResidual

        self._residual = MotionResidual.from_path(self.cfg.motion_residual_path)

    def _predict_all(self) -> None:
        """Advance every track's Kalman state one step in a single batched call.

        Equivalent to calling ``track.predict()`` on each track (the filter maths
        is bit-identical whether a state is advanced alone or stacked with
        others), but replaces the per-track Python loop over ``kf.predict`` with
        one ``(N, 8)`` / ``(N, 8, 8)`` batched predict — the per-frame hot path.
        """
        tracks = self.tracks
        if not tracks:
            return
        means = np.stack([t.mean for t in tracks])
        covs = np.stack([t.covariance for t in tracks])
        means, covs = self.kf.predict(means, covs)
        for i, t in enumerate(tracks):
            t.mean = means[i]
            t.covariance = covs[i]
            t.age += 1
            t.time_since_update += 1

    def _apply_residual(self, track: Track) -> None:
        """Correct a track's just-predicted centre with the learned residual (RQ2).

        No-op unless a residual model is loaded. Uses the track's observed centre
        history and its predicted box height as the scale; nudges the xyah mean's
        centre (``mean[0:2]``) by the residual, leaving covariance/velocity alone.
        """
        if self._residual.model is None or len(track.history) < 2:
            return
        centers = np.array([[(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0]
                            for b in track.history])
        corr = self._residual.correct(centers, float(track.mean[3]))
        track.mean[0] += corr[0]
        track.mean[1] += corr[1]

    def _apply_camera_shift(self, track: Track, shift) -> None:
        """Shift a track's predicted centre by the camera translation (RQ4 GMC).

        The Kalman prediction assumes a static camera; on a moving camera the
        whole scene translates by ``shift = (sx, sy)`` px, so we add it to the
        predicted centre (``mean[0:2]``) to keep the box on its object.
        """
        track.mean[0] += shift[0]
        track.mean[1] += shift[1]

    # -- public API -------------------------------------------------------
    def update(
        self, detections: list[Detection], camera_shift=None
    ) -> list[TrackObservation]:
        """Advance the tracker by one frame and return confirmed observations.

        ``camera_shift`` is an optional ``(sx, sy)`` global camera translation for
        this frame (RQ4 GMC); applied to every track's prediction when
        ``use_gmc`` is set. ``None`` keeps the static-camera behaviour.
        """
        self._frame += 1

        do_gmc = self.cfg.use_gmc and camera_shift is not None
        self._predict_all()
        for track in self.tracks:
            self._apply_residual(track)
            if do_gmc:
                self._apply_camera_shift(track, camera_shift)

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
            track_means = np.stack([t.mean for t in tracks])
            track_covs = np.stack([t.covariance for t in tracks])
            gating_d2 = self.kf.gating_distance_batch(track_means, track_covs, det_xyah)
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

        # Observation-centric momentum (OC-SORT, H1.2) — rewards matches aligned
        # with the track's observed direction of motion. Inert without w_ocm.
        momentum = None
        if weights.momentum_on:
            from .motion.oc import momentum_cost

            momentum = momentum_cost(tracks, det_boxes, self.cfg.ocm_delta_t)

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
            momentum=momentum,
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
        # OC-SORT ORU: if this track was lost for >1 frame, rebuild its state
        # along a virtual trajectory between its last observation and this one,
        # undoing the drift accumulated while coasting. Read last_observation
        # *before* update() overwrites it.
        state = None
        if self.cfg.use_oru and track.time_since_update > 1:
            from ..core.geometry import xyxy_to_xyah
            from .motion.oc import observation_centric_reupdate

            start_mean, start_cov = track.last_obs_state
            state = observation_centric_reupdate(
                self.kf,
                start_mean,
                start_cov,
                track.last_observation,
                xyxy_to_xyah(det.xyxy),
                track.time_since_update,
            )
        track.update(det.xyxy, det.class_id, det.score, feature=det.feature, state=state)

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
                feature=det.feature,
                ema_alpha=self.cfg.appearance_ema_alpha,
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
