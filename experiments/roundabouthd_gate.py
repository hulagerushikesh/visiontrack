"""RoundaboutHD c001/c003/c004: Mahalanobis gate on vs off at one counting line each.

Frozen protocol: docs/REAL_TRAFFIC_EVIDENCE_GATE.md, "Gate test protocol".
The dataset stays owner-local; pass its root on the command line. Expected
layout: <root>/detection/cNNN/labels_xy/imgXXXXXX.txt and
<root>/labels/imagescNNN_SCT_GT.txt.

    python -m experiments.roundabouthd_gate --root <dir> --output <result.json>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.roundabouthd_threshold import (
    digest,
    load_detections,
    load_reference,
    match,
    replay,
)
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

LINES = {
    "c001": ((223.0, 1377.0), (1363.0, 1947.0)),
    "c003": ((150.0, 1300.0), (2850.0, 1300.0)),
    "c004": ((60.0, 1870.0), (2050.0, 1750.0)),
}
VARIANTS = (("gate_on", {}), ("gate_off", {"use_mahalanobis_gating": False}))


def crossings(centres, line) -> list[dict]:
    """Adjacent-frame, same-ID centre steps across one line segment."""
    (ax, ay), (bx, by) = line

    def side(x, y):
        return (bx - ax) * (y - ay) - (by - ay) * (x - ax)

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
        if 0 <= u <= 1:
            events.append({"frame": frame + 1, "id": ident, "x": round(x, 1), "y": round(y, 1),
                           "dir": "A->B" if s1 < 0 else "B->A"})
    return sorted(events, key=lambda e: (e["frame"], e["id"]))


def decide(cameras: dict) -> dict:
    def total(variant, key):
        return sum(c["variants"][variant][key] for c in cameras.values())

    fn_on, fn_off = total("gate_on", "fn"), total("gate_off", "fn")
    fp_on, fp_off = total("gate_on", "fp"), total("gate_off", "fp")
    gain = total("gate_off", "tp") - total("gate_on", "tp")
    allowance = max(2.0, 0.1 * gain)
    worse = [name for name, c in cameras.items()
             if c["variants"]["gate_off"]["fp"] + c["variants"]["gate_off"]["fn"] >
             c["variants"]["gate_on"]["fp"] + c["variants"]["gate_on"]["fn"]]
    supported = fn_off < fn_on and fp_off - fp_on <= allowance and not worse
    return {"pooled": {"fn": [fn_on, fn_off], "fp": [fp_on, fp_off], "tp_gain": gain,
                       "fp_allowance": allowance},
            "cameras_with_more_errors": worse,
            "verdict": "supported" if supported else "not supported"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cameras = {}
    for cam, line in LINES.items():
        frames = load_detections(args.root / "detection" / cam / "labels_xy")
        centres, duplicates = load_reference(args.root / "labels" / f"images{cam}_SCT_GT.txt")
        reference = crossings(centres, line)
        result = {"line": line, "reference_crossings": len(reference),
                  "reference_duplicate_rows": duplicates,
                  "detections": sum(map(len, frames)), "variants": {}}
        for name, overrides in VARIANTS:
            config = TrackerConfig(**overrides)
            tracker = ByteTracker(config)
            first = replay(tracker, frames)
            tracker.reset()
            if digest(first) != digest(replay(tracker, frames)) or \
                    digest(first) != digest(replay(ByteTracker(config), frames)):
                raise ValueError("fresh/reset repeatability mismatch")
            result["variants"][name] = {"output_sha256": digest(first),
                                        "public_ids": len({k[1] for k in first}),
                                        **match(reference, crossings(first, line))}
        cameras[cam] = result
        print(cam, len(reference), {n: {k: v[k] for k in ("tp", "fp", "fn")}
                                    for n, v in result["variants"].items()}, flush=True)
    output = {"protocol": "docs/REAL_TRAFFIC_EVIDENCE_GATE.md#gate-test",
              "cameras": cameras, "decision": decide(cameras)}
    args.output.write_text(json.dumps(output, indent=1))
    print(json.dumps(output["decision"]))


if __name__ == "__main__":
    main()
