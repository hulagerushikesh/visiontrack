"""Versioned, local-first contracts for the VisionTrack Reliability Lab."""

from .comparison import create_comparison_summary
from .contracts import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    TrackObservationRecord,
    canonical_json,
    sha256_json,
)
from .metrics import calculate_bundle_metrics
from .mot import import_mot_ground_truth
from .runner import load_experiment_bundle, resolve_variant_config, run_comparison
from .storage import (
    create_experiment_bundle,
    create_variant_run,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    read_detection_jsonl,
    read_ground_truth_jsonl,
    read_track_jsonl,
    serialize_detection_jsonl,
    serialize_ground_truth_jsonl,
    serialize_track_jsonl,
    verify_detection_payload,
    verify_ground_truth_payload,
    write_comparison_summary,
    write_detection_jsonl,
    write_ground_truth_jsonl,
    write_track_jsonl,
    write_variant_metrics,
)

__all__ = [
    "DetectionRecord",
    "ExperimentManifest",
    "GroundTruthRecord",
    "SourceManifest",
    "TrackObservationRecord",
    "canonical_json",
    "sha256_json",
    "create_comparison_summary",
    "create_experiment_bundle",
    "create_variant_run",
    "detection_payload_sha256",
    "ground_truth_payload_sha256",
    "import_mot_ground_truth",
    "calculate_bundle_metrics",
    "read_detection_jsonl",
    "read_ground_truth_jsonl",
    "read_track_jsonl",
    "serialize_detection_jsonl",
    "serialize_ground_truth_jsonl",
    "serialize_track_jsonl",
    "verify_detection_payload",
    "verify_ground_truth_payload",
    "write_detection_jsonl",
    "write_ground_truth_jsonl",
    "write_track_jsonl",
    "write_variant_metrics",
    "write_comparison_summary",
    "load_experiment_bundle",
    "resolve_variant_config",
    "run_comparison",
]
