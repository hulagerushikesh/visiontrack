"""The Track object and its lifecycle state machine.

A track represents one hypothesised object identity persisting across frames.
Its lifecycle guards against two failure modes:

* **False starts** — a spurious detection should not immediately create a
  confirmed identity. New tracks are ``TENTATIVE`` and must be matched on
  ``n_init`` consecutive frames before being ``CONFIRMED``.
* **Flicker** — a confirmed object briefly lost to occlusion should not lose
  its ID. A track survives up to ``max_age`` unmatched frames (coasting on the
  Kalman prediction) before being ``DELETED``.
"""
from __future__ import annotations

import enum

import numpy as np

from ..core.geometry import xyah_to_xyxy, xyxy_to_xyah
from ..core.kalman import KalmanBoxTracker

__all__ = ["TrackState", "Track"]


class TrackState(enum.IntEnum):
    TENTATIVE = 0  # newly created, not yet confirmed
    CONFIRMED = 1  # matched enough times to be a real identity
    DELETED = 2    # lost; scheduled for removal


class Track:
    """A single tracked object backed by a Kalman state estimate."""

    __slots__ = (
        "track_id",
        "kf",
        "mean",
        "covariance",
        "state",
        "class_id",
        "score",
        "hits",
        "age",
        "time_since_update",
        "n_init",
        "max_age",
        "start_frame",
        "history",
    )

    def __init__(
        self,
        track_id: int,
        detection_xyxy: np.ndarray,
        kf: KalmanBoxTracker,
        class_id: int = -1,
        score: float = 1.0,
        n_init: int = 3,
        max_age: int = 30,
        start_frame: int = 0,
    ) -> None:
        self.track_id = track_id
        self.kf = kf
        self.mean, self.covariance = kf.initiate(xyxy_to_xyah(detection_xyxy))
        self.state = TrackState.TENTATIVE
        self.class_id = class_id
        self.score = score

        self.hits = 1              # total number of matched updates
        self.age = 1               # total frames since creation
        self.time_since_update = 0  # frames since last matched update
        self.n_init = n_init
        self.max_age = max_age
        self.start_frame = start_frame
        self.history: list[np.ndarray] = [self.to_xyxy()]

    # -- geometry accessors ----------------------------------------------
    def to_xyah(self) -> np.ndarray:
        return self.mean[:4].copy()

    def to_xyxy(self) -> np.ndarray:
        return xyah_to_xyxy(self.mean[:4])

    # -- filter steps -----------------------------------------------------
    def predict(self) -> None:
        """Advance the Kalman state; called once per frame for every track."""
        self.mean, self.covariance = self.kf.predict(self.mean, self.covariance)
        self.age += 1
        self.time_since_update += 1

    def update(self, detection_xyxy: np.ndarray, class_id: int, score: float) -> None:
        """Correct the state with a matched detection and promote if ready."""
        self.mean, self.covariance = self.kf.update(
            self.mean, self.covariance, xyxy_to_xyah(detection_xyxy)
        )
        self.class_id = class_id
        self.score = score
        self.hits += 1
        self.time_since_update = 0
        self.history.append(self.to_xyxy())

        if self.state == TrackState.TENTATIVE and self.hits >= self.n_init:
            self.state = TrackState.CONFIRMED

    def mark_missed(self) -> None:
        """Handle a frame with no matching detection."""
        if self.state == TrackState.TENTATIVE:
            # Unconfirmed tracks are fragile: one miss kills them.
            self.state = TrackState.DELETED
        elif self.time_since_update > self.max_age:
            self.state = TrackState.DELETED

    # -- state predicates -------------------------------------------------
    @property
    def is_tentative(self) -> bool:
        return self.state == TrackState.TENTATIVE

    @property
    def is_confirmed(self) -> bool:
        return self.state == TrackState.CONFIRMED

    @property
    def is_deleted(self) -> bool:
        return self.state == TrackState.DELETED

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"Track(id={self.track_id}, state={self.state.name}, "
            f"hits={self.hits}, tsu={self.time_since_update})"
        )
