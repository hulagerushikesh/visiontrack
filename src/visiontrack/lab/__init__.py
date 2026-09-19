"""Versioned, local-first contracts for the VisionTrack Reliability Lab."""

from .contracts import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    canonical_json,
    sha256_json,
)
from .storage import (
    create_experiment_bundle,
    detection_payload_sha256,
    read_detection_jsonl,
    read_track_jsonl,
    serialize_detection_jsonl,
    serialize_track_jsonl,
    verify_detection_payload,
    write_detection_jsonl,
    write_track_jsonl,
)

__all__ = [
    "DetectionRecord",
    "ExperimentManifest",
    "SourceManifest",
    "TrackObservationRecord",
    "canonical_json",
    "sha256_json",
    "create_experiment_bundle",
    "detection_payload_sha256",
    "read_detection_jsonl",
    "read_track_jsonl",
    "serialize_detection_jsonl",
    "serialize_track_jsonl",
    "verify_detection_payload",
    "write_detection_jsonl",
    "write_track_jsonl",
]
