"""Read-only lifecycle diagnosis of an existing, verified Lab run.

The observer delegates every match and birth to ByteTracker. It records actual
decisions, not inferred physical identities or a second association algorithm.
"""
from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .. import __version__
from ..tracking.tracker import ByteTracker
from .comparison import load_variant_result
from .contracts import TrackObservationRecord, sha256_json
from .runner import (
    _as_detections,
    _group_detections,
    load_experiment_bundle,
    resolve_variant_config,
)
from .storage import serialize_track_jsonl

MAX_TRACE_FRAMES = 200
MAX_TRACE_ROWS = 20_000
_STAGES = ("confirmed_high", "confirmed_low", "tentative_high")


class _InitiationObserver(ByteTracker):
    """Observe a bounded window while keeping the entire run's warm-up."""

    def __init__(self, config, *, offset: int, start: int, end: int):
        super().__init__(config)
        self.offset, self.start, self.end = offset, start, end
        self.frames: list[dict[str, Any]] = []
        self.row_count = 0
        self._capture = False

    def _match(self, tracks, dets, iou_thresh, gate):
        result = super()._match(tracks, dets, iou_thresh, gate)
        if self._capture:
            if self._stage >= len(_STAGES):
                raise ValueError("diagnostic association-stage contract changed")
            if gate != (self._stage != 1) or any(
                not (track.is_tentative if self._stage == 2 else track.is_confirmed)
                for track in tracks
            ):
                raise ValueError("diagnostic association-stage contract changed")
            stage = _STAGES[self._stage]
            self._stage += 1
            for ti, di in result[0]:
                index = self._indices[id(dets[int(di)])]
                self._decisions[index] = (f"matched_{stage}", tracks[int(ti)].track_id)
        return result

    def _spawn(self, det):
        super()._spawn(det)
        if self._capture:
            self._decisions[self._indices[id(det)]] = (
                "spawned_tentative", self.tracks[-1].track_id,
            )

    def update(self, detections, camera_shift=None):
        frame = self.offset + self.frame_index + 1
        self._capture = self.start <= frame < self.end
        if not self._capture:
            return super().update(detections, camera_shift=camera_shift)
        self._stage = 0
        self._indices = {id(det): index for index, det in enumerate(detections)}
        self._decisions: dict[int, tuple[str, int]] = {}
        # Keep references to removed tracks to observe their actual deleted state.
        previous = {track.track_id: (track, track.state.name.lower()) for track in self.tracks}
        output = super().update(detections, camera_shift=camera_shift)
        if self._stage != 3:
            raise ValueError("diagnostic association-stage contract changed")

        detection_rows = []
        for index, det in enumerate(detections):
            if index in self._decisions:
                disposition, track_id = self._decisions[index]
            else:
                track_id = None
                if det.score < self.cfg.low_score_thresh:
                    disposition = "below_low_score"
                elif det.score < self.cfg.high_score_thresh:
                    disposition = "unmatched_low_score"
                elif det.score < self.cfg.new_track_thresh:
                    disposition = "below_birth_score"
                else:
                    raise ValueError("unaccounted high-score detection in diagnostic")
            detection_rows.append({
                "input_offset": index, "xyxy": [float(v) for v in det.xyxy],
                "score": float(det.score), "class_id": int(det.class_id),
                "disposition": disposition, "track_id": track_id,
            })

        public_ids = {observation.track_id for observation in output}
        matched = {track_id: index for index, (_, track_id) in self._decisions.items()}
        current = {track.track_id: track for track in self.tracks}
        all_tracks = {key: value[0] for key, value in previous.items()} | current
        track_rows = []
        for track_id, track in sorted(all_tracks.items()):
            old_state = previous[track_id][1] if track_id in previous else None
            if old_state is None:
                event = "born"
            elif track.is_deleted:
                event = "deleted_unconfirmed" if old_state == "tentative" else "deleted_expired"
            elif old_state == "tentative" and track.is_confirmed:
                event = "confirmed_now"
            elif track.time_since_update:
                event = "coasting"
            else:
                event = "tentative_match" if track.is_tentative else "updated"
            track_rows.append({
                "track_id": track_id, "previous_state": old_state,
                "state": track.state.name.lower(), "event": event,
                "birth_frame": self.offset + track.start_frame,
                "hits": track.hits, "age": track.age,
                "time_since_update": track.time_since_update,
                "public": track_id in public_ids, "input_offset": matched.get(track_id),
            })
        self.row_count += len(detection_rows) + len(track_rows)
        if self.row_count > MAX_TRACE_ROWS:
            raise ValueError(f"diagnostic exceeds {MAX_TRACE_ROWS} rows; select a smaller window")
        self.frames.append({
            "frame_index": frame, "detections": detection_rows, "tracks": track_rows,
            "public_track_ids": sorted(public_ids),
        })
        return output


