"""Explicit, privacy-aware production of local Reliability Lab image evidence."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from .contracts import EvidenceImageArtifact, EvidenceManifest, SourceManifest
from .storage import _png_dimensions, read_failure_jsonl, write_evidence_manifest

MAX_EVIDENCE_FRAMES = 25
MAX_SOURCE_IMAGE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_IMAGE_PIXELS = 16_777_216
MAX_EVIDENCE_IMAGE_BYTES = 16 * 1024 * 1024
MAX_EVIDENCE_IMAGE_PIXELS = 4_194_304
DEFAULT_CROP_PADDING = 16
_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _pillow_image() -> Any:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised without the lab extra
        raise RuntimeError(
            "Pillow is required to produce image evidence; install visiontrack-mot[lab]"
        ) from exc
    return Image


def _validated_crop_bounds(
    bounds: Sequence[int], *, width: int, height: int
) -> tuple[int, int, int, int]:
    try:
        values = tuple(bounds)
    except TypeError as exc:
        raise ValueError("crop_bounds must contain exactly four integers") from exc
    if (
        isinstance(bounds, (str, bytes))
        or len(values) != 4
        or any(not isinstance(value, int) or isinstance(value, bool) for value in values)
    ):
        raise ValueError("crop_bounds must contain exactly four integers")
    left, top, right, bottom = values
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("crop_bounds must define a positive rectangle")
    if right > width or bottom > height:
        raise ValueError("crop_bounds exceed the source dimensions")
    if (right - left) * (bottom - top) > MAX_EVIDENCE_IMAGE_PIXELS:
        raise ValueError("evidence crop exceeds the output pixel limit")
    return left, top, right, bottom


def _context_crop_bounds(
    context: Mapping[str, Any], *, width: int, height: int
) -> tuple[int, int, int, int]:
    boxes: list[tuple[float, float, float, float]] = []
    for key in ("ground_truth_box", "track_box"):
        value = context.get(key)
        if value is None:
            continue
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 4
            or any(
                not isinstance(coordinate, (int, float))
                or isinstance(coordinate, bool)
                or not math.isfinite(coordinate)
                for coordinate in value
            )
        ):
            raise ValueError(f"failure context {key} is not a finite xyxy box")
        left, top, right, bottom = (float(coordinate) for coordinate in value)
        if right <= left or bottom <= top:
            raise ValueError(f"failure context {key} does not define a positive box")
        boxes.append((left, top, right, bottom))
    if not boxes:
        raise ValueError(
            "crop_bounds are required when the failure context has no ground-truth or track box"
        )
    bounds = (
        max(0, math.floor(min(box[0] for box in boxes) - DEFAULT_CROP_PADDING)),
        max(0, math.floor(min(box[1] for box in boxes) - DEFAULT_CROP_PADDING)),
        min(width, math.ceil(max(box[2] for box in boxes) + DEFAULT_CROP_PADDING)),
        min(height, math.ceil(max(box[3] for box in boxes) + DEFAULT_CROP_PADDING)),
    )
    return _validated_crop_bounds(bounds, width=width, height=height)


def _encode_png(image: Any, *, redact: bool) -> bytes:
    Image = _pillow_image()
    output = image.convert("RGBA")
    if redact:
        reduced = (
            max(1, min(8, output.width // 2)),
            max(1, min(8, output.height // 2)),
        )
        resampling = getattr(Image, "Resampling", Image)
        output = output.resize(reduced, resample=resampling.NEAREST).resize(
            output.size,
            resample=resampling.NEAREST,
        )
    stream = BytesIO()
    output.save(stream, format="PNG", optimize=False, compress_level=9)
    payload = stream.getvalue()
    if len(payload) > MAX_EVIDENCE_IMAGE_BYTES:
        raise ValueError("produced evidence image exceeds the output byte limit")
    return payload


def produce_failure_evidence(
    bundle: str | Path,
    variant: str,
    event_id: str,
    frames: Mapping[int, bytes],
    *,
    view: str = "crop",
    crop_bounds: Sequence[int] | None = None,
    redact: bool = False,
    allow_full_frame_source_pixels: bool = False,
) -> Path:
    """Produce immutable PNG evidence from explicitly supplied local source frames.

    The default operation is a bounded crop. Synthetic source manifests are
    classified as synthetic automatically. Non-synthetic pixels are classified
    as source pixels unless this function applies its deterministic whole-image
    pixelation operation. Full-frame source pixels require an explicit opt-in.
    """
    if not isinstance(variant, str) or not _RUN_NAME.fullmatch(variant):
        raise ValueError("variant name must be a safe 1-64 character path component")
    if view not in {"crop", "full_frame"}:
        raise ValueError("view must be crop or full_frame")
    if not isinstance(redact, bool) or not isinstance(allow_full_frame_source_pixels, bool):
        raise ValueError("redact and allow_full_frame_source_pixels must be booleans")
    if not isinstance(frames, Mapping) or not frames:
        raise ValueError("frames must be a non-empty mapping of frame indices to PNG bytes")
    if len(frames) > MAX_EVIDENCE_FRAMES:
        raise ValueError(f"at most {MAX_EVIDENCE_FRAMES} evidence frames may be produced")

    bundle_path = Path(bundle)
    source_path = bundle_path / "source.json"
    failure_path = bundle_path / "runs" / variant / "failures.jsonl"
    if not source_path.is_file() or not failure_path.is_file():
        raise ValueError("source and failure artifacts are required before producing evidence")
    source = SourceManifest.from_json(source_path.read_text(encoding="utf-8"))
    if source.width * source.height > MAX_SOURCE_IMAGE_PIXELS:
        raise ValueError("source dimensions exceed the evidence producer pixel limit")
    failures = read_failure_jsonl(failure_path, frame_count=source.frame_count)
    matching = [failure for failure in failures if failure.event_id == event_id]
    if len(matching) != 1:
        raise ValueError("event_id must match exactly one stored failure event")
    failure = matching[0]

    if view == "crop":
        resolved_crop = (
            _context_crop_bounds(failure.context, width=source.width, height=source.height)
            if crop_bounds is None
            else _validated_crop_bounds(crop_bounds, width=source.width, height=source.height)
        )
        output_size = (
            resolved_crop[2] - resolved_crop[0],
            resolved_crop[3] - resolved_crop[1],
        )
    else:
        if crop_bounds is not None:
            raise ValueError("full-frame evidence must not declare crop_bounds")
        resolved_crop = None
        output_size = (source.width, source.height)
        if source.width * source.height > MAX_EVIDENCE_IMAGE_PIXELS:
            raise ValueError("full-frame evidence exceeds the output pixel limit")

    privacy = (
        "redacted" if redact else ("synthetic" if source.kind == "synthetic" else "source_pixels")
    )
    if view == "full_frame" and privacy == "source_pixels" and not allow_full_frame_source_pixels:
        raise ValueError(
            "full-frame source pixels require explicit opt-in with "
            "allow_full_frame_source_pixels=True"
        )

    Image = _pillow_image()
    artifacts: list[EvidenceImageArtifact] = []
    payloads: dict[str, bytes] = {}
    start, end = failure.evidence_frames["start"], failure.evidence_frames["end"]
    for frame_index, source_payload in frames.items():
        if not isinstance(frame_index, int) or isinstance(frame_index, bool):
            raise ValueError("evidence frame indices must be integers")
        if not start <= frame_index < end:
            raise ValueError("evidence frame_index is outside the failure evidence range")
        if not isinstance(source_payload, bytes):
            raise ValueError("source PNG payloads must be bytes")
        if len(source_payload) > MAX_SOURCE_IMAGE_BYTES:
            raise ValueError("source PNG payload exceeds the input byte limit")
    for frame_index, source_payload in sorted(frames.items()):
        if _png_dimensions(source_payload) != (source.width, source.height):
            raise ValueError("source PNG dimensions do not match the source manifest")
        try:
            with Image.open(BytesIO(source_payload)) as image:
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("source evidence must be a single-frame PNG")
                image.load()
                produced = image.crop(resolved_crop) if resolved_crop is not None else image.copy()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("source evidence PNG could not be decoded") from exc
        if produced.size != output_size:
            raise ValueError("produced evidence dimensions do not match the requested operation")
        payload = _encode_png(produced, redact=redact)
        relative_path = f"frame-{frame_index:06d}-{view}.png"
        production = {
            "kind": view,
            "crop_bounds": list(resolved_crop) if resolved_crop is not None else None,
            "redaction": "pixelate_max_8x8" if redact else None,
        }
        artifact = EvidenceImageArtifact(
            relative_path=relative_path,
            frame_index=frame_index,
            image_sha256=hashlib.sha256(payload).hexdigest(),
            byte_length=len(payload),
            media_type="image/png",
            width=output_size[0],
            height=output_size[1],
            view=view,
            privacy=privacy,
            source_image_sha256=hashlib.sha256(source_payload).hexdigest(),
            production=production,
        )
        artifacts.append(artifact)
        payloads[relative_path] = payload

    manifest = EvidenceManifest.create(
        source_id=source.source_id,
        run_id=failure.run_id,
        event_id=failure.event_id,
        event_frame_index=failure.frame_index,
        evidence_frames=failure.evidence_frames,
        artifacts=artifacts,
    )
    return write_evidence_manifest(bundle_path, variant, manifest, payloads)
