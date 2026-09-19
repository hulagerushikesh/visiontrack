"""Portable ground truth and strict MOTChallenge import stay evidence-safe."""
from __future__ import annotations

from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    ground_truth_payload_sha256,
    import_mot_ground_truth,
    load_experiment_bundle,
    read_ground_truth_jsonl,
    run_comparison,
    serialize_ground_truth_jsonl,
    verify_ground_truth_payload,
    write_ground_truth_jsonl,
)

NOW = "2026-09-19T16:00:00Z"
MOT = """2,2,40,20,10,30,0,7,0.4
1,2,35,20,10,30,1,1,0.8
1,1,10,10,20,40,1,1,1.0
"""


def test_ground_truth_record_round_trips_and_validates() -> None:
    record = GroundTruthRecord(0, 1, 7, (10, 20, 30, 60), 1, 0.75, False)
    assert GroundTruthRecord.from_json(record.to_json()) == record

    invalid = [
        {"frame_index": -1},
        {"source_frame": -1},
        {"object_id": 0},
        {"xyxy": (10, 10, 5, 20)},
        {"class_id": 1.5},
        {"visibility": -0.1},
        {"visibility": float("inf")},
        {"ignored": 0},
        {"schema_version": 2},
    ]
    base = {
        "frame_index": 0,
        "source_frame": 1,
        "object_id": 1,
        "xyxy": (0, 0, 10, 20),
        "class_id": 1,
        "visibility": 1.0,
        "ignored": False,
    }
    for change in invalid:
        with pytest.raises(ValueError):
            GroundTruthRecord(**{**base, **change})


def test_mot_import_converts_frames_boxes_and_preserves_ignore_rows(tmp_path: Path) -> None:
    path = tmp_path / "gt.txt"
    path.write_text(MOT, encoding="utf-8")
    records = import_mot_ground_truth(path, frame_count=2)

    assert [(record.frame_index, record.object_id) for record in records] == [
        (0, 1),
        (0, 2),
        (1, 2),
    ]
    assert records[0].source_frame == 1
    assert records[0].xyxy == (10.0, 10.0, 30.0, 50.0)
    assert records[2].xyxy == (40.0, 20.0, 50.0, 50.0)
    assert records[2].ignored is True
    assert records[2].class_id == 7
    assert records[2].visibility == 0.4


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("1,1,0,0,10,10,1,1\n", "9 columns"),
        ("0,1,0,0,10,10,1,1,1\n", "one-based"),
        ("1,0,0,0,10,10,1,1,1\n", "id must be positive"),
        ("1,1,0,0,0,10,1,1,1\n", "width and height"),
        ("1,1,0,0,10,10,2,1,1\n", "consider"),
        ("1,1,0,0,10,10,1,1,1.1\n", "visibility"),
        ("1,1,0,0,10,10,1,1,nan\n", "finite"),
        ("1,1,0,0,10,10,1,1,1\n1,1,1,1,10,10,1,1,1\n", "duplicate"),
        ("1,1,0,0,10,10,1,1,1\n\n2,1,0,0,10,10,1,1,1\n", "blank"),
        ("3,1,0,0,10,10,1,1,1\n", "frame_count"),
    ],
)
def test_mot_import_rejects_ambiguous_or_invalid_rows(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "gt.txt"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        import_mot_ground_truth(path, frame_count=2)


def test_ground_truth_jsonl_is_deterministic_and_immutable(tmp_path: Path) -> None:
    mot_path = tmp_path / "gt.txt"
    mot_path.write_text(MOT, encoding="utf-8")
    records = import_mot_ground_truth(mot_path, frame_count=2)
    unordered = list(reversed(records))
    payload = serialize_ground_truth_jsonl(unordered, frame_count=2)
    path = tmp_path / "ground_truth.jsonl"
    digest = write_ground_truth_jsonl(path, unordered, frame_count=2)
    assert digest == ground_truth_payload_sha256(records, frame_count=2)
    assert path.read_bytes() == payload
    assert read_ground_truth_jsonl(path, frame_count=2) == records
    assert write_ground_truth_jsonl(path, records, frame_count=2) == digest

    with pytest.raises(ValueError, match="duplicate"):
        serialize_ground_truth_jsonl([records[0], records[0]], frame_count=2)


def _bundle_with_ground_truth(tmp_path: Path) -> tuple[Path, SourceManifest]:
    detections = [
        DetectionRecord(frame, None, 0, (10 + frame, 10, 30 + frame, 50), 0.95, 1)
        for frame in range(2)
    ]
    ground_truth = [
        GroundTruthRecord(frame, frame + 1, 1, (10 + frame, 10, 30 + frame, 50), 1, 1.0, False)
        for frame in range(2)
    ]
    source = SourceManifest.create(
        kind="mot",
        name="ground-truth-fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=2),
        ground_truth_sha256=ground_truth_payload_sha256(ground_truth, frame_count=2),
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=2,
        width=100,
        height=80,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=({"name": "baseline", "overrides": {"n_init": 2}},),
        metrics=("HOTA",),
        frame_range={"start": 0, "end": 2},
        visiontrack_version="0.2.0",
        git_revision="8d52ff2",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(
        tmp_path, experiment, source, detections, ground_truth
    )
    return bundle, source


def test_bundle_stores_and_verifies_exact_ground_truth(tmp_path: Path) -> None:
    bundle, source = _bundle_with_ground_truth(tmp_path)
    payload = (bundle / "inputs/ground_truth.jsonl").read_bytes()
    verify_ground_truth_payload(source, payload)
    load_experiment_bundle(bundle)

    (bundle / "inputs/ground_truth.jsonl").write_bytes(payload + b" ")
    with pytest.raises(ValueError, match="ground-truth payload SHA-256"):
        load_experiment_bundle(bundle)


def test_bundle_requires_manifest_and_ground_truth_to_agree(tmp_path: Path) -> None:
    detections = [DetectionRecord(0, None, 0, (0, 0, 10, 20), 0.9, 1)]
    source = SourceManifest.create(
        kind="synthetic",
        name="no-ground-truth",
        detection_sha256=detection_payload_sha256(detections, frame_count=1),
        ground_truth_sha256=None,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=1,
        width=20,
        height=20,
        fps=None,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=({"name": "baseline", "overrides": {}},),
        metrics=("track_count",),
        frame_range={"start": 0, "end": 1},
        visiontrack_version="0.2.0",
        git_revision=None,
        environment={"python": "3.12"},
        created_at=NOW,
    )
    unexpected = [GroundTruthRecord(0, 1, 1, (0, 0, 10, 20), 1, 1.0, False)]
    with pytest.raises(ValueError, match="declares none"):
        create_experiment_bundle(tmp_path, experiment, source, detections, unexpected)


def test_summary_recognizes_verified_ground_truth_but_defers_metrics(tmp_path: Path) -> None:
    bundle, _ = _bundle_with_ground_truth(tmp_path)
    run_comparison(bundle)
    summary = create_comparison_summary(bundle)
    assert summary["evidence"]["ground_truth_status"] == "available_unmeasured"
    assert all(
        item["reason"] == "metric_integration_not_implemented"
        for item in summary["insufficient_evidence"]
    )
