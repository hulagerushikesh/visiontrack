"""Offline, geometry-only continuity warning; no tracker state or ground truth access.

This module defines the v1 candidate before the prospective tracker study runs.
Call ``inspect`` before a frame's tracker update, then ``advance`` with that
frame's *public* observations. It cannot infer a physical person's identity.
"""
from __future__ import annotations

import hashlib
import json
from collections import deque
from numbers import Integral

import numpy as np

from visiontrack.detection.base import Detection
from visiontrack.tracking.tracker import TrackObservation

MIN_SCORE = 0.1
MIN_IOU = 0.3
REASON = "insufficient_distinct_box_support"


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _integer(value: object, name: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, Integral) or isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer (not bool)")
    number = int(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _score(value: object) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)):
        raise ValueError("score must be finite in [0,1]")
    number = float(value)
    if not np.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("score must be finite in [0,1]")
    return number


def _box(value: object) -> list[float]:
    if not isinstance(value, np.ndarray) or value.dtype != np.float64 or value.shape != (4,):
        raise ValueError("xyxy must be a float64 array of shape (4,)")
    if not bool(np.isfinite(value).all()) or not bool((value[2:] > value[:2]).all()):
        raise ValueError("xyxy must have finite coordinates and positive area")
    return value.tolist()


def _iou(first: list[float], second: list[float]) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    overlap = width * height
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    return overlap / (first_area + second_area - overlap)


def _snapshot(observations: list[TrackObservation], frame: int) -> list[dict]:
    copied = []
    for obs in observations:
        if not isinstance(obs, TrackObservation):
            raise ValueError("public TrackObservation required")
        if _integer(obs.frame, "observation frame", minimum=0) != frame:
            raise ValueError("public observation frame mismatch")
        copied.append(dict(frame=frame, track_id=_integer(obs.track_id, "track ID", minimum=1),
                           xyxy=_box(obs.xyxy), score=_score(obs.score),
                           class_id=_integer(obs.class_id, "class ID")))
    copied.sort(key=lambda row: row["track_id"])
    ids = [row["track_id"] for row in copied]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate public track IDs")
    return copied


def _detections(detections: list[Detection]) -> list[dict]:
    copied = []
    for index, det in enumerate(detections):
        if not isinstance(det, Detection):
            raise ValueError("Detection required")
        if det.feature is not None:
            raise ValueError("appearance feature is outside observer input contract")
        score = _score(det.score)
        row = dict(row_index=index, xyxy=_box(det.xyxy), score=score,
                   class_id=_integer(det.class_id, "class ID"))
        copied.append(row)
    return copied


def _matching(track_ids: list[int], row_indices: list[int],
              neighbours: dict[int, list[int]]) -> list[list[int]]:
    """Deterministic maximum-cardinality bipartite matching witness."""
    owner: dict[int, int] = {}
    allowed = set(row_indices)

    def augment(track: int, seen: set[int]) -> bool:
        for row in neighbours[track]:
            if row not in allowed or row in seen:
                continue
            seen.add(row)
            if row not in owner or augment(owner[row], seen):
                owner[row] = track
                return True
        return False

    for track in track_ids:
        augment(track, set())
    return [[owner[row], row] for row in sorted(owner)]


def _components(neighbours: dict[int, list[int]]) -> list[dict]:
    reverse: dict[int, list[int]] = {}
    for track, rows in neighbours.items():
        for row in rows:
            reverse.setdefault(row, []).append(track)
    visited_tracks: set[int] = set()
    results = []
    for start in sorted(neighbours):
        if start in visited_tracks or not neighbours[start]:
            continue
        queue = deque([start])
        tracks: set[int] = set()
        rows: set[int] = set()
        while queue:
            track = queue.popleft()
            if track in tracks:
                continue
            tracks.add(track)
            visited_tracks.add(track)
            for row in neighbours[track]:
                rows.add(row)
                queue.extend(reverse[row])
        track_ids, row_indices = sorted(tracks), sorted(rows)
        witness = _matching(track_ids, row_indices, neighbours)
        results.append(dict(track_ids=track_ids, row_indices=row_indices,
                            maximum_matching_cardinality=len(witness),
                            deficit=len(track_ids) - len(witness), matching_witness=witness))
    return results


class ContinuityObserver:
    """One-frame public-output memory; inspect before, advance after each update."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._next_frame = 0
        self._previous: list[dict] = []
        self._awaiting_advance = False

    def inspect(self, frame: int, detections: list[Detection]) -> dict:
        frame = _integer(frame, "frame", minimum=0)
        if frame != self._next_frame or self._awaiting_advance:
            raise ValueError("nonconsecutive frame or missing public advance")
        current = _detections(detections)
        eligible = [row for row in current if row["score"] >= MIN_SCORE]
        neighbours: dict[int, list[int]] = {r["track_id"]: [] for r in self._previous}
        edges = []
        for previous in self._previous:
            for row in eligible:
                if previous["class_id"] != row["class_id"]:
                    continue
                overlap = _iou(previous["xyxy"], row["xyxy"])
                if overlap >= MIN_IOU:
                    neighbours[previous["track_id"]].append(row["row_index"])
                    edges.append(dict(track_id=previous["track_id"],
                                      row_index=row["row_index"], iou=overlap))
        components = _components(neighbours)
        warnings = [dict(reason=REASON, **component) for component in components
                    if len(component["track_ids"]) >= 2 and component["deficit"] > 0]
        record = dict(frame=frame, previous_fingerprint=_fingerprint(self._previous),
                      detections_fingerprint=_fingerprint(current),
                      previous_count=len(self._previous), eligible_count=len(eligible),
                      edges=edges, unsupported_track_ids=sorted(
                          track for track, rows in neighbours.items() if not rows),
                      components=components, warnings=warnings,
                      two_supported_previous_tracks=sum(bool(rows) for rows in
                                                        neighbours.values()) >= 2,
                      assessment_opportunity=bool(self._previous))
        self._awaiting_advance = True
        return record

    def advance(self, frame: int, observations: list[TrackObservation]) -> None:
        frame = _integer(frame, "frame", minimum=0)
        if frame != self._next_frame or not self._awaiting_advance:
            raise ValueError("public advance must follow inspect at the same frame")
        copied = _snapshot(observations, frame)
        self._previous = copied
        self._next_frame += 1
        self._awaiting_advance = False
