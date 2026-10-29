"""Paired, development-only replay of one rain-clip new-track threshold change.

The 0.55 candidate was chosen after inspecting the owner's frame-57 mark. This
is a post-hoc mechanism check, not a held-out comparison or accuracy estimate.
Both trackers consume the exact same pinned detector output on each frame.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from visiontrack.detection.yolox_onnx import YoloxDetector
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

from .hvsd_rain_gate_trace import EXPECTED_RECEIPT, MARKS
from .hvsd_rain_review import line_crossings
from .hvsd_rain_screen import MODEL_SHA256, ROAD_CLASSES, VIDEO_SHA256
from .hvsd_video_intake import sha256_file

FRAME_COUNT = 194
CANDIDATE_NEW_TRACK_THRESHOLD = 0.55


def _summarize(rows: list[dict], centers: list[tuple[int, int, float, float]]) -> dict:
    crossings = line_crossings(centers)
    return {
        "public_track_boxes": sum(row["public_tracks"] for row in rows),
        "unique_public_track_ids": len({track_id for row in rows
                                        for track_id in row["public_ids"]}),
        "tentative_births": sum(row["tentative_births"] for row in rows),
        "public_crossings": crossings,
        "crossings_near_owner_marks": {
            str(mark): [event for event in crossings
                        if abs(event["estimated_frame"] - mark) <= 4]
            for mark in MARKS
        },
    }


def replay(detection_frames: list[list], *, expected_receipt: str | None = None) -> dict:
    """Compare one changed configuration after checking the frozen baseline.

    ``expected_receipt`` is required for the real-video command. Tests may omit
    it for a small synthetic stream; that does not validate the real source.
    """
    trackers = {
        "baseline": ByteTracker(),
        "new_track_0_55": ByteTracker(TrackerConfig(
            new_track_thresh=CANDIDATE_NEW_TRACK_THRESHOLD)),
    }
    rows: dict[str, list[dict]] = {name: [] for name in trackers}
    centers: dict[str, list[tuple[int, int, float, float]]] = {
        name: [] for name in trackers
    }
    for frame, detections in enumerate(detection_frames):
        for name, tracker in trackers.items():
            next_id = tracker._next_id
            tracks = tracker.update(detections)
            rows[name].append({
                "frame": frame,
                "detections": len(detections),
                "public_tracks": len(tracks),
                "public_ids": [track.track_id for track in tracks],
                "tentative_births": tracker._next_id - next_id,
            })
            for track in tracks:
                box = track.xyxy
                centers[name].append((
                    frame, track.track_id,
                    float((box[0] + box[2]) / 2),
                    float((box[1] + box[3]) / 2),
                ))
    baseline_receipt = hashlib.sha256(json.dumps(
        [{key: value for key, value in row.items() if key != "tentative_births"}
         for row in rows["baseline"]],
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    if expected_receipt is not None and (
        len(detection_frames) != FRAME_COUNT or baseline_receipt != expected_receipt
    ):
        raise ValueError("baseline differs from frozen 194-frame pipeline receipt")

    baseline = _summarize(rows["baseline"], centers["baseline"])
    candidate = _summarize(rows["new_track_0_55"], centers["new_track_0_55"])
    return {
        "schema": "visiontrack.hvsd-rain-threshold-replay/v1",
        "source_video_sha256": VIDEO_SHA256,
        "model_sha256": MODEL_SHA256,
        "frame_count": len(detection_frames),
        "baseline_receipt": baseline_receipt,
        "candidate_changed_setting_only": {"new_track_thresh":
                                           CANDIDATE_NEW_TRACK_THRESHOLD},
        "baseline": baseline,
        "candidate": candidate,
        "delta_public_track_boxes": (candidate["public_track_boxes"]
                                     - baseline["public_track_boxes"]),
        "delta_tentative_births": (candidate["tentative_births"]
                                   - baseline["tentative_births"]),
        "owner_marks_are_dense_truth": False,
        "post_hoc_development_only": True,
        "accuracy_claim": False,
        "recommend_default_change": False,
    }


def run(video: Path, model: Path) -> dict:
    if sha256_file(video) != VIDEO_SHA256 or sha256_file(model) != MODEL_SHA256:
        raise ValueError("video or model fingerprint mismatch")
    try:
        import imageio.v2 as imageio
    except ImportError as exc:
        raise ImportError("install the visiontrack [video] extra") from exc

    detector = YoloxDetector(str(model), class_filter=ROAD_CLASSES)
    reader = imageio.get_reader(str(video))
    try:
        detection_frames = [detector.detect(image) for image in reader]
    finally:
        reader.close()
    return replay(detection_frames, expected_receipt=EXPECTED_RECEIPT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.video, args.model)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
