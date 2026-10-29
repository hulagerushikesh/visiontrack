"""Audit owner rain crossing marks against an unchanged pipeline output.

This is an exploratory development check. Event marks are not dense box/ID
truth, and absence of a mark is not automatically a negative label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from visiontrack.detection.yolox_onnx import YoloxDetector
from visiontrack.tracking.tracker import ByteTracker

from .hvsd_rain_screen import (
    MODEL_SHA256,
    ROAD_CLASSES,
    VIDEO_SHA256,
)
from .hvsd_video_intake import sha256_file

SCHEMA = "visiontrack.hvsd-rain-event-review/v1"
LINE = {"x": 500, "y_min": 205, "y_max": 432,
        "direction": "left-to-right", "region": "near road"}
SOURCE = {"dataset": "HVSD V1", "clip": "Dataset/rain.mp4",
          "video_sha256": VIDEO_SHA256, "frame_count": 194, "line": LINE}
VEHICLES = {"car", "van", "truck", "motorcycle", "other/unknown"}


def audit_reviews(paths: list[Path]) -> dict:
    """Validate separate browser downloads and merge exact duplicates only."""
    if not paths:
        raise ValueError("at least one review JSON is required")
    source_files = []
    unique: dict[tuple[int, str, str], dict] = {}
    by_frame: dict[int, tuple[str, str]] = {}
    duplicate_frames = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA or data.get("source") != SOURCE:
            raise ValueError(f"wrong review schema or source: {path}")
        if (data.get("review_role") != "owner_independent_scene_pass"
                or data.get("dense_identity_truth") is not False
                or data.get("tracker_output_seen_in_page") is not False):
            raise ValueError(f"wrong review role or disclosure: {path}")
        events = data.get("events")
        if not isinstance(events, list):
            raise ValueError(f"events must be a list: {path}")
        source_files.append({"file": path.name, "sha256": sha256_file(path),
                             "record_count": len(events)})
        for event in events:
            if not isinstance(event, dict) or set(event) != {"frame", "vehicle", "certainty"}:
                raise ValueError(f"invalid event fields: {path}")
            frame, vehicle, certainty = event["frame"], event["vehicle"], event["certainty"]
            if (type(frame) is not int or not 0 <= frame < 194
                    or vehicle not in VEHICLES or certainty not in {"clear", "uncertain"}):
                raise ValueError(f"invalid event value: {path}")
            prior = by_frame.get(frame)
            if prior is not None and prior != (vehicle, certainty):
                raise ValueError(f"conflicting marks at frame {frame}")
            by_frame[frame] = (vehicle, certainty)
            key = frame, vehicle, certainty
            if key in unique:
                duplicate_frames.append(frame)
            else:
                unique[key] = dict(event)
    marks = sorted(unique.values(), key=lambda event: (event["frame"], event["vehicle"]))
    return {"schema": "visiontrack.hvsd-rain-review-audit/v1",
            "source": SOURCE, "source_files": source_files,
            "submitted_record_count": sum(item["record_count"] for item in source_files),
            "exact_duplicate_frames": sorted(duplicate_frames),
            "unique_events": marks,
            "unique_clear_events": sum(event["certainty"] == "clear" for event in marks),
            "unique_uncertain_events": sum(event["certainty"] == "uncertain" for event in marks),
            "complete_negative_frame_review_verified": False,
            "dense_identity_truth": False}


def line_crossings(observations: list[tuple[int, int, float, float]]) -> list[dict]:
    """Emit each adjacent-frame, same-public-ID center crossing of the line."""
    previous: dict[int, tuple[int, float, float]] = {}
    events = []
    for frame, track_id, x, y in observations:
        if not all(math.isfinite(value) for value in (x, y)):
            raise ValueError("nonfinite tracker center")
        prior = previous.get(track_id)
        if prior is not None:
            prior_frame, prior_x, prior_y = prior
            if frame == prior_frame + 1 and prior_x < LINE["x"] <= x:
                fraction = (LINE["x"] - prior_x) / (x - prior_x)
                crossing_y = prior_y + fraction * (y - prior_y)
                if LINE["y_min"] <= crossing_y <= LINE["y_max"]:
                    events.append({"track_id": track_id,
                                   "between_frames": [prior_frame, frame],
                                   "estimated_frame": prior_frame + fraction,
                                   "crossing_y": crossing_y})
        previous[track_id] = frame, x, y
    return sorted(events, key=lambda event: (event["estimated_frame"], event["track_id"]))


def pipeline_crossings(video: Path, model: Path, mark_frames: list[int]) -> dict:
    """Re-run frozen detector/tracker; verify aggregate receipt before geometry."""
    if sha256_file(video) != VIDEO_SHA256 or sha256_file(model) != MODEL_SHA256:
        raise ValueError("video or model fingerprint mismatch")
    try:
        import imageio.v2 as imageio
    except ImportError as exc:
        raise ImportError("install the visiontrack [video] extra") from exc
    detector = YoloxDetector(str(model), class_filter=ROAD_CLASSES)
    tracker = ByteTracker()
    observations = []
    rows = []
    diagnostic_frames = {
        frame for mark in mark_frames for frame in range(max(0, mark - 4), min(194, mark + 5))
    }
    diagnostics = []
    reader = imageio.get_reader(str(video))
    try:
        for frame, image in enumerate(reader):
            detections = detector.detect(image)
            tracks = tracker.update(detections)
            rows.append({"frame": frame, "detections": len(detections),
                         "public_tracks": len(tracks),
                         "public_ids": [track.track_id for track in tracks]})
            for track in tracks:
                box = track.xyxy
                observations.append((frame, track.track_id,
                                     float((box[0] + box[2]) / 2),
                                     float((box[1] + box[3]) / 2)))
            if frame in diagnostic_frames:
                def nearby(box) -> bool:
                    center_x = float((box[0] + box[2]) / 2)
                    center_y = float((box[1] + box[3]) / 2)
                    return abs(center_x - LINE["x"]) < 125 and center_y >= LINE["y_min"]

                diagnostics.append({
                    "frame": frame,
                    "near_line_detections": [
                        {"center_x": round(float((det.xyxy[0] + det.xyxy[2]) / 2), 1),
                         "center_y": round(float((det.xyxy[1] + det.xyxy[3]) / 2), 1),
                         "score": round(det.score, 3), "class_id": det.class_id}
                        for det in detections if nearby(det.xyxy)
                    ],
                    "near_line_public_tracks": [
                        {"track_id": track.track_id,
                         "center_x": round(float((track.xyxy[0] + track.xyxy[2]) / 2), 1)}
                        for track in tracks if nearby(track.xyxy)
                    ],
                    "near_line_internal_tracks": [
                        {"track_id": track.track_id, "state": track.state.name,
                         "hits": track.hits, "time_since_update": track.time_since_update,
                         "center_x": round(float((track.to_xyxy()[0]
                                                  + track.to_xyxy()[2]) / 2), 1)}
                        for track in tracker.tracks if nearby(track.to_xyxy())
                    ],
                })
    finally:
        reader.close()
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    receipt = hashlib.sha256(raw).hexdigest()
    expected = "0125e1e9644e0df9fb36d3c1353c8e328dd7fc1e03d8117299af0e0afe4f49c6"
    if len(rows) != 194 or receipt != expected:
        raise ValueError("tracker output differs from frozen smoke receipt")
    return {"pipeline_receipt": receipt, "public_track_box_count": len(observations),
            "crossing_rule": (
                "adjacent frames, same public ID, box center x < 500 then >= 500; "
                "interpolated y 205..432"
            ),
            "crossings": line_crossings(observations),
            "diagnostic_window_rule": (
                "marked frame +/- 4; centers within 125 px of line and y >= 205"
            ),
            "diagnostic_frames": diagnostics,
            "track_ids": dict(sorted(Counter(
                identifier for _, identifier, _, _ in observations
            ).items()))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviews", nargs="+", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--owner-attested-full-frame-pass", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.video is None) != (args.model is None):
        parser.error("--video and --model must be supplied together")
    report = audit_reviews(args.reviews)
    report["owner_attested_all_194_frames_reviewed"] = args.owner_attested_full_frame_pass
    if args.video is not None:
        report["exploratory_pipeline"] = pipeline_crossings(
            args.video, args.model,
            [event["frame"] for event in report["unique_events"]],
        )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
