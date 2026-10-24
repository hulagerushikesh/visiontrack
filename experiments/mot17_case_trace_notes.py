"""Extract a small same-event table from the sealed trace; never run a tracker.

Raw-box IoU to the reference is descriptive. Internal IoU/gate/cost and updates
come from observed calls, not from recomputing an alternative association.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import sha, write_json
from experiments.mot17_case_intake import require
from visiontrack.core.geometry import iou_matrix

TRACE_MANIFEST = "d15c90d36cc851e4fa80b06438bcae3443b4343e70545878fef4c5630b12fdd9"


def overlap(reference, box):
    return float(iou_matrix(np.array([reference]), np.array([box]))[0, 0])


def scoring_neighbors(raw, box):
    neighbors = [dict(gt_id=g, iou=overlap(reference, box))
                 for g, reference, cls, consider in zip(
                     raw["gt_ids"], raw["gt_xyxy"], raw["gt_classes"], raw["gt_consider"],
                     strict=True) if cls == 1 and consider >= 1]
    return sorted((n for n in neighbors if n["iou"] >= 0.5),
                  key=lambda n: (-n["iou"], n["gt_id"]))


def frame_notes(raw, events, event):
    require(all(e["source_frame"] == raw["source_frame"] for e in events),
            "mixed trace frames")
    gt_id = event["gt_id"]
    require(raw["gt_ids"].count(gt_id) == 1, "unique reference required")
    reference = raw["gt_xyxy"][raw["gt_ids"].index(gt_id)]
    overlaps = [overlap(reference, box) for box in raw["detections_xyxy"]]
    require(bool(overlaps), "no raw detection in selected context")
    # A deterministic pointwise maximum, NOT a detection-to-person identity claim.
    best = int(np.argmax(overlaps)) + 1
    stages = [e for e in events if e["kind"] == "_match"]
    target_ids = (event["previous_hyp_id"], event["hyp_id"])
    accepted, pair_checks = [], []
    for stage in stages:
        tracks, dets = stage["tracks"], stage["detection_rows"]
        ids = [t["track_id"] for t in tracks]
        if best in dets:
            di = dets.index(best)
            for ti, track in enumerate(tracks):
                if track["track_id"] in target_ids:
                    matrices = stage["matrices"]
                    pair_checks.append(dict(
                        stage=stage["stage"], track_id=track["track_id"],
                        iou=matrices["ious"][ti][di],
                        d2=None if matrices["gating_d2"] is None
                        else matrices["gating_d2"][ti][di],
                        gate_threshold=stage["gate_threshold"],
                        class_mismatch=None if matrices["class_mismatch"] is None
                        else matrices["class_mismatch"][ti][di],
                        forbidden=stage["forbidden"][ti][di],
                        cost=matrices["cost"][ti][di], max_cost=stage["max_cost"]))
        for ti, di in stage["matches"]:
            accepted.append((ids[ti], dets[di], stage["stage"]))
    updates = []
    for update in (e for e in events if e["kind"] == "_apply_match"):
        tid, row = update["after"]["track_id"], update["detection_row"]
        matches = [s for t, d, s in accepted if (t, d) == (tid, row)]
        require(len(matches) == 1, "update not backed by a unique accepted stage pair")
        if tid in target_ids:
            updates.append(dict(
                track_id=tid, detection_row=row, stage=matches[0],
                raw_iou_to_reference=overlaps[row - 1],
                output_iou_to_reference=overlap(reference, update["after"]["xyxy"]),
                scoring_reference_neighbors=scoring_neighbors(raw, update["after"]["xyxy"]),
                after=update["after"]))
    ends = [e for e in events if e["kind"] == "frame_end"]
    require(len(ends) == 1 and len(stages) == 3, "incomplete observed frame")
    end = ends[0]
    return dict(
        source_frame=raw["source_frame"],
        best_raw=dict(row=best, score=raw["detection_scores"][best - 1],
                      iou_to_reference=overlaps[best - 1],
                      accepted_by=[t for t, d, _ in accepted if d == best],
                      spawned_ids=[t["track_id"] for e in events if e["kind"] == "_spawn"
                                   and e["detection_row"] == best for t in e["created"]]),
        best_raw_stage_membership=[dict(
            stage=s["stage"], offered=best in s["detection_rows"],
            target_tracks_present=[t["track_id"] for t in s["tracks"]
                                   if t["track_id"] in target_ids]) for s in stages],
        actual_best_raw_target_pairs=pair_checks, target_updates=updates,
        target_tracks_at_end=[t for t in end["tracks"] if t["track_id"] in target_ids],
        public_target_ids=[t for t in end["public_ids"] if t in target_ids])


def summarize(contents):
    summary = json.loads(contents["summary.json"])
    require(summary["exact_raw_and_scored_parity"] is True
            and summary["exact_failures_parity"] is True, "unverified replay")
    selected = summary["selected"]
    first, last = selected["source_window"]
    by_frame = {}
    for line in contents["events.jsonl"].splitlines():
        e = json.loads(line)
        by_frame.setdefault(e["source_frame"], []).append(e)
    require(set(by_frame) == set(range(first, last + 1)), "trace window mismatch")
    rows = [json.loads(line) for line in contents["raw.jsonl"].splitlines()]
    require([r["source_frame"] for r in rows] == list(range(1, summary["frame_count"] + 1)),
            "incomplete raw frame stream")
    return dict(
        schema="visiontrack.mot17-first-switch-notes/v1", selected=selected,
        frames=[frame_notes(row, by_frame[row["source_frame"]], selected["event"])
                for row in rows if first <= row["source_frame"] <= last],
        tracker_executed=False, gate_recomputed=False, physical_identity_established=False,
        counterfactual_improvement_tested=False, visual_cause_established=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), "new notes file required")
    manifest = args.trace / "manifest.json"
    require(not manifest.is_symlink() and sha(manifest) == TRACE_MANIFEST, "trace manifest changed")
    inventory, contents = json.loads(manifest.read_text()), {}
    for name, receipt in inventory.items():
        path = args.trace / name
        require(path.parent == args.trace and path.is_file() and not path.is_symlink(),
                "invalid trace member")
        raw = path.read_bytes()
        require(len(raw) == receipt["bytes"]
                and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                f"trace member changed: {name}")
        contents[name] = raw
    result = summarize(contents)
    result.update(trace_manifest_sha256=TRACE_MANIFEST, extractor_sha256=sha(Path(__file__)))
    write_json(args.output, result)
    print(f"Wrote {len(result['frames'])} same-event frame notes to {args.output}")


if __name__ == "__main__":
    main()
