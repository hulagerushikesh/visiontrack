"""Private real-image proposal-coverage preflight; no localization outcome score.

Use the pinned Singapore LTA derivative outside Git. Its teacher-assisted,
single-annotator labels and excluded hard frames are not independent test truth.
This only checks source/annotation integrity and whether a fixed YOLOX detector
can emit complete, supported proposal features on the retained images.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

import numpy as np

from experiments.localization_signal import audit_capture
from visiontrack.detection.yolox_onnx import YoloxDetector

SOURCE_REVISION = "78428468834612d7fdd77e7cd097e8311c2754fe"
MANIFEST_SHA256 = "50262b0d2f52743317f065534cebcfd21b9176b38a9b95423a1505cbe1391360"
LABEL_SHA256 = "b5e9ba3e38616028b5f50561475369cea05846d6195a2c3b8484fccf5db4758c"
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
INPUT_SIZE = 416
FULL_FRAME_CAP = sum((INPUT_SIZE // stride) ** 2 for stride in (8, 16, 32))
ROAD_CLASSES = {2, 3, 5, 7}  # COCO car, motorcycle, bus, truck.
SOURCE_CLASSES = {"car", "motorcycle", "bus", "truck"}
SOURCE_CATEGORY_IDS = {"car": 1, "motorcycle": 2, "bus": 3, "truck": 4}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _annotation_inventory(
    root: Path,
) -> tuple[list[dict[str, str]], Counter[str], dict[str, list[float]]]:
    package = root / "annotations/lta_human_v1"
    manifest = package / "images.csv"
    labels = package / "annotations/annotations.jsonl"
    if _sha256(manifest) != MANIFEST_SHA256 or _sha256(labels) != LABEL_SHA256:
        raise ValueError("pinned LTA manifest or annotation fingerprint mismatch")
    with manifest.open(newline="", encoding="utf-8") as stream:
        images = list(csv.DictReader(stream))
    if len(images) != 63 or len({row["image_path"] for row in images}) != 63:
        raise ValueError("expected 63 distinct annotated images")
    by_path = {row["image_path"]: row for row in images}
    if len({row["camera_id"] for row in images}) != 8:
        raise ValueError("expected eight declared camera units")
    for row in images:
        if (
            row["split"] != "val"
            or row["period"] not in {"day", "night"}
            or Path(row["image_path"]).parts[:2] != ("week2", row["camera_id"])
            or int(row["width"]) <= 0
            or int(row["height"]) <= 0
        ):
            raise ValueError("invalid image split, camera, period or dimensions")
    counts: Counter[str] = Counter()
    input_heights: dict[str, list[float]] = {}
    seen: set[str] = set()
    with labels.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            path = item["image_path"]
            if path in seen or path not in by_path:
                raise ValueError("duplicate or unknown annotation image")
            seen.add(path)
            row = by_path[path]
            if (
                item["camera_id"] != row["camera_id"]
                or item["period"] != row["period"]
                or item["captured_at_utc"] != row["captured_at_utc"]
                or item["sha256"] != row["sha256"]
                or item["width"] != int(row["width"])
                or item["height"] != int(row["height"])
                or len(item["boxes"]) != int(row["n_boxes"])
            ):
                raise ValueError("annotation and image manifest disagree")
            width, height = item["width"], item["height"]
            scale = min(INPUT_SIZE / width, INPUT_SIZE / height)
            for box in item["boxes"]:
                x, y, w, h = box["bbox_xywh"]
                if (
                    box["category"] not in SOURCE_CLASSES
                    or box["category_id"] != SOURCE_CATEGORY_IDS[box["category"]]
                    or not all(math.isfinite(v) for v in (x, y, w, h))
                    or x < 0
                    or y < 0
                    or w <= 0
                    or h <= 0
                    or x + w > width + 1e-6
                    or y + h > height + 1e-6
                ):
                    raise ValueError("invalid annotation class or box")
                counts[box["category"]] += 1
                input_heights.setdefault(item["camera_id"], []).append(h * scale)
    if seen != set(by_path) or sum(counts.values()) != 1197:
        raise ValueError("missing annotation image or unexpected box count")
    return images, counts, input_heights


def preflight(root: Path, model_path: Path) -> dict:
    if _sha256(model_path) != MODEL_SHA256:
        raise ValueError("YOLOX nano model fingerprint mismatch")
    images, reference_classes, input_heights = _annotation_inventory(root)

    from PIL import Image

    detector = YoloxDetector(str(model_path), input_size=INPUT_SIZE, class_filter=ROAD_CLASSES)
    by_camera: dict[str, Counter[str]] = {}
    statuses: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for row in images:
        relative = Path(row["image_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe image path in manifest")
        path = root / relative
        if _sha256(path) != row["sha256"]:
            raise ValueError("image fingerprint mismatch")
        with Image.open(path) as image:
            rgb = np.asarray(image.convert("RGB"))
        if (rgb.shape[1], rgb.shape[0]) != (int(row["width"]), int(row["height"])):
            raise ValueError("image dimensions disagree with manifest")
        bgr = rgb[:, :, ::-1].copy()
        detections, capture = detector.detect_with_proposals(bgr, max_proposals=FULL_FRAME_CAP)
        ordinary = detector.detect(bgr)

        def values(ds):
            return [(d.class_id, d.score, tuple(d.xyxy)) for d in ds]

        if values(detections) != values(ordinary):
            raise ValueError("proposal capture changed ordinary detections")
        audit = audit_capture(capture)
        if capture.truncated or audit.frame_status != "complete":
            raise ValueError("full-frame proposal capture was incomplete")
        camera = by_camera.setdefault(row["camera_id"], Counter())
        camera["images"] += 1
        camera["reference_boxes"] += int(row["n_boxes"])
        camera["returned_detections"] += len(detections)
        camera["supported_detections"] += sum(r.status == "supported" for r in audit.rows)
        camera["night_images"] += row["period"] == "night"
        camera["confidence_filtered_proposals"] += capture.confidence_filtered_count
        camera["nms_suppressed_proposals"] += capture.nms_suppressed_count
        camera["class_filtered_proposals"] += capture.class_filtered_count
        totals["proposals"] += capture.total_proposals
        statuses.update(r.status for r in audit.rows)
    return {
        "schema": "visiontrack.lta-localization-preflight/v1",
        "scope": (
            "real-image detector/proposal feasibility; no reference matching or accuracy claim"
        ),
        "source_revision": SOURCE_REVISION,
        "source_url": "https://huggingface.co/datasets/LOVEIII486/isy5002-lta-traffic-images",
        "manifest_sha256": MANIFEST_SHA256,
        "annotations_sha256": LABEL_SHA256,
        "model_sha256": MODEL_SHA256,
        "model_input_size": INPUT_SIZE,
        "detector_confidence_threshold": detector.conf_threshold,
        "detector_nms_iou_threshold": detector.iou_threshold,
        "images_verified": len(images),
        "camera_units": len(by_camera),
        "reference_class_counts": dict(sorted(reference_classes.items())),
        "reference_box_input_height_by_camera": {
            camera: {
                "median_pixels": median(heights),
                "under_10_pixels": sum(height < 10 for height in heights),
                "boxes": len(heights),
            }
            for camera, heights in sorted(input_heights.items())
        },
        "by_camera": {key: dict(value) for key, value in sorted(by_camera.items())},
        "total_proposals": totals["proposals"],
        "spread_status_counts": dict(sorted(statuses.items())),
        "ordinary_detection_parity": True,
        "reference_matching_ran": False,
        "independent_truth_verified": False,
        "accuracy_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = preflight(args.root, args.model)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
