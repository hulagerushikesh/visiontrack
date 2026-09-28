"""Playback construction uses only sealed, explicitly stored local evidence."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest

from visiontrack.lab import (
    DetectionRecord,
    EvidenceImageArtifact,
    EvidenceManifest,
    ExperimentManifest,
    GroundTruthRecord,
    SourceManifest,
    build_failure_playback,
    calculate_bundle_metrics,
    calculate_failure_events,
    create_comparison_summary,
    create_experiment_bundle,
    detection_payload_sha256,
    generate_local_report,
    ground_truth_payload_sha256,
    read_failure_jsonl,
    run_comparison,
    write_evidence_manifest,
)

NOW = "2026-09-28T12:00:00Z"


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _png(width: int = 100, height: int = 80) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + (b"\x20\x40\x60\xff" * width)
    return (
        signature
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(row * height))
        + _chunk(b"IEND", b"")
    )


def _bundle(tmp_path: Path) -> Path:
    detections = [
        DetectionRecord(frame, frame, 0, (10 + frame, 10, 30 + frame, 50), 0.95, 1)
        for frame in range(4)
    ]
    ground_truth = [
        GroundTruthRecord(frame, frame, 1, (10 + frame, 10, 30 + frame, 50), 1, 1.0, False)
        for frame in range(4)
    ]
    source = SourceManifest.create(
        kind="synthetic",
        name="playback-builder-fixture",
        detection_sha256=detection_payload_sha256(detections, frame_count=4),
        ground_truth_sha256=ground_truth_payload_sha256(ground_truth, frame_count=4),
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=4,
        width=100,
        height=80,
        fps=25.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=(
            {"name": "baseline", "overrides": {"n_init": 2}},
            {"name": "patient", "overrides": {"n_init": 2, "max_age": 60}},
        ),
        metrics=("HOTA", "IDF1", "MOTA", "IDSW", "Frag"),
        frame_range={"start": 0, "end": 4},
        visiontrack_version="0.2.0",
        git_revision="c5261c2",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    bundle = create_experiment_bundle(tmp_path, experiment, source, detections, ground_truth)
    run_comparison(bundle)
    calculate_bundle_metrics(bundle)
    calculate_failure_events(bundle)
    create_comparison_summary(bundle)
    return bundle


def _add_evidence(bundle: Path, variant: str, *, view: str = "full_frame") -> str:
    source = SourceManifest.from_json((bundle / "source.json").read_text(encoding="utf-8"))
    failure = read_failure_jsonl(
        bundle / "runs" / variant / "failures.jsonl", frame_count=source.frame_count
    )[0]
    width, height = (source.width, source.height) if view == "full_frame" else (20, 20)
    payload = _png(width, height)
    artifact = EvidenceImageArtifact(
        relative_path=f"frame-{failure.frame_index:06d}-{view}.png",
        frame_index=failure.frame_index,
        image_sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        media_type="image/png",
        width=width,
        height=height,
        view=view,
        privacy="synthetic",
    )
    manifest = EvidenceManifest.create(
        source_id=source.source_id,
        run_id=failure.run_id,
        event_id=failure.event_id,
        event_frame_index=failure.frame_index,
        evidence_frames=failure.evidence_frames,
        artifacts=(artifact,),
    )
    write_evidence_manifest(bundle, variant, manifest, {artifact.relative_path: payload})
    return failure.event_id


def test_builder_creates_complete_synchronized_lanes_with_visible_gaps(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    event_id = _add_evidence(bundle, "patient")
    generate_local_report(bundle)
    before = {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }

    playback = build_failure_playback(bundle, event_id=event_id, variant="patient")

    assert [lane.variant for lane in playback.lanes] == ["baseline", "patient"]
    assert [frame.frame_index for frame in playback.lanes[0].frames] == [0, 1, 2]
    assert [frame.offset_ms for frame in playback.lanes[0].frames] == [0, 40, 80]
    assert all(frame.status == "missing" for frame in playback.lanes[0].frames)
    assert [frame.status for frame in playback.lanes[1].frames] == [
        "available",
        "missing",
        "missing",
    ]
    available = playback.lanes[1].frames[0]
    assert available.relative_path.startswith(f"runs/patient/evidence/{event_id}/")
    assert available.privacy == "synthetic"
    after = {
        path.relative_to(bundle): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_builder_uses_verified_counterpart_evidence_when_declared(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    baseline_event = _add_evidence(bundle, "baseline")
    patient_event = _add_evidence(bundle, "patient")
    generate_local_report(bundle)

    playback = build_failure_playback(bundle, event_id=patient_event, variant="patient")

    assert playback.anchor_event_id == patient_event
    assert playback.lanes[0].frames[0].status == "available"
    assert f"runs/baseline/evidence/{baseline_event}/" in playback.lanes[0].frames[0].relative_path
    assert playback.lanes[1].frames[0].status == "available"


def test_builder_treats_crop_only_evidence_as_missing_for_playback(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    event_id = _add_evidence(bundle, "patient", view="crop")
    generate_local_report(bundle)

    playback = build_failure_playback(bundle, event_id=event_id, variant="patient")

    assert all(frame.status == "missing" for lane in playback.lanes for frame in lane.frames)


def test_builder_requires_exact_sealed_report_event_and_variant(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    event_id = read_failure_jsonl(bundle / "runs/patient/failures.jsonl")[0].event_id
    with pytest.raises(ValueError, match="sealed report"):
        build_failure_playback(bundle, event_id=event_id, variant="patient")

    generate_local_report(bundle)
    with pytest.raises(ValueError, match="non-baseline"):
        build_failure_playback(bundle, event_id=event_id, variant="baseline")
    with pytest.raises(ValueError, match="exactly one event"):
        build_failure_playback(bundle, event_id="f" * 64, variant="patient")


def test_builder_rejects_stale_or_modified_report(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    event_id = read_failure_jsonl(bundle / "runs/patient/failures.jsonl")[0].event_id
    generate_local_report(bundle)
    report_path = bundle / "report/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source"]["name"] = "tampered"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        build_failure_playback(bundle, event_id=event_id, variant="patient")
