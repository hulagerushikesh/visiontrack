"""Two fresh unchanged runs of the admitted MOT17 annotation-only case.

Writes only a new explicitly selected directory. No images, tuning or candidate.
Retains inputs, public outputs, scored pairs, canonical failures and full metrics.
This is repeatability within our implementation, not independent validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.mot17_case_intake import audit, require
from visiontrack.datasets.cache import CachedSequence
from visiontrack.eval.hota import compute_hota, compute_identity
from visiontrack.eval.mot import MotAccumulator
from visiontrack.eval.mot17 import preprocess_frame
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"


def write_json(path, value):
    with path.open("x") as stream:
        stream.write(encoded(value))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_record(frame, pairs):
    return dict(source_frame=frame, gt_ids=pairs[0].tolist(), gt_xyxy=pairs[1].tolist(),
                track_ids=pairs[2].tolist(), track_xyxy=pairs[3].tolist())


def run_once(seq, directory):
    """One cold-start pass; the canonical accumulator selects the first switch."""
    directory.mkdir()  # do not overwrite or merge an earlier attempt
    tracker = ByteTracker(TrackerConfig())
    accumulator = MotAccumulator(iou_threshold=0.5)
    frames, first_switch, raw_count, scored_count = [], None, 0, 0
    with (directory / "raw.jsonl").open("x") as raw, \
            (directory / "scored.jsonl").open("x") as scored, \
            (directory / "failures.jsonl").open("x") as failures:
        for expected, fd in enumerate(seq.iter_range(1, seq.length), start=1):
            require(fd.frame == expected, "non-contiguous source frame")
            require(fd.det_features is None, "appearance input is not admitted")
            observations = tracker.update(fd.detections())
            ids = np.array([o.track_id for o in observations], dtype=np.int64)
            boxes = np.array([o.xyxy for o in observations], dtype=np.float64).reshape(-1, 4)
            raw.write(encoded(dict(
                source_frame=fd.frame, detections_xyxy=fd.det_xyxy.tolist(),
                detection_scores=fd.det_scores.tolist(),
                gt_ids=fd.gt_ids.tolist(), gt_xyxy=fd.gt_xyxy.tolist(),
                gt_classes=fd.gt_classes.tolist(), gt_consider=fd.gt_conf.tolist(),
                gt_visibility=fd.gt_vis.tolist(), track_ids=ids.tolist(), track_xyxy=boxes.tolist(),
            )))
            pairs = preprocess_frame(fd.gt_xyxy, fd.gt_ids, fd.gt_classes, fd.gt_conf, boxes, ids)
            frames.append(pairs)
            scored.write(encoded(pair_record(fd.frame, pairs)))
            raw_count += len(ids)
            scored_count += len(pairs[2])
            for event in accumulator.update(*pairs):
                row = dict(source_frame=fd.frame, **asdict(event))
                failures.write(encoded(row))
                if first_switch is None and event.event_type == "id_switch":
                    first_switch = row
            if fd.frame % 250 == 0:
                print(f"{directory.name}: tracked {fd.frame}/{seq.length}", flush=True)
    require(len(frames) == seq.length, "incomplete source traversal")
    print(f"{directory.name}: scoring identity and HOTA", flush=True)
    clear = accumulator.result()
    identity, hota = compute_identity(frames), compute_hota(frames)
    full_hota = asdict(hota)
    full_hota["per_alpha"] = hota.per_alpha.tolist()
    summary = dict(
        metrics={**clear.as_dict(), **identity.as_dict(), **hota.as_dict()},
        unrounded=dict(clear=asdict(clear), identity=asdict(identity), hota=full_hota),
        raw_public_boxes=raw_count, scored_public_boxes=scored_count,
        removed_by_ignore_preprocessing=raw_count - scored_count,
        first_chronological_switch=first_switch,
    )
    write_json(directory / "summary.json", summary)
    return summary


def first_switch_context(directory, event, length):
    """Retain the fixed +/-3 frame window, without replay or outcome hunting."""
    if event is None:
        return dict(event=None, window=[], reason="no scored identity switch")
    first, last = max(1, event["source_frame"] - 3), min(length, event["source_frame"] + 3)
    rows = []
    with (directory / "raw.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if first <= row["source_frame"] <= last:
                rows.append(row)
    require([r["source_frame"] for r in rows] == list(range(first, last + 1)),
            "incomplete first-switch context")
    return dict(event=event, window=[first, last], frames=rows,
                visual_cause_established=False, independent_label_review=False)


def code_identity():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "src" / "visiontrack").rglob("*.py"))
    paths += [Path(__file__).resolve(), root / "experiments/mot17_case_intake.py"]
    return dict(
        git_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        git_status=subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
        source_sha256={str(path.relative_to(root)): sha(path) for path in paths},
    )


def execute(cache, labels, output):
    require(not output.exists() and not output.is_symlink(), "output must be a new directory")
    intake = audit(cache, labels)
    identity = code_identity()
    output.mkdir()  # no recursive creation of unspecified parents
    plan = dict(
        schema="visiontrack.mot17-case-baseline/v1", intake=intake,
        code=identity, tracker_config=asdict(TrackerConfig()),
        environment=dict(python=sys.version, numpy=np.__version__, platform=platform.platform()),
        scope=dict(source_frames=[1, 1050], cold_start=True, fresh_runs=2,
                   embeddings=False, candidate=False, images=False, untouched_validation=False),
        preprocessing="visiontrack.eval.mot17.preprocess_frame at IoU 0.5",
        event_rule="first chronological canonical CLEAR-MOT ID switch, then +/-3 source frames",
        frame_convention="source_frame is one-based; failure frame_index is zero-based",
    )
    write_json(output / "plan.json", plan)  # before any tracker execution
    results = []
    for index in (1, 2):
        require(audit(cache, labels) == intake, "input changed before run")
        require(code_identity() == identity, "code changed before run")
        results.append(run_once(CachedSequence(cache), output / f"run-{index}"))
    require(audit(cache, labels) == intake, "input changed during run")
    require(code_identity() == identity, "code changed during run")
    comparisons = {}
    for name in ("raw.jsonl", "scored.jsonl", "failures.jsonl", "summary.json"):
        left, right = (output / "run-1" / name).read_bytes(), (output / "run-2" / name).read_bytes()
        comparisons[name] = left == right
    write_json(output / "repeatability.json", dict(exact_bytes=comparisons,
               independent_implementation=False))
    require(all(comparisons.values()), "fresh-run repeatability mismatch; retain both runs")
    context = first_switch_context(output / "run-1", results[0]["first_chronological_switch"], 1050)
    write_json(output / "first-switch.json", context)
    files = sorted(p for p in output.rglob("*") if p.is_file())
    write_json(output / "manifest.json", dict(
        schema="visiontrack.mot17-case-baseline-manifest/v1",
        files={str(p.relative_to(output)): dict(bytes=p.stat().st_size, sha256=sha(p))
               for p in files},
        repeatability="all four run artifacts byte-identical", images_read=False,
        independent_visual_review=False, improvement_tested=False,
    ))
    print(encoded(dict(output=str(output), **results[0])), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.cache, args.labels, args.output)


if __name__ == "__main__":
    main()
