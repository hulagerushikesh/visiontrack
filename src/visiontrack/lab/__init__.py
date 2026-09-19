"""Versioned, local-first contracts for the VisionTrack Reliability Lab."""

from .comparison import create_comparison_summary
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
    write_comparison_summary,
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
    "create_comparison_summary",
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
    "write_comparison_summary",
    "load_experiment_bundle",
    "resolve_variant_config",
    "run_comparison",
]
