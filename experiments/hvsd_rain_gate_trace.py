"""Trace tentative-track association gates on the pinned HVSD rain clip.

Exploratory diagnosis only. This observes private tracker calls without changing
their return values. It does not establish physical object correspondence,
ground-truth identity, or the benefit of a different gate configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from visiontrack.core.geometry import iou_matrix, xyxy_to_xyah
from visiontrack.detection.yolox_onnx import YoloxDetector
from visiontrack.tracking.tracker import ByteTracker

from .hvsd_rain_screen import MODEL_SHA256, ROAD_CLASSES, VIDEO_SHA256
from .hvsd_video_intake import sha256_file

MARKS = (27, 37, 57, 92, 160)
DIAGNOSTIC_FRAMES = {
    frame for mark in MARKS for frame in range(max(0, mark - 4), min(194, mark + 5))
}
EXPECTED_RECEIPT = "0125e1e9644e0df9fb36d3c1353c8e328dd7fc1e03d8117299af0e0afe4f49c6"


class GateProbe(ByteTracker):
    """Observe stage-three pairs; delegate every actual match to ByteTracker."""

    def __init__(self) -> None:
        super().__init__()
        self._stage = 0
        self.pairs: list[dict] = []

    def update(self, detections, camera_shift=None):
        self._stage = 0
        return super().update(detections, camera_shift=camera_shift)

    def _match(self, tracks, dets, iou_thresh, gate):
        self._stage += 1
        if self._stage != 3 or self.frame_index not in DIAGNOSTIC_FRAMES:
            return super()._match(tracks, dets, iou_thresh, gate)
        if not gate or any(not track.is_tentative for track in tracks):
            raise ValueError("tracker stage-three contract changed")
        if not tracks or not dets:
            return super()._match(tracks, dets, iou_thresh, gate)

        track_boxes = np.stack([track.to_xyxy() for track in tracks])
        track_hits = [track.hits for track in tracks]
        track_classes = [track.class_id for track in tracks]
        det_boxes = np.stack([det.xyxy for det in dets])
        ious = iou_matrix(track_boxes, det_boxes)
        d2s = self.kf.gating_distance_batch(
            np.stack([track.mean for track in tracks]),
            np.stack([track.covariance for track in tracks]),
            xyxy_to_xyah(det_boxes),
        )
        result = super()._match(tracks, dets, iou_thresh, gate)
        matches = {(int(ti), int(di)) for ti, di in result[0]}
        for ti, track in enumerate(tracks):
            for di, det in enumerate(dets):
                x = float((det.xyxy[0] + det.xyxy[2]) / 2)
                y = float((det.xyxy[1] + det.xyxy[3]) / 2)
                if abs(x - 500) >= 125 or y < 205:
                    continue
                iou = float(ious[ti, di])
                d2 = float(d2s[ti, di])
                track_class = track_classes[ti]
                class_ok = (not self.cfg.class_aware or track_class == det.class_id
                            or track_class == -1 or det.class_id == -1)
                self.pairs.append({
                    "frame": self.frame_index,
                    "tentative_track_id": track.track_id,
                    "track_hits_before_match": track_hits[ti],
                    "track_class_id": track_class,
                    "predicted_track_center_x": round(float(
                        (track_boxes[ti, 0] + track_boxes[ti, 2]) / 2), 1),
                    "detection_class_id": det.class_id,
                    "detection_score": round(float(det.score), 3),
                    "detection_center_x": round(x, 1),
                    "iou": round(iou, 4),
                    "mahalanobis_d2": round(d2, 3),
                    "class_gate_pass": class_ok,
                    "iou_gate_pass": iou >= iou_thresh,
                    "mahalanobis_gate_pass": not gate or d2 <= self._gate,
                    "matched": (ti, di) in matches,
                })
        return result


def run(video: Path, model: Path) -> dict:
    if sha256_file(video) != VIDEO_SHA256 or sha256_file(model) != MODEL_SHA256:
        raise ValueError("video or model fingerprint mismatch")
    try:
        import imageio.v2 as imageio
    except ImportError as exc:
        raise ImportError("install the visiontrack [video] extra") from exc

    detector = YoloxDetector(str(model), class_filter=ROAD_CLASSES)
    tracker = GateProbe()
    rows = []
    reader = imageio.get_reader(str(video))
    try:
        for frame, image in enumerate(reader):
            detections = detector.detect(image)
            tracks = tracker.update(detections)
            rows.append({"frame": frame, "detections": len(detections),
                         "public_tracks": len(tracks),
                         "public_ids": [track.track_id for track in tracks]})
    finally:
        reader.close()
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    receipt = hashlib.sha256(raw).hexdigest()
    if len(rows) != 194 or receipt != EXPECTED_RECEIPT:
        raise ValueError("tracker output differs from frozen smoke receipt")
    return {
        "schema": "visiontrack.hvsd-rain-gate-trace/v1",
        "source_video_sha256": VIDEO_SHA256,
        "model_sha256": MODEL_SHA256,
        "pipeline_receipt": receipt,
        "mark_frames": list(MARKS),
        "diagnostic_window": "each mark +/- 4 frames, near-line detection centers only",
        "stage": "tentative tracks versus leftover high-score detections",
        "iou_min": tracker.cfg.match_iou_thresh,
        "mahalanobis_d2_max": tracker._gate,
        "new_track_score_min": tracker.cfg.new_track_thresh,
        "confirmation_hits": tracker.cfg.n_init,
        "pairs": tracker.pairs,
        "physical_object_correspondence_verified": False,
        "accuracy_claim": False,
    }


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
