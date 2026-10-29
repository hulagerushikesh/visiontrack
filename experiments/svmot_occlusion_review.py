"""Preselect a bounded SVMOT development occlusion for visual label review.

Only explicitly named official-train sequences are read. The highest single
annotated occlusion fraction is used to pick a difficult case; this is a label
quality probe, not a tracker evaluation or independent ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _center(box: list[float]) -> tuple[float, float]:
    x, y, width, height = box
    return x + width / 2, y + height / 2


def select_event(root: Path, train_file: Path, test_file: Path,
                 sequences: list[str]) -> dict:
    train = set(train_file.read_text(encoding="utf-8").split())
    test = set(test_file.read_text(encoding="utf-8").split())
    if not train or train & test or not sequences or len(sequences) != len(set(sequences)):
        raise ValueError("invalid or overlapping split/selection")
    if any(Path(seq).name != seq or seq in {".", ".."} for seq in sequences):
        raise ValueError("sequence name must be a plain directory name")
    if not set(sequences) <= train or set(sequences) & test:
        raise ValueError("selection must contain official train sequences only")

    candidates = []
    for sequence in sorted(sequences):
        source = root / "data" / sequence / "occlusion.json"
        data = source.read_bytes()
        observations: dict[int, dict[int, dict]] = {}
        for entry in json.loads(data):
            frame = entry["frame_id"]
            for obj in entry["objects"]:
                observations.setdefault(obj["object_id"], {})[frame] = obj
        for object_id, track in observations.items():
            for onset in sorted(track):
                if (onset <= 3 or onset - 1 not in track or
                        not track[onset]["occlusions"] or track[onset - 1]["occlusions"]):
                    continue
                clear = onset
                while clear in track and track[clear]["occlusions"]:
                    clear += 1
                if (not 5 <= clear - onset <= 30 or
                        any(frame not in track for frame in range(onset - 3, clear + 4))):
                    continue

                movement = math.dist(_center(track[onset - 1]["bbox"]),
                                     _center(track[clear]["bbox"]))
                if movement < 50:
                    continue
                severity = max(
                    max(link["area"] for link in track[frame]["occlusions"])
                    / (track[frame]["bbox"][2] * track[frame]["bbox"][3])
                    for frame in range(onset, clear)
                )
                candidates.append({
                    "sequence": sequence,
                    "object_id": object_id,
                    "onset_frame": onset,
                    "first_clear_frame": clear,
                    "review_start_frame": onset - 3,
                    "review_end_frame": clear + 3,
                    "occluded_frames": clear - onset,
                    "max_single_occlusion_fraction": severity,
                    "center_displacement_px": movement,
                    "occlusion_sha256": hashlib.sha256(data).hexdigest(),
                })
    if not candidates:
        raise ValueError("no qualifying development occlusion")
    winner = sorted(candidates, key=lambda row: (
        -row["max_single_occlusion_fraction"], row["sequence"],
        row["onset_frame"], row["object_id"],
    ))[0]
    return {
        "schema": "visiontrack.svmot-occlusion-review-selection/v1",
        "scope": "selected official-train sequences only",
        "criteria": {
            "pre_frames": 3, "post_frames": 3,
            "occluded_frame_range_inclusive": [5, 30],
            "minimum_center_displacement_px": 50,
            "ranking": "maximum single-link occlusion area / target box area, descending",
        },
        "qualifying_events": len(candidates),
        "selected_event": winner,
        "test_labels_opened": False,
        "tracker_ran": False,
        "physical_identity_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--train-file", required=True, type=Path)
    parser.add_argument("--test-file", required=True, type=Path)
    parser.add_argument("--sequence", required=True, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = select_event(args.root, args.train_file, args.test_file, args.sequence)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
