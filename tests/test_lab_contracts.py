"""Reliability Lab v1 contracts stay strict, deterministic, and portable."""
from __future__ import annotations

import json

import numpy as np
import pytest

from visiontrack.detection.base import Detection
from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    canonical_json,
)
from visiontrack.tracking.tracker import TrackObservation

SHA_A = "a" * 64
SHA_B = "b" * 64
NOW = "2026-09-19T10:00:00Z"


def source_manifest() -> SourceManifest:
    return SourceManifest.create(
        kind="visiontrack_cache",
        name="MOT17-09-FRCNN",
        detection_sha256=SHA_A,
        ground_truth_sha256=SHA_B,
        video_sha256=None,
        detector={"name": "FRCNN", "threshold": 0.5},
        frame_count=525,
        width=1920,
        height=1080,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )


def experiment_manifest(source_id: str) -> ExperimentManifest:
    return ExperimentManifest.create(
        source_id=source_id,
        baseline="bytetrack",
        variants=(
            {"name": "bytetrack", "overrides": {}},
            {"name": "appearance", "overrides": {"w_app": 0.3}},
        ),
        metrics=("HOTA", "IDF1", "IDSW"),
        frame_range={"start": 0, "end": 525},
        visiontrack_version="0.2.0",
        git_revision="abc1234",
        environment={"python": "3.12", "numpy": "2.4.6", "platform": "macOS"},
        created_at=NOW,
    )


def test_canonical_json_is_order_independent_and_rejects_nan() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    with pytest.raises(ValueError):
        canonical_json({"bad": float("nan")})


def test_source_manifest_is_content_addressed_and_round_trips() -> None:
    manifest = source_manifest()
    assert len(manifest.source_id) == 64
    assert SourceManifest.from_json(manifest.to_json()) == manifest
    tampered = manifest.to_dict()
    tampered["width"] = 1280
    with pytest.raises(ValueError, match="source_id"):
        SourceManifest.from_dict(tampered)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"kind": "video"}, "kind"),
        ({"detection_sha256": "short"}, "SHA-256"),
        ({"frame_count": 0}, "positive"),
        ({"fps": float("inf")}, "fps"),
        ({"coordinate_space": "normalized_xywh"}, "pixel_xyxy"),
        ({"created_at": "2026-09-19T10:00:00"}, "UTC"),
    ],
)
def test_source_manifest_rejects_invalid_values(change, message) -> None:
    data = source_manifest().to_dict()
    data.update(change)
    with pytest.raises(ValueError, match=message):
        SourceManifest.from_dict(data)


def test_detection_adapter_and_json_round_trip() -> None:
    detection = Detection(np.array([10, 20, 40, 80]), score=0.75, class_id=1)
    record = DetectionRecord.from_detection(
        detection, frame_index=3, source_frame=4, detection_index=0
    )
    assert record.xyxy == (10.0, 20.0, 40.0, 80.0)
    assert DetectionRecord.from_json(record.to_json()) == record
    assert json.loads(record.to_json())["schema_version"] == 1


@pytest.mark.parametrize(
    "values",
    [
        {"frame_index": -1},
        {"detection_index": -1},
        {"xyxy": (10, 10, 5, 20)},
        {"xyxy": (0, 0, float("inf"), 20)},
        {"score": 1.1},
        {"feature_ref": ""},
    ],
)
def test_detection_record_rejects_invalid_values(values) -> None:
    base = {
        "frame_index": 0,
        "source_frame": None,
        "detection_index": 0,
        "xyxy": (0, 0, 10, 20),
        "score": 0.9,
        "class_id": 1,
        "feature_ref": None,
    }
    with pytest.raises(ValueError):
        DetectionRecord(**{**base, **values})


def test_experiment_manifest_hashes_configuration_and_full_content() -> None:
    manifest = experiment_manifest(source_manifest().source_id)
    assert len(manifest.config_sha256) == 64
    assert len(manifest.experiment_id) == 64
    assert ExperimentManifest.from_json(manifest.to_json()) == manifest

    reordered_environment = ExperimentManifest.create(
        source_id=manifest.source_id,
        baseline=manifest.baseline,
        variants=manifest.variants,
        metrics=manifest.metrics,
        frame_range=manifest.frame_range,
        visiontrack_version=manifest.visiontrack_version,
        git_revision=manifest.git_revision,
        environment={"platform": "macOS", "numpy": "2.4.6", "python": "3.12"},
        created_at=NOW,
    )
    assert reordered_environment.experiment_id == manifest.experiment_id


def test_experiment_manifest_rejects_invalid_baseline_or_range() -> None:
    manifest = experiment_manifest(source_manifest().source_id)
    data = manifest.to_dict()
    data["baseline"] = "missing"
    with pytest.raises(ValueError, match="baseline"):
        ExperimentManifest.from_dict(data)

    data = manifest.to_dict()
    data["frame_range"] = {"start": 10, "end": 10}
    with pytest.raises(ValueError, match="frame_range"):
        ExperimentManifest.from_dict(data)


def test_unknown_fields_and_schema_versions_are_rejected() -> None:
    data = source_manifest().to_dict()
    data["surprise"] = True
    with pytest.raises(ValueError, match="unknown"):
        SourceManifest.from_dict(data)

    detection = DetectionRecord(0, None, 0, (0, 0, 1, 1), 1.0, -1)
    data = detection.to_dict()
    data["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        DetectionRecord.from_dict(data)


def test_track_observation_adapter_and_contract() -> None:
    observation = TrackObservation(
        frame=7,
        track_id=12,
        xyxy=np.array([5.0, 6.0, 25.0, 36.0]),
        score=0.88,
        class_id=1,
    )
    record = TrackObservationRecord.from_observation(observation)
    assert record.frame_index == 7
    assert record.track_id == 12
    assert record.state == "confirmed"
    assert TrackObservationRecord.from_json(record.to_json()) == record

    with pytest.raises(ValueError, match="confirmed"):
        TrackObservationRecord(7, 12, (5, 6, 25, 36), 0.88, 1, state="lost")
