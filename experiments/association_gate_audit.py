"""Read-only audit of Kalman-gate vetoes on a saved detection stream.

This counts *candidate pairs*, not tracking mistakes. A rejected candidate may
be a wrong association; ground truth and downstream crossing scores are needed
to judge any proposed tracker change. The default tracker is replayed unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from visiontrack.detection.base import Detection
from visiontrack.tracking.tracker import ByteTracker


def audit(rows: list[dict]) -> tuple[dict, list[dict]]:
    tracker = ByteTracker()
    counts: Counter[str] = Counter()
    veto_frames: Counter[int] = Counter()
    observations = []

    def observe(cost, max_cost, tracks, dets, ious, iou_thresh,
                class_mismatch, gating_d2, gate_thresh, result):
        del cost, max_cost, result
        if gate_thresh is None:
            return
        compatible = (np.ones_like(ious, dtype=bool) if class_mismatch is None
                      else ~class_mismatch)
        feasible_iou = (ious >= iou_thresh) & compatible
        vetoed = feasible_iou & (gating_d2 > gate_thresh)
        counts["iou_and_class_eligible_pairs"] += int(feasible_iou.sum())
        counts["motion_vetoed_pairs"] += int(vetoed.sum())
        if vetoed.any():
            veto_frames[tracker.frame_index] += int(vetoed.sum())

    tracker._association_observer = observe
    try:
        for index, row in enumerate(rows):
            if row["frame"] != index:
                raise ValueError("expected consecutive zero-based frame indices")
            before = tracker._next_id
            dets = [Detection(np.asarray(d["xyxy"], dtype=float),
                              float(d["score"]), int(d["class_id"]))
                    for d in row["detections"]]
            output = tracker.update(dets)
            observations.append({
                "frame": index,
                "births": tracker._next_id - before,
                "observations": [{
                    "id": int(o.track_id), "xyxy": o.xyxy.tolist(),
                    "score": float(o.score), "class_id": int(o.class_id),
                } for o in output],
            })
    finally:
        tracker._association_observer = None
    return {
        "frames": len(rows),
        "detections": sum(len(row["detections"]) for row in rows),
        "iou_and_class_eligible_pairs": counts["iou_and_class_eligible_pairs"],
        "motion_vetoed_pairs": counts["motion_vetoed_pairs"],
        "frames_with_motion_veto": len(veto_frames),
        "vetoes_by_frame": dict(sorted(veto_frames.items())),
    }, observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("detections", type=Path)
    parser.add_argument("--expected-observations", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source_bytes = args.detections.read_bytes()
    result, observations = audit(json.loads(source_bytes))
    result["detections_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    if args.expected_observations:
        expected_bytes = args.expected_observations.read_bytes()
        expected = json.loads(expected_bytes)
        if observations != expected:
            raise ValueError("default replay differs from frozen observations")
        result["frozen_observations_equal"] = True
        result["frozen_observations_sha256"] = hashlib.sha256(expected_bytes).hexdigest()
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
