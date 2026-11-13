"""Replay pinned YOLOX inference to verify local localization-audit rows.

This checks detector provenance only. Reference labels, scene identity and media
permission remain independent research-admission requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

from experiments.localization_input import _box, load_frames
from experiments.localization_signal import audit_capture
from visiontrack.detection.yolox_onnx import YoloxDetector

_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_replay(
    manifest_path: Path,
    model_path: Path,
    model_sha256: str,
    class_map: dict[int, str],
    *,
    input_size: int,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_proposals: int | None = None,
    populate_output: Path | None = None,
) -> dict:
    """Run one pinned detector pass for verification or manifest population."""
    manifest_path = manifest_path.resolve(strict=True)
    model_path = model_path.resolve(strict=True)
    if not isinstance(model_sha256, str) or _HASH.fullmatch(model_sha256) is None:
        raise ValueError("model_sha256 must be 64 lowercase hex digits")
    if _sha256(model_path) != model_sha256:
        raise ValueError("model SHA-256 mismatch")
    if not class_map or any(
        type(cid) is not int or cid < 0 or not isinstance(label, str) or not label.strip()
        for cid, label in class_map.items()
    ) or len(set(class_map.values())) != len(class_map):
        raise ValueError("class_map needs unique nonempty labels for integer classes")
    if type(input_size) is not int or input_size <= 0:
        raise ValueError("input_size must be a positive integer")
    if not all(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
        for value in (conf_threshold, iou_threshold)
    ):
        raise ValueError("confidence and IoU thresholds must be finite in [0, 1]")
    if max_proposals is None:
        max_proposals = sum((input_size // stride) ** 2 for stride in (8, 16, 32))
    frames, input_receipt = load_frames(manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != input_receipt["manifest_sha256"]:
        raise ValueError("manifest changed during replay setup")
    records = json.loads(manifest_bytes)["frames"]
    if populate_output is not None:
        populate_output = populate_output.resolve()
        if populate_output.parent != manifest_path.parent or populate_output.exists():
            raise ValueError("populate output must be a new file beside the input manifest")
        if any(frame.detections for frame in frames):
            raise ValueError("populate input must have empty detection lists")
    detector = YoloxDetector(
        str(model_path), input_size=input_size, conf_threshold=conf_threshold,
        iou_threshold=iou_threshold, class_filter=set(class_map),
    )
    statuses: dict[str, int] = {}
    total_detections = 0
    generated: list[list[dict]] = []
    for frame, record in zip(frames, records, strict=True):
        context = f"{frame.scene}/{frame.key}"
        image_path = (manifest_path.parent / record["image"]).resolve(strict=True)
        if not image_path.is_relative_to(manifest_path.parent):
            raise ValueError(f"{context}: image path escaped during replay")
        image_bytes = image_path.read_bytes()
        if hashlib.sha256(image_bytes).hexdigest() != frame.image_sha256:
            raise ValueError(f"{context}: image changed after input verification")
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb = np.asarray(image.convert("RGB"))
        if (rgb.shape[1], rgb.shape[0]) != (record["width"], record["height"]):
            raise ValueError(f"{context}: decoded image dimensions changed")
        bgr = rgb[:, :, ::-1].copy()
        detections, capture = detector.detect_with_proposals(
            bgr, max_proposals=max_proposals,
        )
        if capture.truncated:
            raise ValueError(f"{context}: proposal capture was truncated")
        audit = audit_capture(capture)
        ordinary = detector.detect(bgr)
        def signature(rows):
            return [(d.class_id, d.score, tuple(d.xyxy)) for d in rows]
        if signature(detections) != signature(ordinary):
            raise ValueError(f"{context}: capture changed ordinary detections")
        if len(audit.rows) != len(detections):
            raise ValueError(f"{context}: detection count differs from replay")
        if populate_output is None and len(detections) != len(frame.detections):
            raise ValueError(f"{context}: detection count differs from replay")
        generated_rows = []
        for index, (actual, spread) in enumerate(zip(detections, audit.rows, strict=True)):
            if actual.class_id not in class_map:
                raise ValueError(f"{context}: unmapped detector class")
            _box(actual.xyxy.tolist(), record["width"], record["height"],
                 f"{context} detection {index}")
            if not math.isfinite(actual.score) or not 0 <= actual.score <= 1:
                raise ValueError(f"{context}: invalid detector score")
            generated_row = {
                "class_id": class_map[actual.class_id],
                "xyxy": [float(value) for value in actual.xyxy],
                "score": actual.score,
                "spread_status": spread.status,
                "spread": spread.spread,
                "group_size": spread.group_size,
            }
            if populate_output is None:
                declared = frame.detections[index]
                if (
                    declared.class_id != generated_row["class_id"]
                    or declared.xyxy != tuple(generated_row["xyxy"])
                    or declared.score != generated_row["score"]
                    or declared.spread_status != generated_row["spread_status"]
                    or declared.spread != generated_row["spread"]
                    or declared.group_size != generated_row["group_size"]
                ):
                    raise ValueError(f"{context}: detection {index} differs from replay")
            generated_rows.append(generated_row)
            statuses[spread.status] = statuses.get(spread.status, 0) + 1
        generated.append(generated_rows)
        total_detections += len(detections)
    if _sha256(manifest_path) != input_receipt["manifest_sha256"]:
        raise ValueError("manifest changed during detector replay")
    if _sha256(model_path) != model_sha256:
        raise ValueError("model changed during detector replay")
    receipt = {
        "schema": "visiontrack.localization-detector-replay/v1",
        "manifest_sha256": input_receipt["manifest_sha256"],
        "model_sha256": model_sha256,
        "input_size": input_size,
        "conf_threshold": conf_threshold,
        "iou_threshold": iou_threshold,
        "class_map": {str(k): v for k, v in sorted(class_map.items())},
        "max_proposals": max_proposals,
        "frames": len(frames),
        "detections": total_detections,
        "spread_status_counts": dict(sorted(statuses.items())),
        "image_hashes_verified": True,
        "ordinary_detection_parity": True,
        "declared_detector_rows_verified": populate_output is None,
        "independent_labels_verified": False,
        "camera_units_verified": False,
        "source_rights_verified": False,
    }
    if populate_output is not None:
        output_data = json.loads(manifest_bytes)
        for record, generated_rows in zip(output_data["frames"], generated, strict=True):
            record["detections"] = generated_rows
        output_bytes = (json.dumps(output_data, indent=2, sort_keys=True,
                                   allow_nan=False) + "\n").encode("utf-8")
        with populate_output.open("xb") as stream:
            stream.write(output_bytes)
        receipt["generated_manifest_sha256"] = hashlib.sha256(output_bytes).hexdigest()
        receipt["generated_manifest_path"] = str(populate_output)
    return receipt


def verify_replay(
    manifest_path: Path, model_path: Path, model_sha256: str,
    class_map: dict[int, str], *, input_size: int,
    conf_threshold: float = 0.25, iou_threshold: float = 0.45,
    max_proposals: int | None = None,
) -> dict:
    """Require declared rows to match pinned inference exactly.

    The supplied model hash is an independent pin. Environment-dependent
    inference drift fails closed rather than silently changing the study.
    """
    return _run_replay(
        manifest_path, model_path, model_sha256, class_map,
        input_size=input_size, conf_threshold=conf_threshold,
        iou_threshold=iou_threshold, max_proposals=max_proposals,
    )


def populate_manifest(
    manifest_path: Path, output_path: Path, model_path: Path,
    model_sha256: str, class_map: dict[int, str], *, input_size: int,
    conf_threshold: float = 0.25, iou_threshold: float = 0.45,
    max_proposals: int | None = None,
) -> dict:
    """Add replayed detector rows to a reference-only manifest, never overwrite."""
    return _run_replay(
        manifest_path, model_path, model_sha256, class_map,
        input_size=input_size, conf_threshold=conf_threshold,
        iou_threshold=iou_threshold, max_proposals=max_proposals,
        populate_output=output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--class-map", required=True,
                        help="comma-separated detector ID:reference label pairs, e.g. 2:car")
    parser.add_argument("--input-size", required=True, type=int)
    parser.add_argument("--conf-threshold", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--max-proposals", type=int)
    parser.add_argument("--populate-output", type=Path,
                        help="write a new manifest from a reference-only input")
    args = parser.parse_args()
    try:
        pairs = [pair.split(":", 1) for pair in args.class_map.split(",")]
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError("expected ID:label pairs")
        class_map = {int(cid): label for cid, label in pairs}
        if len(class_map) != len(pairs):
            raise ValueError("duplicate class ID")
    except (ValueError, IndexError) as exc:
        parser.error(f"invalid --class-map: {exc}")
    kwargs = dict(
        input_size=args.input_size, conf_threshold=args.conf_threshold,
        iou_threshold=args.iou_threshold, max_proposals=args.max_proposals,
    )
    if args.populate_output is None:
        receipt = verify_replay(
            args.manifest, args.model, args.model_sha256, class_map, **kwargs,
        )
    else:
        receipt = populate_manifest(
            args.manifest, args.populate_output, args.model,
            args.model_sha256, class_map, **kwargs,
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
