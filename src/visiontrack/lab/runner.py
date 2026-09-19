"""Deterministic paired execution for a verified Reliability Lab bundle."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from ..detection.base import Detection
from ..tracking.config import TrackerConfig
from ..tracking.presets import preset
from ..tracking.tracker import ByteTracker
from .contracts import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    sha256_json,
)
from .storage import (
    create_variant_run,
    read_detection_jsonl,
    serialize_track_jsonl,
    verify_detection_payload,
)

_VARIANT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_VARIANT_FIELDS = {"name", "preset", "overrides"}


def _read_manifest(path: Path, record_type):
    try:
        return record_type.from_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read bundle manifest: {path}") from exc


def load_experiment_bundle(
    bundle: str | Path,
) -> tuple[ExperimentManifest, SourceManifest, tuple[DetectionRecord, ...]]:
    """Load and verify the immutable evidence needed by every variant."""
    bundle_path = Path(bundle)
    experiment = _read_manifest(bundle_path / "manifest.json", ExperimentManifest)
    source = _read_manifest(bundle_path / "source.json", SourceManifest)
    if bundle_path.name != experiment.experiment_id:
        raise ValueError("bundle directory name does not match experiment_id")
    if experiment.source_id != source.source_id:
        raise ValueError("experiment source_id does not match source manifest")
    if experiment.frame_range["end"] > source.frame_count:
        raise ValueError("experiment frame_range exceeds source frame_count")

    detection_path = bundle_path / "inputs" / "detections.jsonl"
    try:
        payload = detection_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read detection payload: {detection_path}") from exc
    verify_detection_payload(source, payload)
    records = tuple(read_detection_jsonl(detection_path, frame_count=source.frame_count))
    return experiment, source, records


def resolve_variant_config(variant: dict[str, Any]) -> TrackerConfig:
    """Resolve one declared variant onto an existing named tracker preset."""
    if not isinstance(variant, dict):
        raise ValueError("variant must be an object")
    unknown = set(variant) - _VARIANT_FIELDS
    if unknown:
        raise ValueError(f"unknown variant fields: {sorted(unknown)}")
    name = variant.get("name")
    if not isinstance(name, str) or not _VARIANT_NAME.fullmatch(name):
        raise ValueError("variant name must be a safe 1-64 character path component")
    preset_name = variant.get("preset", "bytetrack")
    if not isinstance(preset_name, str):
        raise ValueError("variant preset must be a string")
    overrides = variant.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("variant overrides must be an object")
    try:
        config = preset(preset_name, **overrides)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid tracker configuration for variant {name!r}: {exc}") from exc
    if config.w_app > 0:
        raise ValueError(
            f"variant {name!r} requires appearance features; "
            "Lab feature payloads are not supported yet"
        )
    if config.motion_residual_path is not None:
        raise ValueError(
            f"variant {name!r} requires an external motion residual, which is not bundle-backed yet"
        )
    if config.use_gmc:
        raise ValueError(
            f"variant {name!r} requires camera shifts, which are not bundle-backed yet"
        )
    return config


def _group_detections(
    records: Iterable[DetectionRecord], *, start: int, end: int
) -> tuple[tuple[DetectionRecord, ...], ...]:
    frames: list[list[DetectionRecord]] = [[] for _ in range(end - start)]
    for record in records:
        if start <= record.frame_index < end:
            if record.feature_ref is not None:
                raise ValueError(
                    "detection feature_ref requires a bundle feature payload, "
                    "which is not supported yet"
                )
            frames[record.frame_index - start].append(record)
    return tuple(tuple(frame) for frame in frames)


def _as_detections(records: tuple[DetectionRecord, ...]) -> list[Detection]:
    return [
        Detection(
            xyxy=np.asarray(record.xyxy, dtype=np.float64),
            score=record.score,
            class_id=record.class_id,
        )
        for record in records
    ]


def _execute_variant(
    config: TrackerConfig,
    frames: tuple[tuple[DetectionRecord, ...], ...],
    *,
    start: int,
) -> list[TrackObservationRecord]:
    tracker = ByteTracker(config)
    output: list[TrackObservationRecord] = []
    for offset, records in enumerate(frames):
        for observation in tracker.update(_as_detections(records)):
            output.append(
                TrackObservationRecord(
                    frame_index=start + offset,
                    track_id=int(observation.track_id),
                    xyxy=tuple(float(value) for value in observation.xyxy),
                    score=float(observation.score),
                    class_id=int(observation.class_id),
                )
            )
    return output


def _run_metadata(
    experiment: ExperimentManifest,
    source: SourceManifest,
    variant_name: str,
    config: TrackerConfig,
    tracks: list[TrackObservationRecord],
) -> dict[str, Any]:
    config_data = asdict(config)
    track_payload = serialize_track_jsonl(tracks, frame_count=source.frame_count)
    data: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment.experiment_id,
        "source_id": source.source_id,
        "variant": variant_name,
        "config": config_data,
        "config_sha256": sha256_json(config_data),
        "detection_sha256": source.detection_sha256,
        "frame_range": experiment.frame_range,
        "track_sha256": hashlib.sha256(track_payload).hexdigest(),
        "observation_count": len(tracks),
    }
    data["run_id"] = sha256_json(data)
    return data


def run_comparison(bundle: str | Path) -> dict[str, tuple[TrackObservationRecord, ...]]:
    """Run every declared variant on the same verified in-memory evidence."""
    bundle_path = Path(bundle)
    experiment, source, records = load_experiment_bundle(bundle_path)
    start = experiment.frame_range["start"]
    end = experiment.frame_range["end"]
    frames = _group_detections(records, start=start, end=end)

    results: dict[str, tuple[TrackObservationRecord, ...]] = {}
    for variant in experiment.variants:
        name = variant["name"]
        config = resolve_variant_config(variant)
        tracks = _execute_variant(config, frames, start=start)
        metadata = _run_metadata(experiment, source, name, config, tracks)
        create_variant_run(
            bundle_path,
            name,
            metadata,
            tracks,
            frame_count=source.frame_count,
        )
        results[name] = tuple(tracks)
    return results
