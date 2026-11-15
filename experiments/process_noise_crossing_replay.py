"""Post-hoc crossing check for fixed process-noise scales on two frozen cameras.

Uses each camera's previously frozen labels, event extraction and scoring.
No detector execution, footage export, production default change or tuning.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np

from experiments.frame_rate_noise_probe import ScaledProcessNoise
from experiments.initiation_threshold import replay
from visiontrack.core.geometry import iou_matrix
from visiontrack.tracking.tracker import ByteTracker


def load_adapter(directory):
    spec = importlib.util.spec_from_file_location("run_holdout", directory / "run_holdout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_camera(directory, mode, first_frame):
    adapter = load_adapter(directory)
    path = directory / "result" / f"{mode}-detections.json"
    raw = path.read_bytes()
    detections = json.loads(raw)
    reference_raw = (directory / "reference.json").read_bytes()
    reference = json.loads(reference_raw)
    boxes = {(frame, identity): box for frame, identity, box, _ in adapter.reference_rows()}
    if len(detections) != adapter.FRAMES or len(reference) != (16 if first_frame == 0 else 5):
        raise ValueError("unexpected frozen input size")
    baseline = json.loads((directory / "result" / "summary.json").read_text())
    expected = baseline["conditions"][mode]
    result = {"frames": adapter.FRAMES, "fps": adapter.FPS,
              "detection_sha256": hashlib.sha256(raw).hexdigest(),
              "reference_sha256": hashlib.sha256(reference_raw).hexdigest(),
              "variants": {}}
    for scale in (1, 3, 9):
        tracker = ByteTracker()
        tracker.kf = ScaledProcessNoise(scale)
        observed = replay(tracker, detections)
        predicted = adapter.events((
            (row["frame"], obs["id"], obs["xyxy"], adapter.CLASSES[obs["class_id"]])
            for row in observed if row["frame"] >= first_frame
            for obs in row["observations"]
        ), reference=False)
        scored = adapter.scores(predicted, reference)
        matched_details = []
        for pair in scored["matches"]:
            frame = pair["reference"]["frame"]
            truth_id = pair["reference"]["track_id"]
            predicted_id = pair["predicted"]["track_id"]
            observed_box = next((item["xyxy"] for item in observed[frame]["observations"]
                                 if item["id"] == predicted_id), None)
            if observed_box is None:
                raise ValueError("matched track absent at reference frame")
            overlap = float(iou_matrix(np.asarray([boxes[frame, truth_id]]),
                                       np.asarray([observed_box]))[0, 0])
            matched_details.append({"frame": frame, "same_frame_iou": overlap})
        if scale == 1:
            for key in ("matched_crossings", "max_cardinality_matches", "matches",
                        "unmatched_predictions", "missed_references"):
                if scored[key] != expected[key]:
                    raise ValueError(f"default mismatch: {directory.name}/{key}")
        result["variants"][f"variance_x{scale}"] = {
            "matched": scored["matched_crossings"],
            "max_cardinality_matches": scored["max_cardinality_matches"],
            "missed": len(scored["missed_references"]),
            "extra": len(scored["unmatched_predictions"]),
            "match_reference_frames": [row["reference"]["frame"] for row in scored["matches"]],
            "match_overlap": matched_details,
            "miss_reference_frames": [row["frame"] for row in scored["missed_references"]],
            "extra_prediction_frames": [row["frame"] for row in scored["unmatched_predictions"]],
            "births": tracker._next_id - 1,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("walkthrough_root", type=Path)
    args = parser.parse_args()
    root = args.walkthrough_root.resolve()
    cameras = {
        "hanoi": (root / "vn-preprocessing-holdout-20261114", "bgr-bilinear", 0),
        "aicc_c002": (root / "aicc22-preprocessing-holdout-20261114", "bgr-bilinear", 2),
    }
    output = {"schema": "visiontrack.process-noise-crossings/v1",
              "scope": "post-hoc diagnostic on previously inspected cameras; "
                       "not independent validation",
              "rule": "Q x1/x3/x9; F, lifecycle, detections and frozen crossing scoring unchanged",
              "cameras": {}}
    for name, (directory, mode, first_frame) in cameras.items():
        prior = Path.cwd()
        try:
            os.chdir(directory)
            output["cameras"][name] = run_camera(directory, mode, first_frame)
        finally:
            os.chdir(prior)
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
