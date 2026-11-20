"""Development run for the aspect-free gate (docs/ASPECT_GATE_DEVELOPMENT.md).

Two parts, both on data already used in this project, so the result is
development evidence only:

1. RoundaboutHD, all four cameras, full 9000 frames: line-crossing TP/FP/FN.
2. MOT17 val-half, FRCNN public detections: HOTA/IDF1/MOTA/ID switches, to
   check the candidate does not harm the pedestrian setting the default was
   tuned for.

    python -m experiments.aspect_gate_dev --roundabout <root> --output <json>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS, make_tracker
from experiments.roundabouthd_gate import LINES, crossings
from experiments.roundabouthd_threshold import LINE as C002_LINE
from experiments.roundabouthd_threshold import (
    digest,
    load_detections,
    load_reference,
    match,
    replay,
)

MOT17_VIDEOS = ("MOT17-02", "MOT17-04", "MOT17-05", "MOT17-09", "MOT17-10", "MOT17-11", "MOT17-13")


def roundabout(root: Path) -> dict:
    lines = dict(LINES, c002=C002_LINE)
    out = {}
    for cam in ("c001", "c002", "c003", "c004"):
        frames = load_detections(root / "detection" / cam / "labels_xy")
        centres, _ = load_reference(root / "labels" / f"images{cam}_SCT_GT.txt")
        reference = crossings(centres, lines[cam])
        out[cam] = {"reference": len(reference)}
        for variant in VARIANTS:
            first = replay(make_tracker(variant), frames)
            if digest(first) != digest(replay(make_tracker(variant), frames)):
                raise ValueError("repeatability mismatch")
            result = match(reference, crossings(first, lines[cam]))
            out[cam][variant] = {k: result[k] for k in ("tp", "fp", "fn")} | {
                "public_ids": len({k[1] for k in first}), "output_sha256": digest(first)}
        summary = {v: {k: out[cam][v][k] for k in ("tp", "fp", "fn")} for v in VARIANTS}
        print(cam, summary, flush=True)
    out["pooled"] = {v: {k: sum(out[c][v][k] for c in ("c001", "c002", "c003", "c004"))
                         for k in ("tp", "fp", "fn", "public_ids")} for v in VARIANTS}
    return out


def mot17() -> dict:
    import visiontrack.eval.mot17 as mot
    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.datasets.splits import load_split
    from visiontrack.tracking.config import TrackerConfig

    split = load_split("mot17_val_half")
    original = mot.ByteTracker
    out = {}
    try:
        for variant in VARIANTS:
            mot.ByteTracker = lambda cfg, _v=variant: make_tracker(_v, cfg)
            per_video = {}
            for video in MOT17_VIDEOS:
                name = f"{video}-FRCNN"
                first, last = split.range_for(name, "val")
                frames = mot.run_sequence(CachedSequence(Path(f"data/cache/mot17/{name}.npz")),
                                          TrackerConfig(), first, last)
                metrics = mot.evaluate_frames(frames)
                per_video[video] = {k: round(float(v), 4) for k, v in metrics.items()
                                    if isinstance(v, (int, float))}
            keys = sorted(set.intersection(*(set(v) for v in per_video.values())))
            mean = {k: round(float(np.mean([per_video[v][k] for v in per_video])), 4) for k in keys}
            out[variant] = {"per_video": per_video, "mean_over_videos": mean}
            print("MOT17", variant, {k: mean[k] for k in ("HOTA", "IDF1", "MOTA", "IDSW")},
                  flush=True)
    finally:
        mot.ByteTracker = original
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roundabout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"status": "development only: all data previously used",
              "roundabouthd": roundabout(args.roundabout), "mot17_val_half_frcnn": mot17()}
    args.output.write_text(json.dumps(result, indent=1))
    print(json.dumps(result["roundabouthd"]["pooled"]))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
