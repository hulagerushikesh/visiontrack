"""Private streaming input path for read-only diagnostic replay.

The ordinary comparison/evaluation APIs still materialize their records. This
path retains one detection frame, validates every row (also outside the replay
range), and verifies exact consumed bytes before a diagnostic can be returned.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from .contracts import DetectionRecord, GroundTruthRecord, SourceManifest, TrackObservationRecord
from .storage import _iter_jsonl


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(256 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ValueError(f"cannot read replay evidence: {path}") from exc
    return digest.hexdigest()


def _verify_replay_files(expected: dict[Path, str]) -> None:
    for path, digest in expected.items():
        if _file_sha256(path) != digest:
            raise ValueError(f"replay evidence SHA-256 changed or does not match: {path.name}")


def _verify_replay_records(bundle: Path, source: SourceManifest, metadata: dict) -> None:
    """Fully validate saved tracks and optional GT without retaining their rows."""
    track_path = bundle / "runs" / metadata["variant"] / "tracks.jsonl"
    start, end = metadata["frame_range"]["start"], metadata["frame_range"]["end"]
    count = 0
    for track in _iter_jsonl(
        track_path, record_type=TrackObservationRecord,
        key=lambda row: (row.frame_index, row.track_id), label="track observation",
        frame_count=source.frame_count, expected_sha256=metadata["track_sha256"],
    ):
        if not start <= track.frame_index < end:
            raise ValueError("track observation falls outside experiment frame_range")
        count += 1
    if count != metadata["observation_count"]:
        raise ValueError("track observation count does not match run metadata")
    if source.ground_truth_sha256 is not None:
        for _ in _iter_jsonl(
            bundle / "inputs" / "ground_truth.jsonl", record_type=GroundTruthRecord,
            key=lambda row: (row.frame_index, row.object_id), label="ground-truth",
            frame_count=source.frame_count, expected_sha256=source.ground_truth_sha256,
        ):
            pass


def _iter_replay_frames(
    bundle: Path, source: SourceManifest, *, start: int, end: int,
) -> Iterator[tuple[DetectionRecord, ...]]:
    """Yield all replay frames, including gaps, then exhaust and hash the tail.

    Source rows before/after the experiment are validated, not replayed. Only
    feature references inside the experiment are unsupported, as in the ordinary
    runner. The retained frame needs memory proportional to its detections.
    """
    frame = start
    current: list[DetectionRecord] = []
    for record in _iter_jsonl(
        bundle / "inputs" / "detections.jsonl", record_type=DetectionRecord,
        key=lambda row: (row.frame_index, row.detection_index), label="detection",
        frame_count=source.frame_count, expected_sha256=source.detection_sha256,
    ):
        if not start <= record.frame_index < end:
            continue
        if record.feature_ref is not None:
            raise ValueError(
                "detection feature_ref requires a bundle feature payload, "
                "which is not supported yet"
            )
        while frame < record.frame_index:
            yield tuple(current)
            current.clear()
            frame += 1
        current.append(record)
    while frame < end:
        yield tuple(current)
        current.clear()
        frame += 1
