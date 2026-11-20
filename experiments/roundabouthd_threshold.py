"""RoundaboutHD c002: initiation threshold 0.60 vs 0.55 on real crossings.

Frozen protocol: docs/REAL_TRAFFIC_EVIDENCE_GATE.md, "Step 3 protocol".
The dataset stays owner-local; pass its paths on the command line.

    python -m experiments.roundabouthd_threshold \
        --detections <labels_xy dir> --labels <imagesc002 SCT_GT.txt> \
        --output <result.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from visiontrack.core.assignment import linear_assignment
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

FRAMES = 9000
LINE = ((491.0, 1396.0), (1245.0, 2108.0))  # owner line, full-resolution pixels
DEV = (3633 - 3, 5432 + 3)  # development window plus buffer, excluded
MAX_FRAMES, MAX_PX = 3, 150.0
VARIANTS = (("baseline", 0.60), ("candidate", 0.55))


def side(x: float, y: float) -> float:
    (ax, ay), (bx, by) = LINE
    return (bx - ax) * (y - ay) - (by - ay) * (x - ax)


def crossings(centres: dict[tuple[int, int], tuple[float, float]]) -> list[dict]:
    """Adjacent-frame, same-ID centre steps across the line segment."""
    (ax, ay), (bx, by) = LINE
    events = []
    for (frame, ident), p in centres.items():
        q = centres.get((frame + 1, ident))
        if q is None:
            continue
        s1, s2 = side(*p), side(*q)
        if s1 == 0 or s1 * s2 > 0:
            continue
        t = s1 / (s1 - s2)
        x, y = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
        u = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
        if 0 <= u <= 1 and not DEV[0] <= frame + 1 <= DEV[1]:
            events.append({"frame": frame + 1, "id": ident, "x": round(x, 1), "y": round(y, 1),
                           "dir": "A->B" if s1 < 0 else "B->A"})
    return sorted(events, key=lambda e: (e["frame"], e["id"]))


def match(reference: list[dict], predicted: list[dict]) -> dict:
    """One to one: maximize matches, then minimize total frame difference."""
    pairs = []
    if reference and predicted:
        cost = np.zeros((len(reference), len(predicted)))
        for i, r in enumerate(reference):
            for j, p in enumerate(predicted):
                df = abs(r["frame"] - p["frame"])
                dist = ((r["x"] - p["x"]) ** 2 + (r["y"] - p["y"]) ** 2) ** 0.5
                if r["dir"] == p["dir"] and df <= MAX_FRAMES and dist <= MAX_PX:
                    cost[i, j] = df - 1000.0
        rows, cols = linear_assignment(cost)
        pairs = [(int(i), int(j)) for i, j in zip(rows, cols, strict=True) if cost[i, j] < 0]
    used_r, used_p = {i for i, _ in pairs}, {j for _, j in pairs}
    return {"reference": len(reference), "predicted": len(predicted), "tp": len(pairs),
            "fp": len(predicted) - len(pairs), "fn": len(reference) - len(pairs),
            "frame_differences": sorted(abs(reference[i]["frame"] - predicted[j]["frame"])
                                        for i, j in pairs),
            "missed": [r for i, r in enumerate(reference) if i not in used_r],
            "false": [p for j, p in enumerate(predicted) if j not in used_p]}


def load_detections(directory: Path) -> list[list[dict]]:
    frames = []
    for k in range(FRAMES):  # file k holds label frame k + 1
        rows = []
        for line in (directory / f"img{k:06d}.txt").read_text().splitlines():
            if line.strip():
                c, x1, y1, x2, y2, s = line.split()
                rows.append({"xyxy": [float(x1), float(y1), float(x2), float(y2)],
                             "score": float(s), "class_id": int(c)})
        frames.append(rows)
    return frames


def load_reference(path: Path) -> tuple[dict, int]:
    boxes: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for line in path.read_text().splitlines():
        t = re.split(r"[ \t,]+", line.strip())
        if len(t) < 6:
            continue
        x1, y1, x2, y2 = (float(v) for v in t[2:6])
        x1, x2 = (min(3840.0, max(0.0, v)) for v in (x1, x2))
        y1, y2 = (min(2160.0, max(0.0, v)) for v in (y1, y2))
        boxes.setdefault((int(float(t[0])), int(float(t[1]))), []).append(
            ((x1 + x2) / 2, (y1 + y2) / 2))
    centres = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v))
               for k, v in boxes.items()}
    return centres, sum(len(v) > 1 for v in boxes.values())


def replay(tracker: ByteTracker, frames: list[list[dict]]) -> dict:
    centres = {}
    for index, rows in enumerate(frames):
        outputs = tracker.update([Detection(np.array(r["xyxy"]), r["score"], r["class_id"])
                                  for r in rows])
        for o in outputs:
            x1, y1, x2, y2 = o.xyxy.tolist()
            centres[(index + 1, int(o.track_id))] = ((x1 + x2) / 2, (y1 + y2) / 2)
    return centres


def digest(value) -> str:
    text = json.dumps(sorted((list(k), list(v)) for k, v in value.items()))
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detections", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frames = load_detections(args.detections)
    reference_centres, duplicates = load_reference(args.labels)
    reference = crossings(reference_centres)
    result = {"protocol": "docs/REAL_TRAFFIC_EVIDENCE_GATE.md#step-3",
              "line": LINE, "excluded_frames": DEV, "reference_duplicate_rows": duplicates,
              "detections": sum(map(len, frames)), "reference_crossings": len(reference),
              "variants": {}}
    for name, threshold in VARIANTS:
        config = TrackerConfig(new_track_thresh=threshold)
        tracker = ByteTracker(config)
        first = replay(tracker, frames)
        tracker.reset()
        if digest(first) != digest(replay(tracker, frames)) or \
                digest(first) != digest(replay(ByteTracker(config), frames)):
            raise ValueError("fresh/reset repeatability mismatch")
        predicted = crossings(first)
        result["variants"][name] = {"new_track_thresh": threshold,
                                    "output_sha256": digest(first),
                                    "public_ids": len({k[1] for k in first}),
                                    **match(reference, predicted)}
    base, cand = result["variants"]["baseline"], result["variants"]["candidate"]
    adopt = cand["tp"] > base["tp"] and cand["fp"] <= base["fp"]
    result["decision"] = "adopt 0.55" if adopt else "keep 0.60"
    args.output.write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in ("reference_crossings", "decision")}))
    for name in ("baseline", "candidate"):
        v = result["variants"][name]
        print(name, {k: v[k] for k in ("tp", "fp", "fn", "predicted", "public_ids")})


if __name__ == "__main__":
    main()
