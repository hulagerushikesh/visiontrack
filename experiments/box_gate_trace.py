"""Opt-in in-memory observation tool; not a study runner or held-out entry.

Capture actual Python frame locals, never recompute costs or patch the tracker.
Tests use authored sequences, not the retained development/held-out grids.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import threading
from dataclasses import asdict

import numpy as np

from visiontrack.core.assignment import associate
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.cost import build_association_cost
from visiontrack.tracking.track import Track
from visiontrack.tracking.tracker import ByteTracker

MAX_FRAMES = 300
MAX_SELECTED = 128
MAX_OBJECTS = 32
MAX_EVENTS = 4096
STAGES = ("confirmed_high", "confirmed_low_recovery", "tentative_leftover_high")


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def selected_frames(crossing_times=()):
    """Fixed startup/pulse windows plus brackets of ALL saved predicted crossings.

    Supply the union across both variants, including matched and extra crossings.
    The future development runner must verify those inputs against saved evidence.
    """
    if not isinstance(crossing_times, (list, tuple)) or len(crossing_times) > 1200:
        raise ValueError("bounded saved crossing times required")
    frames = set(range(4)) | set(range(133, 168)) | set(range(208, 243))
    for time in crossing_times:
        if type(time) not in (float, int) or not math.isfinite(time) or not 0 <= time <= 299:
            raise ValueError("crossing time must be finite and within the frame grid")
        bracket = math.floor(time)
        frames.update(range(max(0, bracket - 1), min(300, bracket + 3)))
    if len(frames) > MAX_SELECTED:
        raise ValueError("trace frame budget exceeded; do not silently truncate")
    return sorted(frames)


def _array(value):
    if value is None:
        return None
    array = np.asarray(value)
    if array.size > MAX_OBJECTS * MAX_OBJECTS or not np.isfinite(array).all():
        raise ValueError("oversized or nonfinite trace array")
    return array.tolist()


def _state(track):
    return dict(
        track_id=track.track_id, state=track.state.name, age=track.age,
        score=track.score, class_id=track.class_id,
        hits=track.hits, time_since_update=track.time_since_update,
        mean=_array(track.mean), covariance=_array(track.covariance),
        xyxy=_array(track.to_xyxy()),
    )


def _states(tracks):
    if len(tracks) > MAX_OBJECTS:
        raise ValueError("track budget exceeded")
    return [_state(track) for track in tracks]


def _rows(observations):
    return [dict(
        frame=o.frame, track_id=o.track_id, xyxy=_array(o.xyxy),
        score=o.score, class_id=o.class_id,
    ) for o in observations]


class ParityMismatch(ValueError):
    """Do not interpret failed tracing. Retain this diagnostic in a future runner."""

    def __init__(self, diagnostic):
        super().__init__("traced public output differs: stop; no interpretation permitted")
        self.diagnostic = diagnostic


class _Observer:
    def __init__(self, tracker, detections, frame, events):
        self.tracker, self.frame, self.events = tracker, frame, events
        self.ordinals = {id(det): i for i, det in enumerate(detections)}
        self.stages = 0
        self.active = {}
        self.codes = {getattr(ByteTracker, name).__code__: name for name in (
            "_match", "_apply_match", "_spawn", "_predict_all",
        )}
        self.codes[Track.mark_missed.__code__] = "mark_missed"

    def add(self, **event):
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("trace event budget exceeded")
        self.events.append(dict(frame=self.frame, **event))

    def __call__(self, frame, event, result):
        # Capture the ACTUAL mask and solver proposals, not a reconstructed gate.
        parent = frame.f_back
        if (event == "return" and parent is not None
                and parent.f_code is ByteTracker._match.__code__
                and parent.f_locals.get("self") is self.tracker):
            local = frame.f_locals
            if frame.f_code is build_association_cost.__code__:
                self.add(kind="cost_build", forbidden=_array(local["forbidden"]),
                         cost=_array(result[0]), max_cost=result[1])
            elif frame.f_code is associate.__code__:
                self.add(kind="assignment", proposed_rows=_array(local.get("row_ind")),
                         proposed_columns=_array(local.get("col_ind")))
        name = self.codes.get(frame.f_code)
        if name is None or event not in ("call", "return"):
            return
        local = frame.f_locals
        owner = local.get("self")
        if owner is not self.tracker and not (
            name == "mark_missed" and any(owner is t for t in self.tracker.tracks)
        ):
            return
        if event == "call":
            if name == "_match":
                if self.stages >= len(STAGES):
                    raise ValueError("unexpected association call count")
                stage = STAGES[self.stages]
                self.stages += 1
                if len(local["dets"]) > MAX_OBJECTS:
                    raise ValueError("detection budget exceeded")
                before = dict(
                    stage=stage, tracks=_states(local["tracks"]),
                    detection_ordinals=[self.ordinals[id(d)] for d in local["dets"]],
                    iou_threshold=local["iou_thresh"], gate_requested=local["gate"],
                )
            elif name == "_apply_match":
                before = dict(track=_state(local["track"]),
                              detection_ordinal=self.ordinals[id(local["det"])])
            elif name == "mark_missed":
                before = dict(track=_state(owner))
            else:
                before = dict(tracks=_states(self.tracker.tracks))
                if name == "_spawn":
                    before["detection_ordinal"] = self.ordinals[id(local["det"])]
            self.active[id(frame)] = before
            return
        before = self.active.pop(id(frame))
        if name == "_match":
            if result is None:
                raise ValueError("association did not return normally")
            # These are copies of the exact matrices used, not new evaluations.
            matrices = {key: _array(local.get(key)) for key in (
                "ious", "class_mismatch", "gating_d2", "cost",
            )}
            self.add(kind="association", before=before, matrices=matrices,
                     gate_threshold=local.get("gate_thresh"),
                     max_cost=local.get("max_cost"),
                     matches=_array(result[0]), unmatched_tracks=_array(result[1]),
                     unmatched_detections=_array(result[2]))
        else:
            after = (_state(local["track"]) if name == "_apply_match" else
                     _state(owner) if name == "mark_missed" else
                     _states(self.tracker.tracks))
            self.add(kind=name, before=before, after=after)


def observe_sequence(tracker, detection_frames, *, frames, expected_output):
    """Run authored/test inputs or a future verified DEV replay, checking every row.

    No file reads/writes, generator, scorer, reset or configuration overrides.
    This is NOT a provenance verifier; a runner must authenticate saved inputs and
    expected output first. On any error discard this tracker; never resume it.
    """
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("main-thread isolated diagnostic only")
    if sys.getprofile() is not None or sys.gettrace() is not None:
        raise ValueError("existing profiler/debugger: do not replace it")
    if type(tracker) is not ByteTracker or tracker.frame_index != -1 or tracker.tracks:
        raise ValueError("fresh exact ByteTracker required")
    baseline = asdict(TrackerConfig())
    settings = asdict(tracker.cfg)
    baseline["use_mahalanobis_gating"] = settings["use_mahalanobis_gating"]
    if _bytes(settings) != _bytes(baseline) or type(settings["use_mahalanobis_gating"]) is not bool:
        raise ValueError("only baseline or gate-off settings supported")
    if type(detection_frames) is not list or not 1 <= len(detection_frames) <= MAX_FRAMES:
        raise ValueError("bounded explicit frame list required")
    if (type(frames) is not list or not frames or len(frames) > MAX_SELECTED
            or any(type(f) is not int or not 0 <= f < len(detection_frames) for f in frames)
            or frames != sorted(set(frames))):
        raise ValueError("sorted unique bounded selected frames required")
    if type(expected_output) is not list or len(expected_output) > MAX_FRAMES * MAX_OBJECTS:
        raise ValueError("bounded expected public rows required")
    expected_bytes = _bytes(expected_output)  # Validate BEFORE the first update.
    # Features are deliberately absent: no private pixels or embeddings observed.
    for detections in detection_frames:
        if (type(detections) is not list or len(detections) > MAX_OBJECTS
                or len({id(d) for d in detections}) != len(detections)):
            raise ValueError("bounded distinct detections required")
        for det in detections:
            if (type(det) is not Detection or det.feature is not None
                    or not np.isfinite(det.xyxy).all()
                    or not (det.xyxy[2:] > det.xyxy[:2]).all()
                    or type(det.score) is not float or not math.isfinite(det.score)
                    or not 0 <= det.score <= 1 or type(det.class_id) is not int):
                raise ValueError("finite feature-free detections required")
    events, output = [], []
    handed = hashlib.sha256()
    for index, detections in enumerate(detection_frames):
        # Fingerprint the actual payload immediately BEFORE every update,
        # including frames not selected for detailed internal snapshots.
        handed.update(_bytes(dict(frame=index, detections=[dict(
            xyxy=_array(d.xyxy), score=d.score, class_id=d.class_id, feature=None,
        ) for d in detections])) + b"\n")
        if len(tracker.tracks) > MAX_OBJECTS:
            raise ValueError("track budget exceeded")
        if index not in frames:
            observations = tracker.update(detections)
            if len(tracker.tracks) > MAX_OBJECTS:
                raise ValueError("track budget exceeded")
            output.extend(_rows(observations))
            continue
        observer = _Observer(tracker, detections, index, events)
        observer.add(kind="frame_start", tracks=_states(tracker.tracks),
                     detections=[dict(ordinal=i, xyxy=_array(d.xyxy), score=d.score,
                                      class_id=d.class_id) for i, d in enumerate(detections)])
        try:
            sys.setprofile(observer)
            observations = tracker.update(detections)
        finally:
            sys.setprofile(None)
        if observer.stages != 3 or observer.active:
            raise ValueError("incomplete observed frame; discard tracker")
        batch = _rows(observations)
        output.extend(batch)
        observer.add(kind="frame_end", tracks=_states(tracker.tracks), public_output=batch)
    if asdict(tracker.cfg) != settings:
        raise ValueError("configuration changed during trace")
    actual_bytes = _bytes(output)
    matches = actual_bytes == expected_bytes
    diagnostic = dict(
        format="visiontrack.box-gate-internal-trace/v1", settings=settings,
        frame_count=len(detection_frames), selected_frames=frames.copy(),
        public_output=output, events=events,
        expected_output_sha256=hashlib.sha256(expected_bytes).hexdigest(),
        actual_output_sha256=hashlib.sha256(actual_bytes).hexdigest(),
        detection_payload_sha256=handed.hexdigest(),
        exact_public_output_parity=matches, interpretation_allowed=False,
        provenance_verified=False, validation_evidence=False,
    )
    # Return detached JSON-compatible snapshots; no live tracker references.
    diagnostic = json.loads(_bytes(diagnostic))
    if not matches:
        raise ParityMismatch(diagnostic)
    return diagnostic