def _implementation_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.py"))
    }


def build_initiation_trace(
    bundle: str | Path, *, variant: str, start: int, end: int,
) -> dict[str, Any]:
    """Replay one saved variant, verify exact output parity, return bounded metadata.

    ``start`` is inclusive and ``end`` exclusive, in source-frame coordinates.
    Replay always starts at the experiment boundary, never at the trace window.
    Nothing is written and no pixels, models or external feature files are read.
    """
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end or end - start > MAX_TRACE_FRAMES):
        raise ValueError(f"require an integer trace window of 1–{MAX_TRACE_FRAMES} frames")
    path = Path(bundle)
    experiment, source, records = load_experiment_bundle(path)
    declared = next((item for item in experiment.variants if item["name"] == variant), None)
    if declared is None:
        raise ValueError("variant is not declared in this experiment")
    run_start, run_end = experiment.frame_range["start"], experiment.frame_range["end"]
    if not run_start <= start < end <= run_end:
        raise ValueError("trace window must be inside the experiment frame_range")
    config = resolve_variant_config(declared)
    metadata, _ = load_variant_result(
        path, declared, experiment_id=experiment.experiment_id, source_id=source.source_id,
        detection_sha256=source.detection_sha256, frame_range=experiment.frame_range,
        frame_count=source.frame_count,
    )
    implementation = _implementation_hashes()
    observer = _InitiationObserver(config, offset=run_start, start=start, end=end)
    frames = _group_detections(records, start=run_start, end=run_end)
    observations = []
    for offset, frame_records in enumerate(frames):
        for observation in observer.update(_as_detections(frame_records)):
            observations.append(TrackObservationRecord(
                frame_index=run_start + offset, track_id=int(observation.track_id),
                xyxy=tuple(float(value) for value in observation.xyxy),
                score=float(observation.score), class_id=int(observation.class_id),
            ))
    digest = hashlib.sha256(serialize_track_jsonl(
        observations, frame_count=source.frame_count,
    )).hexdigest()
    if digest != metadata["track_sha256"]:
        raise ValueError("diagnostic replay differs from saved public output; no trace emitted")
    if implementation != _implementation_hashes():
        raise ValueError("implementation changed during diagnostic replay")
    # Use stable input keys rather than ambiguous detection positions in the export.
    for row in observer.frames:
        selected = frames[row["frame_index"] - run_start]
        for detection in row["detections"]:
            detection["detection_index"] = selected[detection.pop("input_offset")].detection_index
        for track in row["tracks"]:
            index = track.pop("input_offset")
            track["detection_index"] = None if index is None else selected[index].detection_index
    result = {
        "schema": "visiontrack.initiation-trace/v1",
        "experiment_id": experiment.experiment_id, "source_id": source.source_id,
        "variant": variant, "run_id": metadata["run_id"],
        "detection_sha256": source.detection_sha256, "track_sha256": digest,
        "replay_frame_range": experiment.frame_range,
        "trace_frame_range": {"start": start, "end": end},
        "config": asdict(config), "frames": observer.frames,
        "producer": {"visiontrack": __version__, "python": platform.python_version(),
                     "numpy": np.__version__, "implementation_sha256": implementation},
        "public_output_parity": "exact_sha256_match",
        "accuracy_claim": False, "physical_identity_verified": False,
        "limits": [
            "Detection scores and lifecycle states are not truth or accuracy labels.",
            "Unmatched does not identify which gate or competing assignment caused rejection.",
            "Track IDs are local to this run; surviving internally does not emit a public box.",
            "Only the selected window is recorded; replay starts at the experiment boundary.",
        ],
    }
    result["trace_id"] = sha256_json(result)
    return result
