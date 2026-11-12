"""Development-only LTA detector/box-overlap screen; never an accuracy score.

The 63 teacher-assisted validation images have already been inspected. This
fixed development screen asks whether enough returned boxes overlap the supplied
boxes to justify seeking *independent* localization labels. It does not select
a detector for a confirmatory study or tune thresholds on these frames.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from experiments.localization_outcome import _iou
from experiments.localization_signal import audit_capture
from experiments.lta_localization_preflight import (
    LABEL_SHA256,
    MANIFEST_SHA256,
    ROAD_CLASSES,
    _annotation_inventory,
    _sha256,
)
from visiontrack.detection.yolox_onnx import YoloxDetector

MODELS = {
    "nano_416": ("c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d", 416),
    "x_640": ("c892d7aaf1c4746d8a4d675bec669a4db4f434b4ee1efb654bc9b353379c7c55", 640),
}
FACTORIAL_MODELS = {
    "nano_416": MODELS["nano_416"],
    "nano_640": (MODELS["nano_416"][0], 640),
    "x_416": (MODELS["x_640"][0], 416),
    "x_640": MODELS["x_640"],
}
CLASS_ID = {"car": 2, "motorcycle": 3, "bus": 5, "truck": 7}
IOU_GATE = 0.5


def _size_bin(height: float) -> str:
    if height < 10:
        return "under_10px"
    if height < 20:
        return "10_to_under_20px"
    return "20px_or_more"


def _frame_agreement(
    boxes: list[dict], detections: list, supported_indices: set[int], scale: float,
) -> dict[str, Counter[str]]:
    """Any same-class overlap; deliberately *not* unique assignment or recall."""
    output: dict[str, Counter[str]] = defaultdict(Counter)
    for box in boxes:
        x, y, w, h = box["bbox_xywh"]
        label = box["category"]
        source = (x, y, x + w, y + h)
        bin_name = _size_bin(h * scale)
        matching = [
            i for i, det in enumerate(detections)
            if det.class_id == CLASS_ID[label] and _iou(source, tuple(det.xyxy)) >= IOU_GATE
        ]
        for group in ("all", f"class:{label}", f"height:{bin_name}"):
            output[group]["supplied_boxes"] += 1
            output[group]["boxes_with_overlap"] += bool(matching)
            output[group]["boxes_with_supported_overlap"] += bool(
                supported_indices.intersection(matching)
            )
    output["all"]["returned_detections"] += len(detections)
    output["all"]["supported_detections"] += len(supported_indices)
    output["all"]["images"] += 1
    output["all"]["images_without_detections"] += not bool(detections)
    output["all"]["images_without_supported_overlap"] += not bool(
        output["all"]["boxes_with_supported_overlap"]
    )
    return output


def screen(root: Path, model_paths: dict[str, Path], *, factorial: bool = False) -> dict:
    images, _, _ = _annotation_inventory(root)  # also validates pinned annotation bytes.
    labels_path = root / "annotations/lta_human_v1/annotations/annotations.jsonl"
    with labels_path.open(encoding="utf-8") as stream:
        labels = {row["image_path"]: row["boxes"] for row in map(json.loads, stream)}
    if len(labels) != len(images):
        raise ValueError("annotation image inventory changed")
    from PIL import Image

    configurations = FACTORIAL_MODELS if factorial else MODELS
    results = {}
    for key, (expected_digest, input_size) in configurations.items():
        path = model_paths["nano" if key.startswith("nano") else "x"]
        if _sha256(path) != expected_digest:
            raise ValueError(f"{key} model fingerprint mismatch")
        detector = YoloxDetector(str(path), input_size=input_size, class_filter=ROAD_CLASSES)
        cap = sum((input_size // stride) ** 2 for stride in (8, 16, 32))
        totals: dict[str, Counter[str]] = defaultdict(Counter)
        cameras: dict[str, Counter[str]] = defaultdict(Counter)
        for row in images:
            relative = Path(row["image_path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe image path in pinned source manifest")
            image_path = root / relative
            if _sha256(image_path) != row["sha256"]:
                raise ValueError("pinned image fingerprint mismatch")
            with Image.open(image_path) as image:
                rgb = np.asarray(image.convert("RGB"))
            if (rgb.shape[1], rgb.shape[0]) != (int(row["width"]), int(row["height"])):
                raise ValueError("pinned image dimensions changed")
            bgr = rgb[:, :, ::-1].copy()
            detections, capture = detector.detect_with_proposals(bgr, max_proposals=cap)
            if capture.truncated:
                raise ValueError("proposal capture unexpectedly truncated")
            audit = audit_capture(capture)
            if audit.frame_status != "complete" or len(audit.rows) != len(detections):
                raise ValueError("proposal audit disagrees with returned boxes")
            supported = {i for i, item in enumerate(audit.rows) if item.status == "supported"}
            # The two paths intentionally infer separately: capture must not alter
            # ordinary production detections on the exact same input.
            ordinary = detector.detect(bgr)
            if [(d.class_id, d.score, tuple(d.xyxy)) for d in detections] != [
                (d.class_id, d.score, tuple(d.xyxy)) for d in ordinary
            ]:
                raise ValueError("proposal capture changed ordinary detections")
            scale = min(input_size / rgb.shape[1], input_size / rgb.shape[0])
            agreement = _frame_agreement(labels[row["image_path"]], detections, supported, scale)
            for group, counts in agreement.items():
                totals[group].update(counts)
            cameras[row["camera_id"]].update(agreement["all"])
        results[key] = {
            "model_sha256": expected_digest,
            "input_size": input_size,
            "confidence_threshold": detector.conf_threshold,
            "nms_iou_threshold": detector.iou_threshold,
            "by_group": {k: dict(v) for k, v in sorted(totals.items())},
            "by_camera": {k: dict(v) for k, v in sorted(cameras.items())},
            "ordinary_detection_parity": True,
        }
    return {
        "schema": f"visiontrack.lta-detector-agreement/v{2 if factorial else 1}",
        "scope": "development-only any-box overlap against supplied validation annotations",
        "iou_gate": IOU_GATE,
        "one_to_one_assignment": False,
        "independent_truth_verified": False,
        "accuracy_claim": False,
        "images": len(images),
        "source_manifest_sha256": MANIFEST_SHA256,
        "source_annotations_sha256": LABEL_SHA256,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--nano-model", required=True, type=Path)
    parser.add_argument("--x-model", required=True, type=Path)
    parser.add_argument("--factorial", action="store_true",
                        help="run both pinned models at 416 and 640 input sizes")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = screen(args.root, {"nano": args.nano_model, "x": args.x_model},
                    factorial=args.factorial)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
