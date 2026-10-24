"""Versioned saved-output coverage with corrected correspondence and MOT17 policy.

No tracker, candidate, pixels or historical rewrite. Geometry is descriptive,
never a causal diagnosis or a recoverable-accuracy budget.
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
from experiments.mot17_case_coverage import BASELINE_MANIFEST, GROUPS, frame_diagnosis, read_bundle
from experiments.mot17_case_intake import require
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.eval.mot import MotAccumulator
from visiontrack.eval.mot17 import MOT17_PREPROCESSING

RESCORE_MANIFEST = "87403372f0a9158da83b4b8dddacb2c6b244db0a08ea7cc92bfb9ac5084a8e4a"


def read_packet(path, expected):
    require(not path.is_symlink(), "packet directory must not be a symlink")
    require(not (path / "manifest.json").is_symlink(), "manifest must not be a symlink")
    require(sha(path / "manifest.json") == expected, "packet manifest fingerprint mismatch")
    manifest = json.loads((path / "manifest.json").read_bytes())
    contents = {}
    for name, record in manifest.items():
        require(Path(name).name == name, "flat packet names required")
        file = path / name
        require(file.is_file() and not file.is_symlink(), "invalid packet member")
        payload = file.read_bytes()
        require(len(payload) == record["bytes"] and
                hashlib.sha256(payload).hexdigest() == record["sha256"],
                f"packet member changed: {name}")
        contents[name] = payload
    return contents


def analyze(contents, rescore, emit):
    require(json.loads(rescore["method.json"])["evaluator"] == EVALUATOR,
            "v2 metric receipt required")
    reference_check = json.loads(rescore["reference-check.json"])
    require(reference_check["all_reported_checks_agree"] and reference_check["num_checks"] == 45,
            "passing independent metric receipt required")
    failures = [json.loads(line) for line in rescore["failures.jsonl"].splitlines()]
    by_frame = {}
    for event in failures:
        by_frame.setdefault(event["source_frame"], []).append(event)
    plan = json.loads(contents["plan.json"])
    raw = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    scored = [json.loads(line) for line in contents["run-1/scored.jsonl"].splitlines()]
    require(len(raw) == len(scored) == plan["scope"]["source_frames"][1],
            "complete saved sequence required")
    require(plan["scope"]["source_frames"][0] == 1, "cold-start frame convention required")
    require(set(by_frame) <= set(range(1, len(raw) + 1)), "failure outside frame range")
    first_switch = next((f for f in failures if f["event_type"] == "id_switch"), None)
    accumulator = MotAccumulator()
    groups, totals = Counter({g: 0 for g in GROUPS}), Counter()
    pools, context, miss_keys = {}, [], set()
    for frame, (r, s) in enumerate(zip(raw, scored, strict=True), start=1):
        require(r["source_frame"] == s["source_frame"] == frame, "frame order mismatch")
        pairs = (np.asarray(s["gt_ids"], dtype=np.int64),
                 np.asarray(s["gt_xyxy"], dtype=float).reshape(-1, 4),
                 np.asarray(s["track_ids"], dtype=np.int64),
                 np.asarray(s["track_xyxy"], dtype=float).reshape(-1, 4))
        canonical = [dict(source_frame=frame, **asdict(f)) for f in accumulator.update(*pairs)]
        saved = by_frame.get(frame, [])
        require(encoded(canonical) == encoded(saved), "v2 canonical failure mismatch")
        # Shared geometric helper, now running explicit current default MOT17 v2.
        # It checks saved public preprocessing and reprocesses each raw score pool.
        result = frame_diagnosis(r, s, saved, plan["tracker_config"])
        for miss in result["misses"]:
            emit(miss)
            groups[miss["group"]] += 1
            miss_keys.add((frame, miss["gt_id"]))
            if first_switch and miss["gt_id"] == first_switch["gt_id"] and \
                    first_switch["source_frame"] - 3 <= frame <= first_switch["source_frame"] + 3:
                context.append(miss)
        for name, stats in result["pools"].items():
            pools.setdefault(name, Counter()).update(stats)
        totals.update({k: v for k, v in result.items() if k not in ("misses", "pools")})
        if frame % 250 == 0:
            print(f"v2 coverage: saved frame {frame}/{len(raw)}", flush=True)
    metrics = accumulator.result().as_dict()
    score = json.loads(rescore["score.json"])["metrics"]
    require(all(score[k] == value for k, value in metrics.items()), "v2 CLEAR score mismatch")
    require(sum(groups.values()) == metrics["FN"] == len(miss_keys), "FN partition mismatch")
    historical = [json.loads(line) for line in contents["run-1/failures.jsonl"].splitlines()]
    old_keys = {(f["source_frame"], f["gt_id"]) for f in historical if f["event_type"] == "miss"}
    return dict(
        schema="visiontrack.mot17-case-coverage/v2", evaluator=EVALUATOR,
        preprocessing=MOT17_PREPROCESSING, baseline_manifest_sha256=BASELINE_MANIFEST,
        metric_rescore_manifest_sha256=RESCORE_MANIFEST, metrics=metrics,
        fn_groups=dict(groups), pools={k: dict(v) for k, v in pools.items()},
        other_checks=dict(totals), first_switch_misses_in_fixed_context=context,
        miss_correspondence=dict(added=sorted(miss_keys - old_keys),
                                 removed=sorted(old_keys - miss_keys),
                                 unchanged=len(old_keys & miss_keys)),
        tracker_executed=False, images_read=False, causal_attribution=False,
        raw_box_capacity_is_tracker_recall_ceiling=False, independent_visual_review=False,
        historical_records_rewritten=False)


def execute(baseline, rescore_path, preprocessing_path, preprocessing_digest, output):
    require(not output.exists() and not output.is_symlink(), "new output required")
    contents = read_bundle(baseline)
    rescore = read_packet(rescore_path, RESCORE_MANIFEST)
    preprocessing = read_packet(preprocessing_path, preprocessing_digest)
    checked = json.loads(preprocessing["summary.json"])
    require(checked["all_frames_agree"] and checked["frames"] == 1050 and
            checked["preprocessing"] == MOT17_PREPROCESSING, "passing v2 preprocessing required")
    require(preprocessing["reference-scored.jsonl"] == contents["run-1/scored.jsonl"],
            "preprocessing receipt does not cover these exact scored inputs")
    prep_method = json.loads(preprocessing["method.json"])
    require(prep_method["baseline_manifest_sha256"] == BASELINE_MANIFEST,
            "preprocessing receipt baseline mismatch")
    root = Path(__file__).resolve().parents[1]
    paths = [Path(__file__).resolve(), root / "experiments/mot17_case_coverage.py"]
    paths += sorted((root / "src/visiontrack").rglob("*.py"))
    hashes = {str(p): sha(p) for p in paths}
    original = json.loads(contents["plan.json"])["code"]["source_sha256"]
    unchanged = {n: d for n, d in original.items() if n.startswith(tuple(
        f"src/visiontrack/{part}/" for part in ("tracking", "core", "datasets", "detection")))}

    def guard():
        require(read_bundle(baseline) == contents, "historical baseline changed")
        require(read_packet(rescore_path, RESCORE_MANIFEST) == rescore, "v2 receipt changed")
        require(read_packet(preprocessing_path, preprocessing_digest) == preprocessing,
                "preprocessing receipt changed")
        for name, digest in hashes.items():
            require(sha(Path(name)) == digest, f"coverage source changed: {name}")
        for name, digest in prep_method["source_sha256"].items():
            require(sha(Path(name)) == digest, "verified preprocessing source changed")
        for name, digest in unchanged.items():
            require(sha(root / name) == digest, "tracker/input implementation changed")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.mot17-coverage-method/v2", evaluator=EVALUATOR,
        preprocessing=MOT17_PREPROCESSING, source_sha256=hashes,
        baseline_manifest_sha256=BASELINE_MANIFEST, rescore_manifest_sha256=RESCORE_MANIFEST,
        preprocessing_manifest_sha256=preprocessing_digest, unchanged_tracker_sha256=unchanged,
        frames=[1, 1050], thresholds="IoU >=0.5; original low/high/spawn scores",
        fn_group_order=GROUPS, unique_assignment="maximum valid-edge cardinality",
        policy="post-baseline descriptive partition, no tracker, pixels or tuning; "
               "not an achievable recall budget; legacy packets untouched"))
    with (output / "misses.jsonl").open("x") as stream:
        result = analyze(contents, rescore, lambda r: stream.write(encoded(r)))
    guard()
    write_json(output / "summary.json", result)
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "rescore", "preprocessing-check", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--preprocessing-manifest-sha256", required=True)
    args = parser.parse_args()
    execute(args.baseline, args.rescore, args.preprocessing_check,
            args.preprocessing_manifest_sha256, args.output)


if __name__ == "__main__":
    main()
