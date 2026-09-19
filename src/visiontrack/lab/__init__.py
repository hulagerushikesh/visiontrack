"""Versioned, local-first contracts for the VisionTrack Reliability Lab."""

from .contracts import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    canonical_json,
    sha256_json,
)
from .runner import load_experiment_bundle, resolve_variant_config, run_comparison
from .storage import (
    create_experiment_bundle,
    create_variant_run,
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
    "create_variant_run",
    "detection_payload_sha256",
    "read_detection_jsonl",
    "read_track_jsonl",
    "serialize_detection_jsonl",
    "serialize_track_jsonl",
    "verify_detection_payload",
    "write_detection_jsonl",
    "write_track_jsonl",
    "load_experiment_bundle",
    "resolve_variant_config",
    "run_comparison",
]
