"""Reliability Lab image evidence stays optional, local, and content-addressed."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest

from visiontrack.lab import (
    EvidenceImageArtifact,
    EvidenceManifest,
    FailureEvent,
    SourceManifest,
    read_evidence_manifest,
    verify_evidence_image_payload,
    write_evidence_manifest,
    write_failure_jsonl,
)

NOW = "2026-09-20T10:00:00Z"
RUN_ID = "1" * 64


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png_bytes(width: int = 4, height: int = 3) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + (b"\x20\x40\x60\xff" * width)
    return (
        signature
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(row * height))
        + _chunk(b"IEND", b"")
    )


def image_artifact(
    payload: bytes,
    *,
    path: str = "frame-000001.png",
    frame: int = 1,
    width: int = 4,
    height: int = 3,
    view: str = "full_frame",
    privacy: str = "synthetic",
) -> EvidenceImageArtifact:
    return EvidenceImageArtifact(
        relative_path=path,
        frame_index=frame,
        image_sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
        media_type="image/png",
        width=width,
        height=height,
        view=view,
        privacy=privacy,
    )


def source_manifest() -> SourceManifest:
    return SourceManifest.create(
        kind="synthetic",
        name="evidence-fixture",
        detection_sha256="a" * 64,
        ground_truth_sha256="b" * 64,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=3,
        width=4,
        height=3,
        fps=30.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )


def failure_event() -> FailureEvent:
    return FailureEvent.create(
        run_id=RUN_ID,
        frame_index=1,
        event_type="miss",
        track_ids=(),
        ground_truth_ids=(7,),
        context={"metric_id": "c" * 64},
        evidence_frames={"start": 0, "end": 3},
    )


def evidence_manifest(*artifacts: EvidenceImageArtifact) -> EvidenceManifest:
    source = source_manifest()
    failure = failure_event()
    return EvidenceManifest.create(
        source_id=source.source_id,
        run_id=failure.run_id,
        event_id=failure.event_id,
        event_frame_index=failure.frame_index,
        evidence_frames=failure.evidence_frames,
        artifacts=artifacts,
    )


def make_bundle(tmp_path: Path) -> tuple[Path, SourceManifest, FailureEvent]:
    source = source_manifest()
    failure = failure_event()
    bundle = tmp_path / "bundle"
    run = bundle / "runs" / "baseline"
    run.mkdir(parents=True)
    (bundle / "source.json").write_text(source.to_json() + "\n", encoding="utf-8")
    (run / "run.json").write_text(
        json.dumps({"source_id": source.source_id, "run_id": RUN_ID}) + "\n",
        encoding="utf-8",
    )
    write_failure_jsonl(run / "failures.jsonl", [failure], frame_count=source.frame_count)
    return bundle, source, failure


def test_evidence_manifest_is_content_addressed_sorted_and_allows_no_media() -> None:
    full = png_bytes()
    crop = png_bytes(2, 2)
    artifacts = (
        image_artifact(full),
        image_artifact(crop, path="frame-000000-crop.png", frame=0, width=2, height=2, view="crop"),
    )
    manifest = evidence_manifest(*artifacts)

    assert [item.frame_index for item in manifest.artifacts] == [0, 1]
    assert EvidenceManifest.from_json(manifest.to_json()) == manifest
    assert evidence_manifest(*reversed(artifacts)).evidence_id == manifest.evidence_id
    assert evidence_manifest().artifacts == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"relative_path": "../frame.png"}, "relative_path"),
        ({"relative_path": "frame.jpg", "media_type": "image/jpeg"}, "image/png"),
        ({"frame_index": -1}, "frame_index"),
        ({"byte_length": 0}, "byte_length"),
        ({"width": 0}, "positive"),
        ({"view": "thumbnail"}, "view"),
        ({"privacy": "public"}, "privacy"),
    ],
)
def test_evidence_artifact_rejects_unsafe_or_ambiguous_metadata(change, message) -> None:
    payload = png_bytes()
    values = image_artifact(payload).to_dict()
    values.update(change)
    with pytest.raises(ValueError, match=message):
        EvidenceImageArtifact.from_dict(values)


def test_evidence_manifest_rejects_tampering_duplicates_and_out_of_range_frames() -> None:
    payload = png_bytes()
    artifact = image_artifact(payload)
    manifest = evidence_manifest(artifact)
    tampered = manifest.to_dict()
    tampered["event_frame_index"] = 2
    with pytest.raises(ValueError, match="evidence_id"):
        EvidenceManifest.from_dict(tampered)

    duplicate = image_artifact(payload, path="duplicate.png")
    with pytest.raises(ValueError, match="frame/view"):
        evidence_manifest(artifact, duplicate)

    outside = image_artifact(payload, path="outside.png", frame=3)
    with pytest.raises(ValueError, match="within evidence_frames"):
        evidence_manifest(outside)


def test_evidence_lineage_checks_source_event_range_and_dimensions() -> None:
    source = source_manifest()
    failure = failure_event()
    valid = evidence_manifest(image_artifact(png_bytes()))
    valid.verify_lineage(source, failure)

    oversized = image_artifact(png_bytes(5, 3), width=5, height=3, view="crop")
    with pytest.raises(ValueError, match="exceed"):
        evidence_manifest(oversized).verify_lineage(source, failure)

    wrong_source = SourceManifest.create(
        kind=source.kind,
        name="different",
        detection_sha256=source.detection_sha256,
        ground_truth_sha256=source.ground_truth_sha256,
        video_sha256=source.video_sha256,
        detector=source.detector,
        frame_count=source.frame_count,
        width=source.width,
        height=source.height,
        fps=source.fps,
        coordinate_space=source.coordinate_space,
        created_at=NOW,
    )
    with pytest.raises(ValueError, match="source_id"):
        valid.verify_lineage(wrong_source, failure)


def test_png_payload_verification_checks_hash_size_structure_and_dimensions() -> None:
    payload = png_bytes()
    artifact = image_artifact(payload)
    verify_evidence_image_payload(artifact, payload)

    with pytest.raises(ValueError, match="byte_length"):
        verify_evidence_image_payload(artifact, payload + b"x")
    wrong_dimensions = image_artifact(payload, width=3)
    with pytest.raises(ValueError, match="dimensions"):
        verify_evidence_image_payload(wrong_dimensions, payload)
    corrupt = bytearray(payload)
    corrupt[-1] ^= 1
    corrupt_payload = bytes(corrupt)
    with pytest.raises(ValueError, match="CRC"):
        verify_evidence_image_payload(image_artifact(corrupt_payload), corrupt_payload)


def test_evidence_storage_is_atomic_idempotent_and_local_to_failure(tmp_path: Path) -> None:
    bundle, source, failure = make_bundle(tmp_path)
    payload = png_bytes()
    artifact = image_artifact(payload)
    manifest = evidence_manifest(artifact)

    path = write_evidence_manifest(bundle, "baseline", manifest, {artifact.relative_path: payload})
    expected = bundle / "runs" / "baseline" / "evidence" / failure.event_id
    assert path == expected / "manifest.json"
    assert path.read_text().endswith("\n")
    assert (expected / artifact.relative_path).read_bytes() == payload
    assert (
        write_evidence_manifest(
            bundle, "baseline", manifest, {artifact.relative_path: payload}
        )
        == path
    )
    assert read_evidence_manifest(path, source=source, failure=failure) == manifest
    assert not list((bundle / "runs" / "baseline" / "evidence").glob(f".{failure.event_id}.*"))

    orphan = expected / "orphan.png"
    orphan.write_bytes(payload)
    with pytest.raises(ValueError, match="do not match"):
        read_evidence_manifest(path, source=source, failure=failure)
    orphan.unlink()
    (expected / artifact.relative_path).write_bytes(payload + b"x")
    with pytest.raises(ValueError, match="byte_length"):
        read_evidence_manifest(path, source=source, failure=failure)


def test_evidence_storage_refuses_missing_conflicting_or_mismatched_inputs(tmp_path: Path) -> None:
    bundle, _, _ = make_bundle(tmp_path)
    payload = png_bytes()
    artifact = image_artifact(payload)
    manifest = evidence_manifest(artifact)

    with pytest.raises(ValueError, match="paths"):
        write_evidence_manifest(bundle, "baseline", manifest, {})
    bad_manifest = EvidenceManifest.create(
        source_id=manifest.source_id,
        run_id="2" * 64,
        event_id=manifest.event_id,
        event_frame_index=manifest.event_frame_index,
        evidence_frames=manifest.evidence_frames,
        artifacts=(artifact,),
    )
    with pytest.raises(ValueError, match="run_id"):
        write_evidence_manifest(bundle, "baseline", bad_manifest, {artifact.relative_path: payload})

    path = write_evidence_manifest(bundle, "baseline", manifest, {artifact.relative_path: payload})
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="manifest.json"):
        write_evidence_manifest(bundle, "baseline", manifest, {artifact.relative_path: payload})
