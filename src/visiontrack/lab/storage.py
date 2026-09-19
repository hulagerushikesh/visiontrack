"""Deterministic, local-only storage for Reliability Lab v1 records."""
from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

from .contracts import (
    ContractRecord,
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    canonical_json,
)

_R = TypeVar("_R", bound=ContractRecord)
_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_document(record: ContractRecord) -> bytes:
    return f"{record.to_json()}\n".encode()


def _serialize_jsonl(
    records: Iterable[_R],
    *,
    key: Callable[[_R], tuple[int, int]],
    label: str,
    frame_count: int | None,
) -> bytes:
    ordered = sorted(records, key=key)
    previous: tuple[int, int] | None = None
    lines: list[str] = []
    for record in ordered:
        record_key = key(record)
        if record_key == previous:
            raise ValueError(f"duplicate {label} key: {record_key}")
        if frame_count is not None and record_key[0] >= frame_count:
            raise ValueError(
                f"{label} frame_index {record_key[0]} is outside frame_count {frame_count}"
            )
        previous = record_key
        lines.append(record.to_json())
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def serialize_detection_jsonl(
    records: Iterable[DetectionRecord], *, frame_count: int | None = None
) -> bytes:
    """Return canonical detection JSONL ordered by frame and detection index."""
    return _serialize_jsonl(
        records,
        key=lambda record: (record.frame_index, record.detection_index),
        label="detection",
        frame_count=frame_count,
    )


def serialize_track_jsonl(
    records: Iterable[TrackObservationRecord], *, frame_count: int | None = None
) -> bytes:
    """Return canonical track JSONL ordered by frame and run-local track ID."""
    return _serialize_jsonl(
        records,
        key=lambda record: (record.frame_index, record.track_id),
        label="track observation",
        frame_count=frame_count,
    )


def detection_payload_sha256(
    records: Iterable[DetectionRecord], *, frame_count: int | None = None
) -> str:
    """Hash the exact canonical detection payload stored in a Lab bundle."""
    return _sha256(serialize_detection_jsonl(records, frame_count=frame_count))


def _write_immutable(path: Path, payload: bytes) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if not path.is_file() or path.read_bytes() != payload:
            raise FileExistsError(f"refusing to overwrite conflicting file: {path}") from None
    return _sha256(payload)


def write_detection_jsonl(
    path: str | Path,
    records: Iterable[DetectionRecord],
    *,
    frame_count: int | None = None,
) -> str:
    """Write an immutable canonical detection stream and return its SHA-256."""
    payload = serialize_detection_jsonl(records, frame_count=frame_count)
    return _write_immutable(Path(path), payload)


def write_track_jsonl(
    path: str | Path,
    records: Iterable[TrackObservationRecord],
    *,
    frame_count: int | None = None,
) -> str:
    """Write immutable canonical observations and return their SHA-256."""
    payload = serialize_track_jsonl(records, frame_count=frame_count)
    return _write_immutable(Path(path), payload)


def _read_jsonl(
    path: str | Path,
    *,
    record_type: type[_R],
    key: Callable[[_R], tuple[int, int]],
    label: str,
    frame_count: int | None,
) -> list[_R]:
    records: list[_R] = []
    previous: tuple[int, int] | None = None
    text = Path(path).read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank line in {label} JSONL at line {line_number}")
        try:
            record = record_type.from_json(line)
        except ValueError as exc:
            raise ValueError(
                f"invalid {label} JSONL record at line {line_number}: {exc}"
            ) from exc
        record_key = key(record)
        if previous is not None and record_key <= previous:
            reason = "duplicate" if record_key == previous else "out-of-order"
            raise ValueError(f"{reason} {label} key at line {line_number}: {record_key}")
        if frame_count is not None and record_key[0] >= frame_count:
            raise ValueError(
                f"{label} frame_index {record_key[0]} is outside frame_count {frame_count}"
            )
        records.append(record)
        previous = record_key
    return records


