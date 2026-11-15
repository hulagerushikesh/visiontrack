"""Exploratory process-noise sensitivity at a fixed, declared frame rate.

The tracker's velocity remains in pixels per *observed frame*. Only its
one-step process covariance is scaled. This is an offline hypothesis probe,
not a physical-time Kalman model or a proposed production default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.frame_spacing_gate_probe import FRAME_RATES, SPEEDS_PX_PER_SEC, stream
from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.detection.base import Detection
from visiontrack.tracking.tracker import ByteTracker


class ScaledProcessNoise(KalmanBoxTracker):
    def __init__(self, scale: float) -> None:
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("process variance scale must be finite and positive")
        super().__init__()
        self.scale = scale

    def _process_noise(self, heights: np.ndarray) -> np.ndarray:
        return super()._process_noise(heights) * self.scale


def replay(rows: list[dict], scale: float) -> dict:
    tracker = ByteTracker()
    tracker.kf = ScaledProcessNoise(scale)
    public_ids: set[int] = set()
    public_frames = 0
    for row in rows:
        detections = [Detection(np.asarray(d["xyxy"], dtype=float),
                                float(d["score"]), int(d["class_id"]))
                      for d in row["detections"]]
        output = tracker.update(detections)
        public_ids.update(o.track_id for o in output)
        public_frames += bool(output)
    return {"public_ids": len(public_ids), "births": tracker._next_id - 1,
            "frames_with_public_track": public_frames}


def synthetic() -> dict:
    return {f"{speed}pxps_{fps}fps": {
        "variance_x1": replay(stream(speed, fps), 1.0),
        "variance_x3": replay(stream(speed, fps), 3.0),
        "variance_x9": replay(stream(speed, fps), 9.0),
    } for speed in SPEEDS_PX_PER_SEC for fps in FRAME_RATES}


def saved(path: Path, fps: float) -> dict:
    raw = path.read_bytes()
    rows = json.loads(raw)
    return {"input_sha256": hashlib.sha256(raw).hexdigest(), "fps": fps,
            "frames": len(rows),
            "variance_x1": replay(rows, 1.0),
            "variance_x3": replay(rows, 3.0),
            "variance_x9": replay(rows, 9.0)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved", type=Path)
    parser.add_argument("--fps", type=float)
    args = parser.parse_args()
    if (args.saved is None) != (args.fps is None):
        parser.error("--saved and --fps must be supplied together")
    if args.fps is not None and (not np.isfinite(args.fps) or args.fps <= 0):
        parser.error("--fps must be finite and positive")
    result = {"schema": "visiontrack.frame-rate-noise-probe/v1",
              "scope": "exploratory; public-ID counts are not accuracy",
              "variance_rule": "one-step Q multiplied by 1, 3, or 9; F and lifecycle unchanged",
              "synthetic": synthetic()}
    if args.saved is not None:
        result["saved"] = saved(args.saved, args.fps)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
