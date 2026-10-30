"""Bounded synthetic development screen of 0.60 versus 0.55 track initiation.

No detector training, footage, holdout, parameter sweep or default change.
The committed protocol fixes all 54 paired cells before study execution.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.hvsd_rain_review import LINE, line_crossings
from experiments.traffic_runner import _check_import_origins, _environment, _git, _verify_tree
from visiontrack.detection.base import Detection
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "6ca1d9f54a5376b090e5d7b40dbb2b271138d4ae"
SCORES = (0.54, 0.57, 0.61)
SPEEDS = (2, 6)
CASES = (
    "steady_true", "late_strong", "short_true", "confirmation_gap",
    "confirmed_gap", "brief_false", "persistent_false", "true_and_clutter",
    "long_absence",
)
METHOD_FILES = (
    "experiments/initiation_threshold.py", "tests/test_initiation_threshold.py",
    "docs/INITIATION_THRESHOLD_PROTOCOL.md", "experiments/hvsd_rain_review.py",
    "experiments/traffic_runner.py",
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def scene(case, score, speed):
    """Deterministic supplied proposals and separate scripted truth; no tracker."""
    if case not in CASES or score not in SCORES or speed not in SPEEDS:
        raise ValueError("unregistered cell")
    rows = []
    for frame in range(48 if case == "long_absence" else 12):
        local = frame - 40 if frame >= 40 else frame
        visible = local < (4 if case == "short_true" else
                           2 if case == "brief_false" else
                           8 if case == "long_absence" else 12)
        crossing = 2.5 if case == "short_true" else 0.5 if case == "brief_false" else 4.5
        x = 500 + speed * (local - crossing)
        box = [x - 20, 280, x + 20, 320]
        truth, proposals = [], []
        if visible:
            if case not in {"brief_false", "persistent_false"}:
                truth = [{"id": 1, "xyxy": box.copy()}]
            supplied = not (case == "confirmation_gap" and frame == 1 or
                            case == "confirmed_gap" and frame in {5, 6})
            if supplied:
                confidence = 0.9 if case == "late_strong" and frame >= 4 else score
                if case == "true_and_clutter":
                    proposals.append({"xyxy": box.copy(), "score": 0.9, "class_id": 2})
                    box = [x - 20, 350, x + 20, 390]
                proposals.append({"xyxy": box, "score": confidence, "class_id": 2})
        rows.append({"frame": frame, "truth": truth, "detections": proposals})
    return rows


def replay(tracker, inputs):
    if tracker.frame_index != -1:
        raise ValueError("cold start required")
    rows = []
    for row in inputs:
        before = tracker._next_id
        # Truth is never supplied to the tracker. Arrays are copied per variant.
        outputs = tracker.update([Detection(np.array(d["xyxy"], dtype=float),
                                            d["score"], d["class_id"])
                                  for d in row["detections"]])
        rows.append({"frame": row["frame"], "births": tracker._next_id - before,
                     "observations": [{"id": int(o.track_id), "xyxy": o.xyxy.tolist(),
                                       "score": float(o.score), "class_id": int(o.class_id)}
                                      for o in outputs]})
    return rows


def centers(rows, key):
    return [(r["frame"], o["id"], (o["xyxy"][0] + o["xyxy"][2]) / 2,
             (o["xyxy"][1] + o["xyxy"][3]) / 2) for r in rows for o in r[key]]


def crossing_score(truth, predicted):
    """Exact one-to-one time/position matching; IDs need not agree across worlds."""
    if len(truth) > 2 or len(predicted) > 4:
        raise ValueError("outside bounded crossing scorer capacity")
    eligible = [[-1] + [i for i, p in enumerate(predicted)
                       if abs(t["estimated_frame"] - p["estimated_frame"]) <= 1
                       and abs(t["crossing_y"] - p["crossing_y"]) <= 10] for t in truth]
    assignments = [a for a in itertools.product(*eligible)
                   if len([i for i in a if i >= 0]) == len({i for i in a if i >= 0})]
    def rank(a):
        return (-sum(i >= 0 for i in a), sum(abs(truth[t]["estimated_frame"] -
                predicted[i]["estimated_frame"]) for t, i in enumerate(a) if i >= 0), a)
    best = min(assignments, key=rank)
    tp = sum(i >= 0 for i in best)
    return {"true_events": len(truth), "predicted_events": len(predicted),
            "tp": tp, "fp": len(predicted) - tp, "fn": len(truth) - tp}


def score_run(inputs, outputs):
    if len(inputs) != len(outputs) or any(a["frame"] != i or b["frame"] != i
                                         for i, (a, b) in enumerate(zip(inputs, outputs,
                                                                       strict=True))):
        raise ValueError("complete ordered input/output required")
    accumulator = MotAccumulator(iou_threshold=0.5)
    matched_ids, all_ids, false_ids, matched_frames = {}, set(), set(), set()
    for row, output in zip(inputs, outputs, strict=True):
        truth, observations = row["truth"], output["observations"]
        failures = accumulator.update(
            np.array([t["id"] for t in truth]), np.array([t["xyxy"] for t in truth]),
            np.array([o["id"] for o in observations]), np.array([o["xyxy"] for o in observations]))
        missed = {e.gt_id for e in failures if e.event_type == "miss"}
        false_ids.update(e.hyp_id for e in failures if e.event_type == "false_positive")
        all_ids.update(o["id"] for o in observations)
        for t in truth:
            if t["id"] not in missed:
                matched_ids.setdefault(t["id"], set()).add(accumulator._last_hyp[t["id"]])
                matched_frames.add((row["frame"], t["id"]))
    # Delay is measured separately for each contiguous visible truth segment.
    starts = [(r["frame"], t["id"]) for r in inputs for t in r["truth"]
              if r["frame"] == 0 or t["id"] not in
              {p["id"] for p in inputs[r["frame"] - 1]["truth"]}]
    delays = []
    for start, identity in starts:
        end = start
        while end < len(inputs) and identity in {t["id"] for t in inputs[end]["truth"]}:
            end += 1
        first = next((f for f in range(start, end) if (f, identity) in matched_frames), None)
        delays.append({"reference_id": identity, "start_frame": start,
                       "delay_frames": None if first is None else first - start})
    metrics = asdict(accumulator.result())
    births = sum(o["births"] for o in outputs)
    return {"mot": {k: metrics[k] for k in ("num_gt", "true_positives", "false_positives",
                                           "false_negatives", "id_switches", "fragmentations")},
            "births": births, "unconfirmed_births": births - len(all_ids),
            "public_boxes": sum(len(o["observations"]) for o in outputs),
            "public_ids": len(all_ids), "ids_with_false_positive_boxes": len(false_ids),
            "extra_matched_ids": sum(max(0, len(ids) - 1) for ids in matched_ids.values()),
            "confirmation_delays": delays,
            "crossings": crossing_score(line_crossings(centers(inputs, "truth")),
                                        line_crossings(centers(outputs, "observations")))}


def run_cell(case, confidence, speed, factory=ByteTracker):
    inputs = scene(case, confidence, speed)
    original = digest(inputs)
    runs, results = {}, {}
    for name, threshold in (("baseline", 0.6), ("candidate", 0.55)):
        config = TrackerConfig(new_track_thresh=threshold)
        tracker = factory(config)
        first = replay(tracker, inputs)
        tracker.reset()
        if (encoded(first) != encoded(replay(tracker, inputs)) or
                encoded(first) != encoded(replay(factory(config), inputs))):
            raise ValueError("fresh/reset repeatability mismatch")
        if original != digest(inputs):
            raise ValueError("input mutation")
        runs[name] = first
        results[name] = score_run(inputs, first)
    return inputs, runs, {"case": case, "score": confidence, "speed": speed,
                          "input_sha256": original, "detector_sha256": digest(
                              [r["detections"] for r in inputs]),
                          "output_sha256": {k: digest(v) for k, v in runs.items()}, **results}


def method():
    _check_import_origins()
    sources = {}
    for name in METHOD_FILES:
        data = (ROOT / name).read_bytes()
        if _git(ROOT, "show", f"HEAD:{name}") != data:
            raise ValueError("commit complete method before study execution")
        sources[name] = hashlib.sha256(data).hexdigest()
    if LINE != {"x": 500, "y_min": 205, "y_max": 432,
                "direction": "left-to-right", "region": "near road"}:
        raise ValueError("crossing extraction changed")
    return {"revision": _git(ROOT, "rev-parse", "HEAD").decode().strip(), "sources": sources,
            "package": _verify_tree(ROOT, BASELINE), "environment": _environment(),
            "baseline_config": asdict(TrackerConfig()),
            "changed_setting": {"new_track_thresh": 0.55},
            "cases": CASES, "scores": SCORES, "speeds": SPEEDS,
            "development_only": True, "real_world_accuracy_claim": False}


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def execute(output):
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("new output directory under an existing parent required")
    if any(output.resolve().is_relative_to(p) for p in (ROOT, ROOT.parent / "visiontrack-cpp")):
        raise ValueError("keep complete run artifacts outside both repos")
    provenance = method()
    output.mkdir()
    write(output / "method.json", provenance)
    results = []
    try:
        for case, confidence, speed in itertools.product(CASES, SCORES, SPEEDS):
            directory = output / f"{case}-{confidence:.2f}-{speed}"
            directory.mkdir()
            inputs, runs, result = run_cell(case, confidence, speed)
            write(directory / "inputs.json", inputs)
            for name, rows in runs.items():
                write(directory / f"{name}.json", rows)
            write(directory / "scored.json", result)
            results.append(result)
        if method() != provenance:
            raise ValueError("method drift during execution")
        write(output / "summary.json", {"schema": "visiontrack.initiation-threshold/v1",
              "method": provenance, "cells": results, "paired_cells": 54, "tracker_passes": 324,
              "recommend_default_change": False, "real_world_accuracy_claim": False})
    except BaseException as error:
        write(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
    write(output / "manifest.json", {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*.json"))})
    print(f"Completed {len(results)} paired development cells: {output / 'summary.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    execute(args.output)


if __name__ == "__main__":
    main()
