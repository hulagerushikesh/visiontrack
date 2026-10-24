"""Versioned v2 re-score of unchanged saved outputs, never a tracker rerun.

Retains old/new failure deltas and an independently computed reference check.
The original v1 baseline, public outputs and studies are never overwritten.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import require
from experiments.mot17_metric_crosscheck import crosscheck, reference_api
from visiontrack.eval.definitions import EVALUATOR, LEGACY_EVALUATOR
from visiontrack.eval.hota import compute_hota, compute_identity
from visiontrack.eval.mot import MotAccumulator


def rescore(contents, emit):
    import numpy as np

    accumulator, frames, failures = MotAccumulator(iou_threshold=0.5), [], []
    for frame, line in enumerate(contents["run-1/scored.jsonl"].splitlines(), start=1):
        row = json.loads(line)
        require(row["source_frame"] == frame, "non-contiguous saved scored frames")
        pairs = (np.array(row["gt_ids"], dtype=np.int64),
                 np.array(row["gt_xyxy"], dtype=np.float64).reshape(-1, 4),
                 np.array(row["track_ids"], dtype=np.int64),
                 np.array(row["track_xyxy"], dtype=np.float64).reshape(-1, 4))
        frames.append(pairs)
        for event in accumulator.update(*pairs):
            record = dict(source_frame=frame, **asdict(event))
            failures.append(record)
            emit(record)
    hota, identity, clear = compute_hota(frames), compute_identity(frames), accumulator.result()
    hota_values = asdict(hota)
    hota_values["per_alpha"] = hota.per_alpha.tolist()
    summary = dict(metrics={**clear.as_dict(), **identity.as_dict(), **hota.as_dict()},
                   unrounded=dict(clear=asdict(clear), identity=asdict(identity), hota=hota_values))
    historical = [json.loads(line) for line in contents["run-1/failures.jsonl"].splitlines()]

    def key(row):
        return (row["event_type"], row["source_frame"], row["gt_id"],
                row["hyp_id"], row["previous_hyp_id"])

    old, new = {key(r) for r in historical}, {key(r) for r in failures}
    added = [r for r in failures if key(r) not in old]
    removed = [r for r in historical if key(r) not in new]
    changes = dict(
        old_evaluator=LEGACY_EVALUATOR, new_evaluator=EVALUATOR,
        old_counts=dict(Counter(r["event_type"] for r in historical)),
        new_counts=dict(Counter(r["event_type"] for r in failures)),
        added_events=added, removed_events=removed,
        new_first_switch=next((r for r in failures if r["event_type"] == "id_switch"), None),
        delta_key="event type, source frame, GT, current and previous hypothesis",
        historical_records_rewritten=False)
    return summary, changes


def execute(baseline, output):
    require(not output.exists() and not output.is_symlink(), "new output required")
    contents = read_bundle(baseline)
    root = Path(__file__).resolve().parents[1]
    original = json.loads(contents["plan.json"])["code"]["source_sha256"]
    tracker_inputs = {name: digest for name, digest in original.items() if name.startswith(tuple(
        f"src/visiontrack/{part}/" for part in ("tracking", "core", "datasets", "detection")))}
    te, box_iou, aliases = reference_api()
    te_root = Path(te.__file__).resolve().parent
    paths = sorted((root / "src/visiontrack/eval").glob("*.py"))
    paths += [Path(__file__).resolve(), root / "experiments/mot17_metric_crosscheck.py"]
    paths += sorted(te_root.rglob("*.py"))
    hashes = {str(p): sha(p) for p in paths}

    def guard():
        require(read_bundle(baseline) == contents, "original baseline changed")
        for name, digest in tracker_inputs.items():
            require(sha(root / name) == digest, f"tracker/input implementation changed: {name}")
        for name, digest in hashes.items():
            require(sha(Path(name)) == digest, "evaluator/reference source changed")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.metric-rescore/v2", evaluator=EVALUATOR,
        original_baseline_manifest_sha256=BASELINE_MANIFEST, source_sha256=hashes,
        tracker_input_sha256=tracker_inputs, frames=[1, 1050],
        policy="rescore unchanged saved scored pairs; no tracker, preprocessing change or tuning",
        equivalence=dict(integer_tolerance=0, float_tolerance=1e-10, checks=45),
        numpy_compatibility_aliases=aliases,
        environment=dict(python=sys.version, platform=platform.platform())))
    with (output / "failures.jsonl").open("x") as stream:
        summary, changes = rescore(contents, lambda r: stream.write(encoded(r)))
    write_json(output / "score.json", summary)
    write_json(output / "event-changes.json", changes)
    # Substitute only the in-memory comparison target, never the historical file.
    comparison_input = dict(contents)
    comparison_input["run-1/summary.json"] = encoded(summary).encode()
    checked = crosscheck(comparison_input, te, box_iou)
    write_json(output / "reference-check.json", checked)
    guard()
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded(dict(output=str(output), metrics=summary["metrics"],
                       reference_agrees=checked["all_reported_checks_agree"],
                       new_first_switch=changes["new_first_switch"])), flush=True)
    return checked["all_reported_checks_agree"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.baseline, args.output) else 2)


if __name__ == "__main__":
    main()
