"""Reliability Lab image evidence stays optional, local, and content-addressed."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest

from visiontrack.cli import main as cli_main
from visiontrack.lab import (
    EvidenceImageArtifact,
    EvidenceManifest,
    FailureEvent,
    SourceManifest,
    plan_failure_evidence,
    produce_failure_evidence,
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


def source_manifest(*, kind: str = "synthetic") -> SourceManifest:
    return SourceManifest.create(
        kind=kind,
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


def failure_event(*, context: dict | None = None) -> FailureEvent:
    return FailureEvent.create(
        run_id=RUN_ID,
        frame_index=1,
        event_type="miss",
        track_ids=(),
        ground_truth_ids=(7,),
        context=context or {"metric_id": "c" * 64},
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


def make_bundle(
    tmp_path: Path,
    *,
    source_kind: str = "synthetic",
    failure_context: dict | None = None,
) -> tuple[Path, SourceManifest, FailureEvent]:
    source = source_manifest(kind=source_kind)
    failure = failure_event(context=failure_context)
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


def test_evidence_artifact_validates_additive_production_provenance() -> None:
    payload = png_bytes()
    values = image_artifact(payload).to_dict()
    values["source_image_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="both be present"):
        EvidenceImageArtifact.from_dict(values)

    values["production"] = {
        "kind": "full_frame",
        "crop_bounds": None,
        "redaction": "pixelate_max_8x8",
    }
    with pytest.raises(ValueError, match="redacted privacy"):
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
        write_evidence_manifest(bundle, "baseline", manifest, {artifact.relative_path: payload})
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


def test_evidence_producer_defaults_to_a_bounded_synthetic_crop(tmp_path: Path) -> None:
    bundle, source, failure = make_bundle(tmp_path)
    source_payload = png_bytes()

    path = produce_failure_evidence(
        bundle,
        "baseline",
        failure.event_id,
        {failure.frame_index: source_payload},
        crop_bounds=(1, 0, 4, 3),
    )
    manifest = read_evidence_manifest(path, source=source, failure=failure)
    artifact = manifest.artifacts[0]

    assert artifact.view == "crop"
    assert artifact.privacy == "synthetic"
    assert (artifact.width, artifact.height) == (3, 3)
    assert artifact.source_image_sha256 == hashlib.sha256(source_payload).hexdigest()
    assert artifact.production == {
        "kind": "crop",
        "crop_bounds": [1, 0, 4, 3],
        "redaction": None,
    }
    assert artifact.relative_path == "frame-000001-crop.png"
    assert (
        produce_failure_evidence(
            bundle,
            "baseline",
            failure.event_id,
            {failure.frame_index: source_payload},
            crop_bounds=(1, 0, 4, 3),
        )
        == path
    )


def test_evidence_producer_derives_default_crop_from_failure_boxes(tmp_path: Path) -> None:
    bundle, source, failure = make_bundle(
        tmp_path,
        failure_context={
            "metric_id": "c" * 64,
            "ground_truth_box": [1, 1, 3, 3],
            "track_box": [2, 0, 4, 2],
        },
    )
    path = produce_failure_evidence(
        bundle,
        "baseline",
        failure.event_id,
        {failure.frame_index: png_bytes()},
    )
    artifact = read_evidence_manifest(path, source=source, failure=failure).artifacts[0]

    assert artifact.view == "crop"
    assert artifact.production["crop_bounds"] == [0, 0, 4, 3]


def test_evidence_producer_derives_privacy_from_its_operation(tmp_path: Path) -> None:
    source_payload = png_bytes()
    redacted_bundle, redacted_source, redacted_failure = make_bundle(
        tmp_path / "redacted", source_kind="mot"
    )
    with pytest.raises(ValueError, match="explicit opt-in"):
        produce_failure_evidence(
            redacted_bundle,
            "baseline",
            redacted_failure.event_id,
            {redacted_failure.frame_index: source_payload},
            view="full_frame",
        )

    redacted_path = produce_failure_evidence(
        redacted_bundle,
        "baseline",
        redacted_failure.event_id,
        {redacted_failure.frame_index: source_payload},
        view="full_frame",
        redact=True,
    )
    redacted = read_evidence_manifest(
        redacted_path, source=redacted_source, failure=redacted_failure
    ).artifacts[0]
    assert redacted.privacy == "redacted"
    assert redacted.production["redaction"] == "pixelate_max_8x8"
    assert redacted.image_sha256 != redacted.source_image_sha256

    source_bundle, source, source_failure = make_bundle(
        tmp_path / "source-pixels", source_kind="mot"
    )
    source_path = produce_failure_evidence(
        source_bundle,
        "baseline",
        source_failure.event_id,
        {source_failure.frame_index: source_payload},
        view="full_frame",
        allow_full_frame_source_pixels=True,
    )
    source_artifact = read_evidence_manifest(
        source_path, source=source, failure=source_failure
    ).artifacts[0]
    assert source_artifact.privacy == "source_pixels"
    assert source_artifact.production["redaction"] is None


def test_evidence_producer_rejects_ambiguous_unsafe_and_conflicting_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_payload = png_bytes()
    ambiguous, _, failure = make_bundle(tmp_path / "ambiguous")
    with pytest.raises(ValueError, match="crop_bounds are required"):
        produce_failure_evidence(
            ambiguous,
            "baseline",
            failure.event_id,
            {failure.frame_index: source_payload},
        )
    with pytest.raises(ValueError, match="outside the failure evidence range"):
        produce_failure_evidence(
            ambiguous,
            "baseline",
            failure.event_id,
            {3: source_payload},
            crop_bounds=(0, 0, 2, 2),
        )

    conflict, _, conflict_failure = make_bundle(tmp_path / "conflict")
    produce_failure_evidence(
        conflict,
        "baseline",
        conflict_failure.event_id,
        {conflict_failure.frame_index: source_payload},
        crop_bounds=(0, 0, 2, 2),
    )
    with pytest.raises(FileExistsError, match="conflicting content"):
        produce_failure_evidence(
            conflict,
            "baseline",
            conflict_failure.event_id,
            {conflict_failure.frame_index: source_payload},
            crop_bounds=(1, 0, 4, 3),
        )

    limited, _, limited_failure = make_bundle(tmp_path / "limited")
    monkeypatch.setattr("visiontrack.lab.evidence.MAX_EVIDENCE_IMAGE_PIXELS", 4)
    with pytest.raises(ValueError, match="output pixel limit"):
        produce_failure_evidence(
            limited,
            "baseline",
            limited_failure.event_id,
            {limited_failure.frame_index: source_payload},
            crop_bounds=(0, 0, 3, 3),
        )


def test_evidence_plan_previews_resolved_operation_without_writing(tmp_path: Path) -> None:
    bundle, _, failure = make_bundle(
        tmp_path,
        source_kind="mot",
        failure_context={
            "metric_id": "c" * 64,
            "ground_truth_box": [1, 1, 3, 3],
            "track_box": None,
        },
    )

    plan = plan_failure_evidence(
        bundle,
        "baseline",
        failure.event_id,
        [failure.frame_index],
        view="full_frame",
    )

    assert plan.frame_indices == (failure.frame_index,)
    assert plan.output_size == (4, 3)
    assert plan.privacy == "source_pixels"
    assert plan.requires_full_frame_confirmation is True
    assert not (bundle / "runs/baseline/evidence").exists()


def test_lab_evidence_cli_previews_then_writes_explicit_png(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _, failure = make_bundle(tmp_path)
    png_path = tmp_path / "frame.png"
    arguments = [
        "lab-evidence",
        str(bundle),
        "baseline",
        failure.event_id,
        "--frame",
        f"{failure.frame_index}={png_path}",
        "--crop",
        "1,0,4,3",
    ]

    assert cli_main(arguments) == 0
    preview = capsys.readouterr()
    assert "Evidence production preview" in preview.out
    assert "privacy: synthetic" in preview.out
    assert "Preview only; no PNG inputs were read and nothing was written." in preview.out
    assert not (bundle / "runs/baseline/evidence").exists()

    png_path.write_bytes(png_bytes())
    assert cli_main([*arguments, "--write"]) == 0
    written = capsys.readouterr()
    assert "Wrote 1 verified artifact(s)" in written.out
    assert "manifest:" in written.out
    assert (bundle / "runs/baseline/evidence" / failure.event_id / "manifest.json").is_file()


def test_lab_evidence_cli_requires_full_frame_confirmation_before_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _, failure = make_bundle(tmp_path, source_kind="mot")
    png_path = tmp_path / "frame.png"
    png_path.write_bytes(png_bytes())
    arguments = [
        "lab-evidence",
        str(bundle),
        "baseline",
        failure.event_id,
        "--frame",
        f"{failure.frame_index}={png_path}",
        "--view",
        "full_frame",
    ]

    assert cli_main(arguments) == 0
    preview = capsys.readouterr()
    assert "full-frame source-pixel confirmation: required" in preview.out

    assert cli_main([*arguments, "--write"]) == 2
    blocked = capsys.readouterr()
    assert "--allow-full-frame-source-pixels" in blocked.err
    assert not (bundle / "runs/baseline/evidence").exists()

    assert cli_main([*arguments, "--write", "--allow-full-frame-source-pixels"]) == 0
    confirmed = capsys.readouterr()
    assert "full-frame source-pixel confirmation: confirmed" in confirmed.out
    assert "Wrote 1 verified artifact(s)" in confirmed.out
