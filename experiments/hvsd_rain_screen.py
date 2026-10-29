"""Reproduce a metadata-only, development-only HVSD rain pipeline smoke run.

No reference IDs are supplied by the source. Counts here are pipeline outputs,
not accuracy, recall, continuity, traffic flow, or a frozen comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from visiontrack.detection.yolox_onnx import YoloxDetector
from visiontrack.tracking.tracker import ByteTracker

from .hvsd_video_intake import sha256_file

VIDEO_SHA256 = "efd4ea6e3548b9894caefc59df1d9914c1861f88fc93e7fb9114cb44acb78a9b"
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
ROAD_CLASSES = {2, 3, 5, 7}  # COCO car, motorcycle, bus, truck


def run(video_path: Path, model_path: Path) -> dict:
    if sha256_file(video_path) != VIDEO_SHA256:
        raise ValueError("rain clip fingerprint mismatch")
    if sha256_file(model_path) != MODEL_SHA256:
        raise ValueError("YOLOX nano fingerprint mismatch")

    try:
        import imageio.v2 as imageio
    except ImportError as exc:
        raise ImportError("install the visiontrack [video] extra") from exc

    detector = YoloxDetector(str(model_path), class_filter=ROAD_CLASSES)
    tracker = ByteTracker()
    reader = imageio.get_reader(str(video_path))
    rows = []
    try:
        for index, frame in enumerate(reader):
            detections = detector.detect(frame)
            observations = tracker.update(detections)
            rows.append({
                "frame": index,
                "detections": len(detections),
                "public_tracks": len(observations),
                "public_ids": [item.track_id for item in observations],
            })
    finally:
        reader.close()

    if len(rows) != 194:
        raise ValueError(f"expected 194 decoded frames, got {len(rows)}")
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {
        "source": "HVSD V1 / Dataset/rain.mp4",
        "video_sha256": VIDEO_SHA256,
        "model_sha256": MODEL_SHA256,
        "settings": "YOLOX nano 416, score >= 0.25, road classes 2/3/5/7; ByteTracker defaults",
        "decoded_frames": len(rows),
        "detector_boxes": sum(row["detections"] for row in rows),
        "frames_without_detections": sum(row["detections"] == 0 for row in rows),
        "public_track_boxes": sum(row["public_tracks"] for row in rows),
        "unique_public_track_ids": len({identifier for row in rows
                                        for identifier in row["public_ids"]}),
        "max_simultaneous_public_tracks": max(row["public_tracks"] for row in rows),
        "per_frame_output_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_labels_present": False,
        "accuracy_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.video, args.model), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
