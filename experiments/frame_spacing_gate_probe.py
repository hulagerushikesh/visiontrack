"""Exploratory, synthetic check of the default motion gate at two frame rates.

Same physical two-second path and box geometry, with one perfect detection per
sampled frame. This isolates sampling interval from detector and camera domain;
it does not estimate traffic accuracy or justify disabling the gate.
"""

from __future__ import annotations

import json

import numpy as np

from experiments.association_gate_audit import audit
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

SPEEDS_PX_PER_SEC = (60, 120, 180, 240, 300, 360)
FRAME_RATES = (30, 10)


def stream(speed: int, fps: int) -> list[dict]:
    return [{
        "frame": frame,
        "detections": [{
            "xyxy": [x, 200.0, x + 100.0, 270.0], "score": 0.9, "class_id": 2,
        }],
    } for frame in range(2 * fps) for x in [100.0 + speed * frame / fps]]


def no_gate_replay(rows: list[dict]) -> tuple[int, int]:
    tracker = ByteTracker(TrackerConfig(use_mahalanobis_gating=False))
    public_ids: set[int] = set()
    for row in rows:
        detection = row["detections"][0]
        output = tracker.update([Detection(
            np.asarray(detection["xyxy"]), detection["score"], detection["class_id"],
        )])
        public_ids.update(o.track_id for o in output)
    return len(public_ids), tracker._next_id - 1


def run() -> dict:
    cases = []
    for speed in SPEEDS_PX_PER_SEC:
        for fps in FRAME_RATES:
            rows = stream(speed, fps)
            gate_audit, observations = audit(rows)
            no_gate_ids, no_gate_births = no_gate_replay(rows)
            cases.append({
                "speed_px_per_sec": speed,
                "fps": fps,
                "samples": len(rows),
                "default_public_ids": len({
                    obs["id"] for row in observations for obs in row["observations"]
                }),
                "default_births": sum(row["births"] for row in observations),
                "default_motion_vetoed_pairs": gate_audit["motion_vetoed_pairs"],
                "no_gate_public_ids": no_gate_ids,
                "no_gate_births": no_gate_births,
            })
    return {
        "schema": "visiontrack.frame-spacing-gate-probe/v1",
        "scope": "exploratory synthetic mechanism probe; no real-data accuracy claim",
        "geometry": (
            "100x70 px box, constant horizontal velocity, 2 s, "
            "perfect 0.9-confidence car detections"
        ),
        "caveat": (
            "n_init and max_age are frame counts, so their elapsed-time "
            "meaning also changes with fps"
        ),
        "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, allow_nan=False))
