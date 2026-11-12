"""Load local localization-audit inputs and verify the referenced image bytes.

This is an input-integrity check, not an assertion about permission, annotation
independence, camera identity, or detector provenance. Keep media outside Git.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from pathlib import Path

from PIL import Image

from experiments.localization_outcome import SPREAD_STATUSES, DetectionRow, Frame, ReferenceRow

SCHEMA = "visiontrack.localization-input/v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _fields(value: object, expected: set[str], context: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{context} needs exactly: {', '.join(sorted(expected))}")
    return value


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a nonempty string")
    return value


def _number(value: object, context: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{context} must be a finite number")
    return float(value)


def _box(value: object, width: int, height: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{context} needs four coordinates")
    x1, y1, x2, y2 = (_number(v, context) for v in value)
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"{context} is outside the image or has no area")
    return (x1, y1, x2, y2)


def _image(path: Path, root: Path, expected_hash: object, width: object,
           height: object) -> str:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("image path must stay relative to the manifest directory")
    resolved = (root / path).resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("image path escapes the manifest directory")
    if not resolved.is_file():
        raise ValueError("image path is not a file")
    if not isinstance(expected_hash, str) or _HASH.fullmatch(expected_hash) is None:
        raise ValueError("image_sha256 must be 64 lowercase hex digits")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("image width and height must be positive integers")
    data = resolved.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_hash:
        raise ValueError(f"image SHA-256 mismatch: {path}")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            actual_size = image.size
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid image: {path}") from exc
    if actual_size != (width, height):
        raise ValueError(f"image dimensions disagree: {path}")
    return digest


def load_frames(manifest_path: Path) -> tuple[list[Frame], dict]:
    """Read a frozen local manifest and bind every frame to image bytes.

    The caller must separately review source rights, scene units and reference
    labels before interpreting ``compare(..., require_image_hashes=True)``.
    """
    manifest_path = manifest_path.resolve(strict=True)
    manifest_bytes = manifest_path.read_bytes()
    data = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs,
                      parse_constant=_invalid_constant)
    data = _fields(data, {"schema", "source_id", "frames"}, "manifest")
    if data["schema"] != SCHEMA:
        raise ValueError("unsupported localization input schema")
    source_id = _string(data["source_id"], "source_id")
    records = data["frames"]
    if not isinstance(records, list) or not records:
        raise ValueError("manifest needs at least one frame")
    root = manifest_path.parent
    frames: list[Frame] = []
    seen: set[tuple[str, str]] = set()
    scene_splits: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for index, raw in enumerate(records):
        context = f"frame {index}"
        row = _fields(raw, {"split", "scene", "key", "image", "image_sha256",
                            "width", "height", "detections", "references"}, context)
        split = row["split"]
        if split not in ("development", "test"):
            raise ValueError(f"{context}: invalid split")
        scene = _string(row["scene"], f"{context} scene")
        key = _string(row["key"], f"{context} key")
        if (scene, key) in seen:
            raise ValueError(f"{context}: duplicate scene/frame key")
        seen.add((scene, key))
        if scene in scene_splits and scene_splits[scene] != split:
            raise ValueError(f"{context}: scene leaks across splits")
        scene_splits[scene] = split
        relative = Path(_string(row["image"], f"{context} image"))
        digest = _image(relative, root, row["image_sha256"], row["width"],
                        row["height"])
        if digest in hashes and hashes[digest] != split:
            raise ValueError(f"{context}: source image leaks across splits")
        hashes[digest] = split
        if not isinstance(row["detections"], list) or not isinstance(row["references"], list):
            raise ValueError(f"{context}: detections and references must be lists")
        detections = []
        for n, raw_det in enumerate(row["detections"]):
            name = f"{context} detection {n}"
            det = _fields(raw_det, {"class_id", "xyxy", "score", "spread_status",
                                    "spread", "group_size"}, name)
            score = _number(det["score"], f"{name} score")
            status = _string(det["spread_status"], f"{name} spread status")
            spread = (None if det["spread"] is None
                      else _number(det["spread"], f"{name} spread"))
            group_size = det["group_size"]
            if not 0 <= score <= 1 or status not in SPREAD_STATUSES:
                raise ValueError(f"{name}: invalid score or spread status")
            if (status == "supported") != (spread is not None) or (
                spread is not None and spread < 0
            ):
                raise ValueError(f"{name}: spread does not match status")
            if group_size is not None and (
                type(group_size) is not int or group_size < 1
                or (status == "supported" and group_size < 3)
            ):
                raise ValueError(f"{name}: invalid group size")
            detections.append(DetectionRow(
                _string(det["class_id"], f"{name} class"),
                _box(det["xyxy"], row["width"], row["height"], name),
                score, status, spread, group_size,
            ))
        references = []
        for n, raw_ref in enumerate(row["references"]):
            name = f"{context} reference {n}"
            ref = _fields(raw_ref, {"class_id", "xyxy", "eligible", "visibility"}, name)
            if type(ref["eligible"]) is not bool:
                raise ValueError(f"{name} eligible must be boolean")
            references.append(ReferenceRow(
                _string(ref["class_id"], f"{name} class"),
                _box(ref["xyxy"], row["width"], row["height"], name),
                ref["eligible"], _string(ref["visibility"], f"{name} visibility"),
            ))
        frames.append(Frame(split, scene, key, tuple(detections), tuple(references), digest))
    return frames, {
        "schema": SCHEMA,
        "source_id": source_id,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "frames": len(frames),
        "scenes": len(scene_splits),
        "verified_image_files": len(frames),
        "independent_labels_verified_by_this_loader": False,
        "source_rights_verified_by_this_loader": False,
        "camera_units_verified_by_this_loader": False,
    }
