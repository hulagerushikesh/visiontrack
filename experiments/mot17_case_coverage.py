"""Read-only geometry/score diagnosis of the pinned saved baseline, not a tracker.

Pointwise FN groups are descriptive, not causal. Unique raw-box assignment
capacity is not achievable tracker recall: filtering can change geometry.
No detections, tracker configuration, baseline files or pixels are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_intake import require
from visiontrack.core.assignment import linear_assignment
from visiontrack.core.geometry import iou_matrix
from visiontrack.eval.mot import MotAccumulator
from visiontrack.eval.mot17 import preprocess_frame

BASELINE_MANIFEST = "4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8"
GROUPS = ("no_raw_geometric_neighbor", "only_subthreshold_neighbors",
          "eligible_neighbors_removed_by_ignore", "eligible_neighbor_without_scored_match")
RUN_FILES = ("raw.jsonl", "scored.jsonl", "failures.jsonl", "summary.json")


def maximum_cardinality(ious):
    """Maximum number of disjoint >=0.5 edges; no identity/IoU tie claims.

    A complete rectangular assignment with cost -1 for a valid edge and 0
    otherwise maximizes the number of valid edges; discard the invalid fillers.
    Unlike maximizing IoU then thresholding, this cannot sacrifice cardinality.
    """
    require(ious.ndim == 2 and bool(np.isfinite(ious).all()), "invalid IoU matrix")
    require(bool(((ious >= 0) & (ious <= 1)).all()), "IoU outside [0,1]")
    valid = ious >= 0.5
    rows, columns = linear_assignment(-valid.astype(np.float64))
    return int(valid[rows, columns].sum())


def geometry(gt, boxes):
    return iou_matrix(gt, np.asarray(boxes, dtype=np.float64).reshape(-1, 4))


def best(ious):
    # IoU cannot be negative; 0 is the actual empty-neighbour maximum here.
    return ious.max(axis=1) if ious.shape[1] else np.zeros(ious.shape[0])


def frame_diagnosis(raw, scored, failures, config):
    ids = np.array(raw["gt_ids"], dtype=np.int64)
    gt = np.array(raw["gt_xyxy"], dtype=np.float64).reshape(-1, 4)
    classes, consider = np.array(raw["gt_classes"]), np.array(raw["gt_consider"])
    scoring = (classes == 1) & (consider >= 1)
    score_ids, score_gt = ids[scoring], gt[scoring]
    det = np.array(raw["detections_xyxy"], dtype=np.float64).reshape(-1, 4)
    scores = np.array(raw["detection_scores"], dtype=np.float64)
    public = np.array(raw["track_xyxy"], dtype=np.float64).reshape(-1, 4)
    public_ids = np.array(raw["track_ids"], dtype=np.int64)
    actual = preprocess_frame(gt, ids, classes, consider, public, public_ids)
    expected = (scored["gt_ids"], scored["gt_xyxy"], scored["track_ids"], scored["track_xyxy"])
    require(all(np.array_equal(a, np.array(b).reshape(a.shape))
                for a, b in zip(actual, expected, strict=True)), "saved preprocessing mismatch")
    missed_ids = {f["gt_id"] for f in failures if f["event_type"] == "miss"}
    require(missed_ids <= set(score_ids.tolist()), "miss outside scoring reference")
    missed = np.array([int(g) in missed_ids for g in score_ids], dtype=bool)
    raw_iou = geometry(score_gt, det)
    raw_best = best(raw_iou)
    eligible_iou = raw_iou[:, scores >= config["low_score_thresh"]]
    pool_stats, pool_ious = {}, {}
    thresholds = dict(all_scores=None, eligible=config["low_score_thresh"],
                      high=config["high_score_thresh"], spawn_score=config["new_track_thresh"])
    for name, threshold in thresholds.items():
        selected = np.ones(len(det), dtype=bool) if threshold is None else scores >= threshold
        # Ordinals are frame-local detection row handles, NOT person identities.
        ordinals = np.flatnonzero(selected) + 1
        _, _, kept_ids, kept = preprocess_frame(
            gt, ids, classes, consider, det[selected], ordinals)
        ious = geometry(score_gt, kept)
        pool_ious[name] = ious
        pool_stats[name] = dict(
            input_boxes=int(selected.sum()), kept_boxes=len(kept_ids),
            ignore_removed=int(selected.sum()) - len(kept_ids),
            pointwise_gt_neighbors=int((best(ious) >= 0.5).sum()),
            unique_gt_capacity=maximum_cardinality(ious),
            pointwise_fn_neighbors=int((best(ious)[missed] >= 0.5).sum()),
            fn_only_unique_capacity=maximum_cardinality(ious[missed]),
        )
    eligible_best, kept_best = best(eligible_iou), best(pool_ious["eligible"])
    public_best = best(geometry(score_gt, actual[3]))
    rows = []
    for i in np.flatnonzero(missed):
        if raw_best[i] < 0.5:
            group = GROUPS[0]
        elif eligible_best[i] < 0.5:
            group = GROUPS[1]
        elif kept_best[i] < 0.5:
            group = GROUPS[2]
        else:
            group = GROUPS[3]
        rows.append(dict(
            source_frame=raw["source_frame"], gt_id=int(score_ids[i]), group=group,
            best_raw_iou=float(raw_best[i]), best_eligible_iou=float(eligible_best[i]),
            best_kept_eligible_iou=float(kept_best[i]),
            best_scored_output_iou=float(public_best[i]),
            raw_geometric_neighbors=int((raw_iou[i] >= 0.5).sum()),
        ))
    return dict(
        misses=rows, pools=pool_stats, scoring_boxes=len(score_ids),
        matched_without_raw_neighbor=int(((~missed) & (raw_best < 0.5)).sum()),
        matched_without_kept_eligible_neighbor=int(((~missed) & (kept_best < 0.5)).sum()),
        fn_with_scored_output_neighbor=int((public_best[missed] >= 0.5).sum()),
    )


def read_bundle(path, expected_sha=BASELINE_MANIFEST):
    manifest_path = path / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "invalid manifest")
    require(sha(manifest_path) == expected_sha, "baseline manifest fingerprint mismatch")
    manifest = json.loads(manifest_path.read_text())
    names = {f"run-{i}/{n}" for i in (1, 2) for n in RUN_FILES}
    names |= {"plan.json", "repeatability.json", "first-switch.json"}
    require(set(manifest["files"]) == names, "unexpected baseline inventory")
    contents = {}
    for name in sorted(names):
        file = path / name
        require(file.is_file() and not file.is_symlink() and not file.parent.is_symlink(),
                "invalid baseline member")
        raw = file.read_bytes()
        record = manifest["files"][name]
        require(len(raw) == record["bytes"] and hashlib.sha256(raw).hexdigest() == record["sha256"],
                f"baseline member changed: {name}")
        contents[name] = raw
    for name in RUN_FILES:
        require(contents[f"run-1/{name}"] == contents[f"run-2/{name}"], "baseline runs differ")
    return contents


def analyze(contents, emit):
    plan = json.loads(contents["plan.json"])
    config = plan["tracker_config"]
    first, last = plan["scope"]["source_frames"]
    require(first == 1, "cold-start frame convention required")
    reference = json.loads(contents["run-1/summary.json"])
    raw_rows = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    scored_rows = [json.loads(line) for line in contents["run-1/scored.jsonl"].splitlines()]
    failures = [json.loads(line) for line in contents["run-1/failures.jsonl"].splitlines()]
    by_frame = {}
    for row in failures:
        by_frame.setdefault(row["source_frame"], []).append(row)
    require(len(raw_rows) == len(scored_rows) == last, "incomplete saved frames")
    require(set(by_frame) <= set(range(1, last + 1)), "failure outside source range")
    accumulator = MotAccumulator(iou_threshold=0.5)
    groups, pools, totals, context = Counter({g: 0 for g in GROUPS}), {}, Counter(), []
    event = reference["first_chronological_switch"]
    for frame, (raw, scored) in enumerate(zip(raw_rows, scored_rows, strict=True), start=1):
        require(raw["source_frame"] == scored["source_frame"] == frame, "frame order mismatch")
        pairs = (np.array(scored["gt_ids"], dtype=np.int64),
                 np.array(scored["gt_xyxy"]).reshape(-1, 4),
                 np.array(scored["track_ids"], dtype=np.int64),
                 np.array(scored["track_xyxy"]).reshape(-1, 4))
        canonical = [dict(source_frame=frame, **asdict(f)) for f in accumulator.update(*pairs)]
        saved = by_frame.get(frame, [])
        require(encoded(canonical) == encoded(saved), "saved canonical failures mismatch")
        result = frame_diagnosis(raw, scored, saved, config)
        for row in result["misses"]:
            emit(row)
            groups[row["group"]] += 1
            if event and row["gt_id"] == event["gt_id"] and \
                    event["source_frame"] - 3 <= frame <= event["source_frame"] + 3:
                context.append(row)
        for name, stats in result["pools"].items():
            pools.setdefault(name, Counter()).update(stats)
        totals.update({key: value for key, value in result.items()
                       if key not in ("misses", "pools")})
        if frame % 250 == 0:
            print(f"diagnosed saved frame {frame}/{last}", flush=True)
    metrics = accumulator.result().as_dict()
    require(all(reference["metrics"][key] == value for key, value in metrics.items()),
            "saved CLEAR metrics mismatch")
    require(sum(groups.values()) == metrics["FN"], "FN partition mismatch")
    return dict(
        schema="visiontrack.mot17-case-coverage/v1", baseline_manifest_sha256=BASELINE_MANIFEST,
        metrics=metrics, fn_groups=dict(groups), pools={k: dict(v) for k, v in pools.items()},
        other_checks=dict(totals), first_switch_misses_in_fixed_context=context,
        tracker_executed=False, images_read=False, causal_attribution=False,
        raw_box_capacity_is_tracker_recall_ceiling=False, independent_visual_review=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), "new output required")
    contents = read_bundle(args.baseline)
    source_hashes = json.loads(contents["plan.json"])["code"]["source_sha256"]
    root = Path(__file__).resolve().parents[1]
    for name, digest in source_hashes.items():
        require(sha(root / name) == digest, f"baseline implementation changed: {name}")
    analysis_sha = sha(Path(__file__))
    args.output.mkdir()
    write_json(args.output / "method.json", dict(
        baseline_manifest_sha256=BASELINE_MANIFEST, analysis_sha256=analysis_sha,
        baseline_implementation_matches=True,
        thresholds="IoU >=0.5 inclusive; saved default low/high/spawn scores",
        fn_group_order=GROUPS, unique_assignment="maximum valid-edge cardinality",
        restrictions="descriptive post-baseline diagnostic, no causal or improvement claim",
    ))
    with (args.output / "misses.jsonl").open("x") as stream:
        summary = analyze(contents, lambda row: stream.write(encoded(row)))
    require(read_bundle(args.baseline) == contents, "baseline changed during diagnosis")
    for name, digest in source_hashes.items():
        require(sha(root / name) == digest, f"baseline implementation changed: {name}")
    require(sha(Path(__file__)) == analysis_sha, "analysis changed during diagnosis")
    write_json(args.output / "summary.json", summary)
    write_json(args.output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(args.output.iterdir()) if p.is_file()
    })
    print(encoded(summary), flush=True)


if __name__ == "__main__":
    main()
