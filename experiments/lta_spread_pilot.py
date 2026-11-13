"""Exploratory cross-camera spread check on already-inspected LTA labels.

This is development-only. The labels were corrected from model pre-labels by
one annotator, and this subset was used in previous model screens. No fold is an
independent held-out test and the result cannot establish an accuracy gain.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from experiments.localization_outcome import (
    DetectionRow,
    Frame,
    MatchedRow,
    ReferenceRow,
    _area,
    _frame_rows,
    _predict,
)
from experiments.localization_signal import audit_capture
from experiments.lta_detector_agreement import CLASS_ID, MODELS
from experiments.lta_localization_preflight import (
    LABEL_SHA256,
    MANIFEST_SHA256,
    ROAD_CLASSES,
    _annotation_inventory,
    _sha256,
)
from visiontrack.detection.yolox_onnx import YoloxDetector

CLASS_NAME = {value: key for key, value in CLASS_ID.items()}


def cross_camera(rows_by_camera: dict[str, list[MatchedRow]]) -> dict:
    """Refit B2 and B3 for each omitted camera on identical supported rows."""
    cameras = sorted(rows_by_camera)
    folds: dict[str, dict] = {}
    weighted_delta = 0.0
    contributing = 0
    for camera in cameras:
        train = [row for other in cameras if other != camera
                 for row in rows_by_camera[other] if row.spread is not None]
        classes = {row.class_id for row in train}
        test = [row for row in rows_by_camera[camera]
                if row.spread is not None and row.class_id in classes]
        excluded = sum(row.spread is not None and row.class_id not in classes
                       for row in rows_by_camera[camera])
        fold = {
            "matched": len(rows_by_camera[camera]),
            "supported_matched": sum(row.spread is not None
                                     for row in rows_by_camera[camera]),
            "train_supported_matched": len(train),
            "paired_test_matched": len(test),
            "excluded_unseen_class": excluded,
            "ambiguous_paired_matches": sum(row.match_ambiguous for row in test),
        }
        if not train or not test:
            fold["status"] = "no paired comparison"
        else:
            b2 = _predict(train, test, 2)
            b3 = _predict(train, test, 3)
            area2, _ = _area(test, b2)
            area3, _ = _area(test, b3)
            fold.update({"status": "descriptive development fold",
                         "B2_area": area2, "B3_area": area3,
                         "B3_minus_B2": area3 - area2})
            weighted_delta += (area3 - area2) * len(test)
            contributing += len(test)
        folds[camera] = fold
    comparable = [fold["B3_minus_B2"] for fold in folds.values()
                  if "B3_minus_B2" in fold]
    return {
        "camera_folds": folds,
        "cameras_total": len(cameras),
        "cameras_with_paired_matches": len(comparable),
        "paired_matches_total": contributing,
        "camera_mean_delta": (sum(comparable) / len(comparable)
                              if comparable else None),
        "match_weighted_camera_delta": (weighted_delta / contributing
                                        if contributing else None),
        "cameras_B3_better": sum(delta < 0 for delta in comparable),
        "cameras_B3_worse": sum(delta > 0 for delta in comparable),
        "cameras_tied": sum(delta == 0 for delta in comparable),
    }


def pilot(root: Path, model_path: Path) -> dict:
    """Verify the pinned source and run one fixed X/640 detector configuration."""
    expected_model, input_size = MODELS["x_640"]
    if _sha256(model_path) != expected_model:
        raise ValueError("X/640 model fingerprint mismatch")
    images, _, _ = _annotation_inventory(root)
    labels_path = root / "annotations/lta_human_v1/annotations/annotations.jsonl"
    with labels_path.open(encoding="utf-8") as stream:
        labels = {row["image_path"]: row["boxes"] for row in map(json.loads, stream)}
    if len(labels) != len(images):
        raise ValueError("annotation image inventory changed")
    detector = YoloxDetector(str(model_path), input_size=input_size,
                             class_filter=ROAD_CLASSES)
    cap = sum((input_size // stride) ** 2 for stride in (8, 16, 32))
    rows_by_camera: dict[str, list[MatchedRow]] = {}
    inventory_by_camera: dict[str, Counter[str]] = {}
    for source in images:
        relative = Path(source["image_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe image path in pinned source manifest")
        path = root / relative
        if _sha256(path) != source["sha256"]:
            raise ValueError("pinned image fingerprint mismatch")
        with Image.open(path) as image:
            rgb = np.asarray(image.convert("RGB"))
        if (rgb.shape[1], rgb.shape[0]) != (int(source["width"]), int(source["height"])):
            raise ValueError("pinned image dimensions changed")
        bgr = rgb[:, :, ::-1].copy()
        detections, capture = detector.detect_with_proposals(bgr, max_proposals=cap)
        if capture.truncated:
            raise ValueError("proposal capture unexpectedly truncated")
        audit = audit_capture(capture)
        if audit.frame_status != "complete" or len(audit.rows) != len(detections):
            raise ValueError("proposal audit disagrees with returned boxes")
        ordinary = detector.detect(bgr)
        def signature(values):
            return [(d.class_id, d.score, tuple(d.xyxy)) for d in values]
        if signature(detections) != signature(ordinary):
            raise ValueError("proposal capture changed ordinary detections")
        frame = Frame(
            "development", source["camera_id"], source["image_path"],
            tuple(DetectionRow(
                CLASS_NAME[d.class_id], tuple(float(x) for x in d.xyxy), d.score,
                spread.status, spread.spread, spread.group_size,
            ) for d, spread in zip(detections, audit.rows, strict=True)),
            tuple(ReferenceRow(
                box["category"],
                (box["bbox_xywh"][0], box["bbox_xywh"][1],
                 box["bbox_xywh"][0] + box["bbox_xywh"][2],
                 box["bbox_xywh"][1] + box["bbox_xywh"][3]),
                True, "unknown",
            ) for box in labels[source["image_path"]]),
        )
        matched, counts = _frame_rows(frame)
        rows_by_camera.setdefault(frame.scene, []).extend(matched)
        inventory_by_camera.setdefault(frame.scene, Counter()).update(counts)
        inventory_by_camera[frame.scene]["images"] += 1
    if _sha256(model_path) != expected_model:
        raise ValueError("model changed during pilot")
    if _sha256(labels_path) != LABEL_SHA256:
        raise ValueError("annotations changed during pilot")
    result = cross_camera(rows_by_camera)
    result.update({
        "schema": "visiontrack.lta-spread-pilot/v1",
        "scope": "already-inspected, development-only, leave-one-camera-out diagnostic",
        "source_manifest_sha256": MANIFEST_SHA256,
        "source_annotations_sha256": LABEL_SHA256,
        "model_sha256": expected_model,
        "input_size": input_size,
        "matching": "same-class one-to-one maximum IoU at 0.5",
        "metric": "mean normalized bottom-anchor error versus retained coverage; lower is better",
        "by_camera_inventory": {camera: dict(counts) for camera, counts
                                in sorted(inventory_by_camera.items())},
        "ordinary_detection_parity": True,
        "independent_truth_verified": False,
        "held_out_evaluation": False,
        "accuracy_claim": False,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="new aggregate-only report outside Git")
    args = parser.parse_args()
    result = pilot(args.root, args.model)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    print(json.dumps({"output": str(args.output),
                      "cameras_with_paired_matches": result["cameras_with_paired_matches"],
                      "paired_matches_total": result["paired_matches_total"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
