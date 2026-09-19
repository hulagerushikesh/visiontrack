"""Portable Reliability Lab storage is deterministic and overwrite-safe."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    SourceManifest,
    TrackObservationRecord,
    create_experiment_bundle,
    detection_payload_sha256,
    read_detection_jsonl,
    read_track_jsonl,
    serialize_detection_jsonl,
    serialize_track_jsonl,
    verify_detection_payload,
    write_detection_jsonl,
)

NOW = "2026-09-19T10:00:00Z"


def detections() -> list[DetectionRecord]:
    return [
        DetectionRecord(1, None, 0, (20, 20, 40, 60), 0.8, 1),
        DetectionRecord(0, None, 1, (50, 10, 80, 70), 0.7, 1),
        DetectionRecord(0, None, 0, (10, 10, 30, 50), 0.9, 1),
    ]


def source(records: list[DetectionRecord] | None = None) -> SourceManifest:
    records = detections() if records is None else records
    return SourceManifest.create(
        kind="synthetic",
        name="two-frame-sequence",
        detection_sha256=detection_payload_sha256(records, frame_count=2),
        ground_truth_sha256=None,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=2,
        width=100,
        height=80,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )


def experiment(source_id: str) -> ExperimentManifest:
    return ExperimentManifest.create(
        source_id=source_id,
        baseline="default",
        variants=({"name": "default", "overrides": {}},),
        metrics=("track_count",),
        frame_range={"start": 0, "end": 2},
        visiontrack_version="0.2.0",
        git_revision="893079c",
        environment={"python": "3.12"},
        created_at=NOW,
    )


def test_detection_jsonl_is_canonical_and_round_trips(tmp_path: Path) -> None:
    unordered = detections()
    payload = serialize_detection_jsonl(unordered, frame_count=2)
    keys = [
        (item["frame_index"], item["detection_index"])
        for item in (json.loads(line) for line in payload.decode().splitlines())
    ]
    assert keys == [(0, 0), (0, 1), (1, 0)]
    assert payload.endswith(b"\n")

    path = tmp_path / "detections.jsonl"
    digest = write_detection_jsonl(path, unordered, frame_count=2)
    assert digest == detection_payload_sha256(unordered, frame_count=2)
    assert read_detection_jsonl(path, frame_count=2) == sorted(
        unordered, key=lambda record: (record.frame_index, record.detection_index)
    )


def test_track_jsonl_is_canonical_and_round_trips(tmp_path: Path) -> None:
    unordered = [
        TrackObservationRecord(1, 2, (10, 10, 20, 30), 0.8, 1),
        TrackObservationRecord(0, 3, (40, 10, 60, 30), 0.7, 1),
        TrackObservationRecord(0, 1, (10, 10, 20, 30), 0.9, 1),
    ]
    path = tmp_path / "tracks.jsonl"
    path.write_bytes(serialize_track_jsonl(unordered, frame_count=2))
    assert [(record.frame_index, record.track_id) for record in read_track_jsonl(path)] == [
        (0, 1),
        (0, 3),
        (1, 2),
    ]


@pytest.mark.parametrize(
    "records",
    [
        [
            DetectionRecord(0, None, 0, (0, 0, 10, 10), 0.9, 1),
            DetectionRecord(0, None, 0, (1, 1, 11, 11), 0.8, 1),
        ],
        [DetectionRecord(2, None, 0, (0, 0, 10, 10), 0.9, 1)],
    ],
)
def test_detection_writer_rejects_duplicate_or_out_of_range_records(records) -> None:
    with pytest.raises(ValueError):
        serialize_detection_jsonl(records, frame_count=2)


def test_reader_rejects_out_of_order_duplicate_blank_and_corrupt_lines(
    tmp_path: Path,
) -> None:
    first, second = sorted(
        detections(), key=lambda record: (record.frame_index, record.detection_index)
    )[:2]
    cases = {
        "out-of-order": f"{second.to_json()}\n{first.to_json()}\n",
        "duplicate": f"{first.to_json()}\n{first.to_json()}\n",
        "blank": f"{first.to_json()}\n\n",
        "invalid": f"{first.to_json()}\n{{bad json}}\n",
    }
    for reason, content in cases.items():
        path = tmp_path / f"{reason}.jsonl"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            read_detection_jsonl(path, frame_count=2)


def test_detection_hash_verification_detects_corruption() -> None:
    records = detections()
    manifest = source(records)
    payload = serialize_detection_jsonl(records, frame_count=manifest.frame_count)
    verify_detection_payload(manifest, payload)
    with pytest.raises(ValueError, match="does not match"):
        verify_detection_payload(manifest, payload + b" ")


def test_immutable_writer_is_idempotent_but_refuses_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "detections.jsonl"
    write_detection_jsonl(path, detections(), frame_count=2)
    write_detection_jsonl(path, reversed(detections()), frame_count=2)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_detection_jsonl(
            path,
            [DetectionRecord(0, None, 0, (0, 0, 1, 1), 1.0, 1)],
            frame_count=2,
        )


def test_bundle_creation_is_atomic_idempotent_and_structured(tmp_path: Path) -> None:
    records = detections()
    source_manifest = source(records)
    manifest = experiment(source_manifest.source_id)

    bundle = create_experiment_bundle(tmp_path, manifest, source_manifest, records)
    assert bundle == tmp_path / manifest.experiment_id
    assert (bundle / "manifest.json").read_text().endswith("\n")
    assert (bundle / "source.json").read_text().endswith("\n")
    assert read_detection_jsonl(
        bundle / "inputs/detections.jsonl", frame_count=source_manifest.frame_count
    )
    assert (bundle / "runs").is_dir()
    assert (bundle / "report").is_dir()
    assert create_experiment_bundle(tmp_path, manifest, source_manifest, records) == bundle
    assert not list(tmp_path.glob(f".{manifest.experiment_id}.*"))


def test_bundle_refuses_corruption_and_mismatched_inputs(tmp_path: Path) -> None:
    records = detections()
    source_manifest = source(records)
    manifest = experiment(source_manifest.source_id)
    bundle = create_experiment_bundle(tmp_path, manifest, source_manifest, records)
    (bundle / "source.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="source.json"):
        create_experiment_bundle(tmp_path, manifest, source_manifest, records)

    wrong_source = source([DetectionRecord(0, None, 0, (0, 0, 1, 1), 1.0, 1)])
    with pytest.raises(ValueError, match="source_id"):
        create_experiment_bundle(tmp_path / "other", manifest, wrong_source, records)


def test_bundle_rejects_payload_hash_or_frame_range_mismatch(tmp_path: Path) -> None:
    records = detections()
    source_manifest = source(records)
    manifest = experiment(source_manifest.source_id)
    with pytest.raises(ValueError, match="SHA-256"):
        create_experiment_bundle(tmp_path, manifest, source_manifest, records[:1])

    too_long = ExperimentManifest.create(
        source_id=source_manifest.source_id,
        baseline="default",
        variants=({"name": "default", "overrides": {}},),
        metrics=("track_count",),
        frame_range={"start": 0, "end": 3},
        visiontrack_version="0.2.0",
        git_revision=None,
        environment={"python": "3.12"},
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="frame_range"):
        create_experiment_bundle(tmp_path, too_long, source_manifest, records)
