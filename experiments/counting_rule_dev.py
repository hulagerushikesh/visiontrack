"""Development run for the jitter-proof counting rules (docs/COUNTING_RULE_DEVELOPMENT.md).

RoundaboutHD, all four cameras, the three motion-gate variants. Every frame has
been used before, so this is development evidence only. Each rule is applied to
the reference tracks and the tracker output alike.

    python -m experiments.counting_rule_dev --roundabout <root> --cache <dir> --output <json>
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS, make_tracker
from experiments.crossing_rules import cancel_reversals, hysteresis_crossings
from experiments.roundabouthd_gate import LINES, crossings, decide
from experiments.roundabouthd_threshold import LINE as C002_LINE
from experiments.roundabouthd_threshold import (
    digest,
    load_detections,
    load_reference,
    match,
    replay,
)

CAMERAS = ("c001", "c002", "c003", "c004")
WINDOWS = (8, 15, 30)  # frames at 15 fps; 15 (one second) is the primary choice
BANDS = (25.0, 50.0, 100.0)  # pixels at 3840x2160; 50 is the primary choice


def rules(centres: dict, line) -> dict[str, list[dict]]:
    plain = crossings(centres, line)
    out = {"plain": plain}
    out |= {f"cancel_{w}": cancel_reversals(plain, w) for w in WINDOWS}
    out |= {f"hysteresis_{int(b)}": hysteresis_crossings(centres, line, b) for b in BANDS}
    return out


def tracked(root: Path, cache: Path, cam: str, variant: str) -> dict:
    path = cache / f"{cam}-{variant}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    frames = load_detections(root / "detection" / cam / "labels_xy")
    first = replay(make_tracker(variant), frames)
    if digest(first) != digest(replay(make_tracker(variant), frames)):
        raise ValueError("repeatability mismatch")
    path.write_bytes(pickle.dumps(first))
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roundabout", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    lines = dict(LINES, c002=C002_LINE)
    cams: dict = {}
    for cam in CAMERAS:
        ref_centres, _ = load_reference(args.roundabout / "labels" / f"images{cam}_SCT_GT.txt")
        reference = rules(ref_centres, lines[cam])
        cams[cam] = {"reference": {r: len(v) for r, v in reference.items()}, "variants": {}}
        for variant in VARIANTS:
            predicted = rules(tracked(args.roundabout, args.cache, cam, variant), lines[cam])
            cams[cam]["variants"][variant] = {
                r: {k: m[k] for k in ("tp", "fp", "fn")}
                for r in reference for m in [match(reference[r], predicted[r])]}
        print(cam, {v: cams[cam]["variants"][v]["cancel_15"] for v in VARIANTS}, flush=True)
    rule_names = list(cams["c001"]["reference"])
    pooled = {r: {v: {k: sum(cams[c]["variants"][v][r][k] for c in CAMERAS)
                      for k in ("tp", "fp", "fn")} for v in VARIANTS} for r in rule_names}
    reference_totals = {r: sum(cams[c]["reference"][r] for c in CAMERAS) for r in rule_names}
    # Post hoc only: the frozen gate test's decision recomputed under each counting rule.
    gate_test = {r: decide({c: {"variants": {v: cams[c]["variants"][v][r]
                                             for v in ("gate_on", "gate_off")}}
                            for c in ("c001", "c003", "c004")})["verdict"] for r in rule_names}
    result = {"status": "development only: all data previously used",
              "cameras": cams, "pooled": pooled, "reference_crossings": reference_totals,
              "gate_test_recomputed_post_hoc": gate_test}
    args.output.write_text(json.dumps(result, indent=1))
    print(json.dumps({"reference": reference_totals, "pooled": pooled, "gate_test": gate_test}))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
