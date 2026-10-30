"""Run one pinned detector on a preselected SVMOT training occlusion window.

This is a development-only detector coverage diagnostic. It does not run a
tracker, use the publisher's GT-mirroring detections, or score a benchmark.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from visiontrack.detection.yolox_onnx import YoloxDetector

MODEL_SPECS = {
    "nano": (
        "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d",
        416,
    ),
    "x": (
        "c892d7aaf1c4746d8a4d675bec669a4db4f434b4ee1efb654bc9b353379c7c55",
        640,
    ),
}
COCO_CAR = 2
SVMOT_CAR = 1
IOU_SCREEN = 0.5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def preflight(root: Path, train_file: Path, test_file: Path, selection_file: Path,
              model_path: Path, detector_factory=YoloxDetector,
              model_key: str = "nano") -> dict:
    if model_key not in MODEL_SPECS:
        raise ValueError("unknown pinned detector model")
    expected_hash, input_size = MODEL_SPECS[model_key]
    train = set(train_file.read_text(encoding="utf-8").split())
    test = set(test_file.read_text(encoding="utf-8").split())
    selection = json.loads(selection_file.read_text(encoding="utf-8"))
    if (not train or train & test or
            selection.get("schema") != "visiontrack.svmot-occlusion-review-selection/v1" or
            selection.get("test_labels_opened") is not False):
        raise ValueError("invalid training split or selection receipt")
    event = selection["selected_event"]
    sequence = event["sequence"]
    if (Path(sequence).name != sequence or sequence in {".", ".."} or
            sequence not in train or sequence in test):
        raise ValueError("selected sequence must be official train only")
    start = event["review_start_frame"]
    end = event["review_end_frame"]
    onset = event["onset_frame"]
    clear = event["first_clear_frame"]
    target_id = event["object_id"]
    if not (isinstance(start, int) and isinstance(end, int) and
            isinstance(onset, int) and isinstance(clear, int) and
            isinstance(target_id, int) and 1 <= start < onset < clear <= end and
            end - start <= 60):
        raise ValueError("invalid bounded review frame range")
    folder = root / "data" / sequence
    if _sha256(folder / "occlusion.json") != event["occlusion_sha256"]:
        raise ValueError("occlusion source differs from selection receipt")
    model_hash = _sha256(model_path)
    if model_hash != expected_hash:
        raise ValueError("detector model fingerprint mismatch")

    gt_path = folder / "gt" / "gt.txt"
    target = {}
    with gt_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.reader(stream):
            if int(row[1]) != target_id or not start <= int(row[0]) <= end:
                continue
            frame = int(row[0])
            if frame in target or int(row[7]) != SVMOT_CAR:
                raise ValueError("target ID has duplicate rows or is not a car")
            x, y, width, height = map(float, row[2:6])
            target[frame] = ((x, y, x + width, y + height), float(row[8]))
    if set(target) != set(range(start, end + 1)):
        raise ValueError("selected target is not labeled on every review frame")

    from PIL import Image

    detector = detector_factory(str(model_path), input_size=input_size,
                                class_filter={COCO_CAR})
    rows = []
    for frame in range(start, end + 1):
        image_path = folder / "img" / f"{frame:04d}.jpg"
        image = np.asarray(Image.open(image_path).convert("RGB"))
        detections = detector.detect(image)
        if any(item.class_id != COCO_CAR for item in detections):
            raise ValueError("detector returned a class outside the pinned filter")
        gt_box, visibility = target[frame]
        best_iou = max((float(_iou(gt_box, tuple(item.xyxy))) for item in detections),
                       default=0.0)
        phase = "before" if frame < onset else "occluded" if frame < clear else "after"
        rows.append({
            "frame": frame,
            "phase": phase,
            "reference_visibility": visibility,
            "image_sha256": _sha256(image_path),
            "car_detections": len(detections),
            "best_car_box_iou": round(best_iou, 6),
            "box_overlap_at_0_5": best_iou >= IOU_SCREEN,
        })
    phases = {
        phase: {
            "frames": sum(row["phase"] == phase for row in rows),
            "frames_with_car_box_overlap_at_0_5": sum(
                row["phase"] == phase and row["box_overlap_at_0_5"] for row in rows),
            "frames_with_any_car_detection": sum(
                row["phase"] == phase and row["car_detections"] > 0 for row in rows),
        }
        for phase in ("before", "occluded", "after")
    }
    return {
        "schema": "visiontrack.svmot-detector-preflight/v1",
        "scope": "one preselected official-train occlusion; detector-only diagnostic",
        "sequence": sequence,
        "target_id": target_id,
        "selection_sha256": _sha256(selection_file),
        "gt_sha256": _sha256(gt_path),
        "model_sha256": model_hash,
        "detector": (f"YOLOX {model_key} ONNX; {input_size} px; score >= 0.25; "
                     "NMS IoU 0.45; COCO car only"),
        "box_overlap_screen_iou": IOU_SCREEN,
        "phases": phases,
        "frames": rows,
        "tracker_ran": False,
        "publisher_detections_used": False,
        "test_scenes_opened": False,
        "accuracy_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--train-file", required=True, type=Path)
    parser.add_argument("--test-file", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-key", choices=sorted(MODEL_SPECS), default="nano")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = preflight(args.root, args.train_file, args.test_file,
                       args.selection, args.model, model_key=args.model_key)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
