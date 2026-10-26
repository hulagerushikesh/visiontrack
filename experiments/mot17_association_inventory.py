"""Read the fixed 36--57 saved trace: detection support is not identity truth.

No tracker execution, reassignment, new pixels, tuning or intervention outcome.
The raw two-reference capacity deliberately ignores other objects and cannot
be interpreted as achievable recall or a feasible whole-scene assignment.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import require
from experiments.mot17_coverage_v2 import read_packet
from visiontrack.eval.geometry import metric_iou

TRACE_MANIFEST = "4fef0282c0c8ec68fb5339256846abc37439764e050303795fd6e0ebb283c471"
WINDOW = (36, 57)
REFERENCES = (85, 89)


def capacity(supports):
    """Two reference nodes: a shared detection may be used only once."""
    left, right = supports
    if any(a != b for a in left for b in right):
        return 2
    return int(bool(left or right))


def frame_inventory(raw, events):
    require(all(e["source_frame"] == raw["source_frame"] for e in events),
            "mixed source frames")
    starts = [e for e in events if e["kind"] == "frame_start"]
    ends = [e for e in events if e["kind"] == "frame_end"]
    require(len(starts) == len(ends) == 1, "unique frame boundaries required")
    detections = starts[0]["detections"]
    require([d["row"] for d in detections] == list(range(1, len(detections) + 1)),
            "ordered one-based detection rows required")
    require([d["xyxy"] for d in detections] == raw["detections_xyxy"] and
            [d["score"] for d in detections] == raw["detection_scores"],
            "trace detections differ from saved input")
    require(len(set(raw["gt_ids"])) == len(raw["gt_ids"]) and
            all(len(raw[k]) == len(raw["gt_ids"]) for k in (
                "gt_xyxy", "gt_classes", "gt_consider")), "unaligned references")
    refs = []
    for identity in REFERENCES:
        require(identity in raw["gt_ids"], "required reference missing")
        index = raw["gt_ids"].index(identity)
        require(raw["gt_classes"][index] == 1 and raw["gt_consider"][index] == 1,
                "scored pedestrian reference required")
        refs.append(raw["gt_xyxy"][index])
    boxes = np.asarray([d["xyxy"] for d in detections], dtype=float).reshape(-1, 4)
    reference_boxes = np.asarray(refs, dtype=float)
    require(bool(np.isfinite(boxes).all()) and bool(np.isfinite(reference_boxes).all()) and
            bool((boxes[:, 2:] > boxes[:, :2]).all()) and
            bool((reference_boxes[:, 2:] > reference_boxes[:, :2]).all()),
            "finite positive-area boxes required")
    overlaps = metric_iou(reference_boxes, boxes)
    updates = [e for e in events if e["kind"] == "_apply_match"]
    old_updates = [e for e in updates if e["before"]["track_id"] == 19]
    require(len(old_updates) == 1 and 19 in ends[0]["public_ids"],
            "one public track-19 update required")
    selected = old_updates[0]["detection_row"]
    stages = [e for e in events if e["kind"] == "_match"]
    require([e["stage"] for e in stages] == [
        "confirmed_high", "confirmed_low_recovery", "tentative_leftover_high"],
        "complete ordered stages required")
    assigned = {e["detection_row"]: e["before"]["track_id"] for e in updates}
    require(len(assigned) == len(updates), "detection reused across updates")
    rows = []
    for col, detection in enumerate(detections):
        score = detection["score"]
        require(np.isfinite(score) and 0 <= score <= 1, "invalid score")
        # Retain every raw row, including sub-threshold and unsupported ones.
        offered = []
        for stage in stages:
            ids = [t["track_id"] for t in stage["tracks"]]
            require(len(set(ids)) == len(ids) and
                    len(set(stage["detection_rows"])) == len(stage["detection_rows"]),
                    "unique stage rows required")
            if 19 not in ids or detection["row"] not in stage["detection_rows"]:
                continue
            ti, di = ids.index(19), stage["detection_rows"].index(detection["row"])
            matrices = stage["matrices"]
            pair = {key: matrices[key][ti][di] if matrices[key] is not None else None
                    for key in ("ious", "class_mismatch", "gating_d2", "cost")}
            pair.update(stage=stage["stage"], forbidden=stage["forbidden"][ti][di],
                        max_cost=stage["max_cost"], gate_threshold=stage["gate_threshold"])
            require(pair["forbidden"] == (pair["cost"] > pair["max_cost"]),
                    "recorded feasibility/cost disagree")
            offered.append(pair)
        rows.append(dict(row=detection["row"], score=score,
                         reference_ious=overlaps[:, col].tolist(),
                         supported_reference_ids=[REFERENCES[i] for i in range(2)
                                                  if overlaps[i, col] >= 0.5],
                         assigned_track_id=assigned.get(detection["row"]),
                         offered_to_19=offered))
    pools = {}
    for name, threshold in (("raw", 0), ("eligible", 0.1), ("high", 0.5)):
        supports = [[r["row"] for r in rows if r["score"] >= threshold and
                     identity in r["supported_reference_ids"]] for identity in REFERENCES]
        pools[name] = dict(reference_rows=supports, two_reference_capacity=capacity(supports))
    chosen = rows[selected - 1]
    require(any(p["forbidden"] is False for p in chosen["offered_to_19"]) and
            chosen["assigned_track_id"] == 19, "selected pair not feasible/assigned")
    return dict(source_frame=raw["source_frame"], selected_row=selected,
                selected_support=chosen["supported_reference_ids"], pools=pools,
                detections=rows)


def method():
    return dict(schema="visiontrack.mot17-association-inventory/v1",
                source_window=list(WINDOW), reference_ids=list(REFERENCES), track_id=19,
                baseline_manifest_sha256=BASELINE_MANIFEST,
                trace_manifest_sha256=TRACE_MANIFEST, diagnostic_iou_threshold=0.5,
                question="Are two distinct raw detections available during the known "
                         "correspondence change, and what pairs were actually offered to 19?",
                limits="Exploratory known episode, not preregistered validation. "
                       "Raw support ignores scoring ignore-removal and other objects; "
                       "capacity is not achievable recall. No solver rerun, tracker, "
                       "counterfactual, pixels, label adjudication or physical ID claim.")


def execute(baseline, trace, output):
    root = Path(__file__).resolve().parents[1]
    require(not output.exists() and not output.is_symlink(), "new output required")
    require(output.parent.is_dir() and not output.resolve().is_relative_to(root),
            "existing external parent required")
    original = read_bundle(baseline)
    packet = read_packet(trace, TRACE_MANIFEST)
    require(packet["raw.jsonl"] == original["run-1/raw.jsonl"], "trace raw outputs differ")
    source_files = [Path(__file__).resolve(), root / "src/visiontrack/eval/geometry.py"]
    hashes = {str(p): sha(p) for p in source_files}
    output.mkdir()
    write_json(output / "method.json", dict(**method(), source_sha256=hashes))
    try:
        saved = [json.loads(line) for line in packet["raw.jsonl"].splitlines()]
        require([r["source_frame"] for r in saved] == list(range(1, 1051)),
                "complete ordered raw sequence required")
        events = [json.loads(line) for line in packet["events.jsonl"].splitlines()]
        require({e["source_frame"] for e in events} == set(range(36, 58)),
                "exact fixed trace window required")
        frames = [frame_inventory(saved[f - 1], [e for e in events if e["source_frame"] == f])
                  for f in range(36, 58)]
        require(read_bundle(baseline) == original and read_packet(trace, TRACE_MANIFEST) == packet
                and all(sha(Path(p)) == digest for p, digest in hashes.items()),
                "input or implementation changed")
        summary = dict(frames=len(frames), selected_support_counts=dict(Counter(
            "+".join(map(str, f["selected_support"])) or "neither" for f in frames)),
            eligible_capacity_counts=dict(Counter(
                str(f["pools"]["eligible"]["two_reference_capacity"]) for f in frames)),
            tracker_executed=False, physical_identity_established=False,
            intervention_tested=False, independent_review_completed=False)
        write_json(output / "frames.json", frames)
        write_json(output / "summary.json", summary)
    except Exception as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "trace", "output"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(encoded(method()))
        return
    require(all(v is not None for v in (args.baseline, args.trace, args.output)),
            "explicit inputs/output required")
    execute(args.baseline, args.trace, args.output)


if __name__ == "__main__":
    main()