def read_detection_jsonl(
    path: str | Path, *, frame_count: int | None = None
) -> list[DetectionRecord]:
    """Read and validate a canonically ordered detection JSONL stream."""
    return _read_jsonl(
        path,
        record_type=DetectionRecord,
        key=lambda record: (record.frame_index, record.detection_index),
        label="detection",
        frame_count=frame_count,
    )


def read_track_jsonl(
    path: str | Path, *, frame_count: int | None = None
) -> list[TrackObservationRecord]:
    """Read and validate a canonically ordered track JSONL stream."""
    return _read_jsonl(
        path,
        record_type=TrackObservationRecord,
        key=lambda record: (record.frame_index, record.track_id),
        label="track observation",
        frame_count=frame_count,
    )


def verify_detection_payload(source: SourceManifest, payload: bytes) -> None:
    """Raise when exact detection bytes do not match their source manifest."""
    actual = _sha256(payload)
    if actual != source.detection_sha256:
        raise ValueError(
            "detection payload SHA-256 does not match source manifest: "
            f"expected {source.detection_sha256}, got {actual}"
        )


def _verify_existing_bundle(path: Path, expected: dict[str, bytes]) -> None:
    conflicts = [
        relative
        for relative, payload in expected.items()
        if not (path / relative).is_file() or (path / relative).read_bytes() != payload
    ]
    if conflicts:
        joined = ", ".join(conflicts)
        raise FileExistsError(
            f"experiment bundle {path.name} already exists with conflicting content: {joined}"
        )


def create_experiment_bundle(
    root: str | Path,
    experiment: ExperimentManifest,
    source: SourceManifest,
    detections: Iterable[DetectionRecord],
) -> Path:
    """Atomically create the immutable input scaffold for one experiment.

    Repeating the call with identical inputs is safe. Existing conflicting
    manifest, source, or detection content is never overwritten.
    """
    if experiment.source_id != source.source_id:
        raise ValueError("experiment source_id does not match the source manifest")
    if experiment.frame_range["end"] > source.frame_count:
        raise ValueError("experiment frame_range exceeds the source frame_count")

    detection_payload = serialize_detection_jsonl(
        detections, frame_count=source.frame_count
    )
    verify_detection_payload(source, detection_payload)
    expected = {
        "manifest.json": _json_document(experiment),
        "source.json": _json_document(source),
        "inputs/detections.jsonl": detection_payload,
    }

    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    destination = root_path / experiment.experiment_id
    if destination.exists():
        _verify_existing_bundle(destination, expected)
        return destination

    staging = Path(tempfile.mkdtemp(prefix=f".{experiment.experiment_id}.", dir=root_path))
    try:
        for relative, payload in expected.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        (staging / "runs").mkdir()
        (staging / "report").mkdir()
        try:
            staging.rename(destination)
        except FileExistsError:
            _verify_existing_bundle(destination, expected)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def create_variant_run(
    bundle: str | Path,
    variant: str,
    metadata: dict,
    tracks: Iterable[TrackObservationRecord],
    *,
    frame_count: int,
) -> Path:
    """Atomically persist one immutable variant result inside a Lab bundle."""
    if not _RUN_NAME.fullmatch(variant) or variant in {".", ".."}:
        raise ValueError("variant name must be a safe 1-64 character path component")

    track_payload = serialize_track_jsonl(tracks, frame_count=frame_count)
    track_sha256 = _sha256(track_payload)
    if metadata.get("track_sha256") != track_sha256:
        raise ValueError("run metadata track_sha256 does not match track observations")
    expected = {
        "run.json": (canonical_json(metadata) + "\n").encode("utf-8"),
        "tracks.jsonl": track_payload,
    }

    runs = Path(bundle) / "runs"
    if not runs.is_dir():
        raise ValueError(f"bundle runs directory does not exist: {runs}")
    destination = runs / variant
    if destination.exists():
        _verify_existing_bundle(destination, expected)
        return destination

    staging = Path(tempfile.mkdtemp(prefix=f".{variant}.", dir=runs))
    try:
        for relative, payload in expected.items():
            (staging / relative).write_bytes(payload)
        try:
            staging.rename(destination)
        except FileExistsError:
            _verify_existing_bundle(destination, expected)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)
