"""Check one pinned UVH-26 image for proposal-audit feasibility, not accuracy.

Keep publisher images and annotations outside Git. This checks source integrity,
COCO geometry, normal/captured detection parity, and feature abstention. The
release has no camera IDs, so this cannot produce a scene-separated test result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from experiments.localization_signal import audit_capture
from visiontrack.detection.yolox_onnx import YoloxDetector

ANNOTATION_SHA256 = "9d279f48589e653d7749b9636c945a8763b457c067f23ea79def3fa70c8e8ab4"
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
ROAD_CLASSES = {2, 3, 5, 7}  # COCO car, motorcycle, bus, truck; no label mapping here.
INPUT_SIZE = 416
FULL_FRAME_CAP = sum((INPUT_SIZE // stride) ** 2 for stride in (8, 16, 32))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _annotation_inventory(data: dict) -> tuple[dict[str, dict], Counter[str]]:
    if data.get("licenses") != [{
        "id": 1, "name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"
    }]:
        raise ValueError("unexpected dataset annotation license record")
    images = data["images"]
    annotations = data["annotations"]
    categories = data["categories"]
    by_id = {item["id"]: item for item in images}
    if len(by_id) != len(images) or len({a["id"] for a in annotations}) != len(annotations):
        raise ValueError("duplicate image or annotation ID")
    by_name = {item["file_name"]: item for item in images}
    if len(by_name) != len(images) or any(item.get("license") != 1 for item in images):
        raise ValueError("duplicate image filename or unexpected license ID")
    category_ids = {item["id"] for item in categories}
    if len(category_ids) != len(categories):
        raise ValueError("duplicate category ID")
    counts: Counter[str] = Counter()
    for item in annotations:
        image = by_id.get(item["image_id"])
        if image is None or item["category_id"] not in category_ids:
            raise ValueError("annotation references missing image or class")
        x, y, width, height = item["bbox"]
        if (
            not all(math.isfinite(v) for v in (x, y, width, height))
            or x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > image["width"] + 1e-6
            or y + height > image["height"] + 1e-6
        ):
            raise ValueError("invalid or out-of-image annotation box")
        counts["annotations"] += 1
        if not math.isclose(item["area"], width * height, rel_tol=1e-8, abs_tol=1e-4):
            counts["area_differs_from_box"] += 1
            if abs(item["area"] - width * height) / (width * height) > 0.01:
                counts["area_differs_over_1pct"] += 1
                if (
                    x < 1e-5 or y < 1e-5
                    or image["width"] - x - width < 1e-5
                    or image["height"] - y - height < 1e-5
                ):
                    counts["over_1pct_and_touches_edge"] += 1
    return by_name, counts


def preflight(annotations: Path, image_path: Path, model_path: Path) -> dict:
    if _sha256(annotations) != ANNOTATION_SHA256:
        raise ValueError("UVH-26 v1.0 validation annotation fingerprint mismatch")
    if _sha256(model_path) != MODEL_SHA256:
        raise ValueError("YOLOX nano model fingerprint mismatch")
    data = json.loads(annotations.read_text(encoding="utf-8"))
    by_name, counts = _annotation_inventory(data)
    image_record = by_name.get(image_path.name)
    if image_record is None:
        raise ValueError("image filename absent from pinned annotation file")

    from PIL import Image

    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    if (rgb.shape[1], rgb.shape[0]) != (image_record["width"], image_record["height"]):
        raise ValueError("image dimensions disagree with annotation metadata")
    bgr = rgb[:, :, ::-1].copy()
    detector = YoloxDetector(str(model_path), input_size=INPUT_SIZE,
                             class_filter=ROAD_CLASSES)
    detections, capture = detector.detect_with_proposals(
        bgr, max_proposals=FULL_FRAME_CAP
    )
    ordinary = detector.detect(bgr)
    def values(rows):
        return [(d.class_id, d.score, tuple(d.xyxy)) for d in rows]
    if values(detections) != values(ordinary):
        raise ValueError("proposal capture changed ordinary detections")
    audit = audit_capture(capture)
    if capture.truncated or audit.frame_status != "complete":
        raise ValueError("pinned full-frame capture was incomplete")
    statuses = Counter(row.status for row in audit.rows)
    image_annotations = [a for a in data["annotations"]
                         if a["image_id"] == image_record["id"]]
    return {
        "schema": "visiontrack.uvh26-localization-preflight/v1",
        "source": "iisc-aim/UVH-26@v1.0, UVH-26-MV-Val",
        "scope": "one-image detector/capture feasibility; not an outcome study",
        "annotation_sha256": ANNOTATION_SHA256,
        "image_name": image_path.name,
        "image_sha256": _sha256(image_path),
        "model_sha256": MODEL_SHA256,
        "image_count_in_annotation_file": len(by_name),
        "annotation_inventory": dict(counts),
        "selected_image_annotation_count": len(image_annotations),
        "model_input_size": INPUT_SIZE,
        "proposal_count": capture.total_proposals,
        "full_frame_cap": FULL_FRAME_CAP,
        "returned_detections": len(detections),
        "spread_status_counts": dict(statuses),
        "ordinary_detection_parity": True,
        "scene_ids_in_annotation_file": any(
            "scene_id" in item or "camera_id" in item for item in data["images"]
        ),
        "tracker_ran": False,
        "reference_matching_ran": False,
        "accuracy_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = preflight(args.annotations, args.image, args.model)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
