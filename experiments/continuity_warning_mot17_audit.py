"""Read-only scalar audit of saved MOT17 warning replay and triage arithmetic."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.continuity_warning_audit import audit_frame
from experiments.continuity_warning_mot17 import (
    EVENT_TYPES,
    FRAME_COUNT,
    ROOT,
    check_frame_input,
    check_frame_output,
    validated_inputs,
)
from experiments.mot17_case_baseline import sha, write_json
from experiments.mot17_case_intake import require
from experiments.traffic_runner import _git
from visiontrack.datasets.cache import CachedSequence
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def verified_study(path: Path) -> tuple[dict, dict, list[dict]]:
    require(path.is_dir() and not path.is_symlink(), "regular study directory required")
    manifest_path = path / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(),
            "regular success manifest required")
    manifest = json.loads(manifest_path.read_text())
    require(set(manifest) == {"method.json", "summary.json", "warnings.jsonl"} and
            {p.name for p in path.iterdir()} == set(manifest) | {"manifest.json"},
            "study inventory mismatch")
    for name, record in manifest.items():
        member = path / name
        require(member.is_file() and not member.is_symlink(), "invalid study member")
        require(member.stat().st_size == record["bytes"] and
                sha(member) == record["sha256"], f"study member drift: {name}")
    method = json.loads((path / "method.json").read_text())
    summary = json.loads((path / "summary.json").read_text())
    warnings = [json.loads(line) for line in (path / "warnings.jsonl").open()]
    require(method["frame_range"] == [1, FRAME_COUNT] and
            method["warning_window_after"] == 2 and len(warnings) == FRAME_COUNT,
            "study method or coverage mismatch")
    revision = method["committed"]["revision"]
    for name, digest in method["committed"]["sources"].items():
        require(hashlib.sha256(_git(ROOT, "show", f"{revision}:{name}")).hexdigest() == digest,
                f"frozen source fingerprint mismatch: {name}")
    return method, summary, warnings


def check_summary_independently(summary: dict, warnings: list[dict], failures: list[dict]) -> None:
    positive = [r["source_frame"] for r in warnings if r["warnings"]]
    require(summary["warning_frames"] == positive and
            summary["warning_frame_count"] == len(positive) and
            summary["warning_component_count"] == sum(len(r["warnings"]) for r in warnings),
            "warning total mismatch")
    intervals = []
    for frame in positive:
        last = min(frame + 2, FRAME_COUNT)
        if intervals and frame <= intervals[-1][1] + 1:
            intervals[-1][1] = max(intervals[-1][1], last)
        else:
            intervals.append([frame, last])
    covered_frames = set()
    for first, last in intervals:
        covered_frames.update(range(first, last + 1))
    require(summary["review_windows"] == intervals and
            summary["review_task_count"] == len(intervals) and
            summary["review_frame_count"] == len(covered_frames) and
            summary["review_frame_fraction"] == len(covered_frames) / FRAME_COUNT,
            "review burden mismatch")
    require(summary["assessment_opportunity_frames"] ==
            sum(bool(r["assessment_opportunity"]) for r in warnings) and
            summary["two_supported_previous_track_frames"] ==
            sum(bool(r["two_supported_previous_tracks"]) for r in warnings),
            "assessment opportunity mismatch")
    for kind in EVENT_TYPES:
        events = [e for e in failures if e["event_type"] == kind]
        frames = {e["source_frame"] for e in events}
        actual = summary["events"][kind]
        counts = dict(count=len(events), unique_frames=len(frames),
                      covered_count=sum(e["source_frame"] in covered_frames for e in events),
                      missed_count=sum(e["source_frame"] not in covered_frames for e in events),
                      covered_unique_frames=len(frames & covered_frames),
                      review_tasks_with_event=sum(any(a <= f <= b for f in frames)
                                                  for a, b in intervals),
                      review_tasks_without_event=sum(not any(a <= f <= b for f in frames)
                                                     for a, b in intervals))
        require(all(actual[k] == v for k, v in counts.items()),
                f"triage event arithmetic mismatch: {kind}")
        expected_covered = [dict(source_frame=e["source_frame"], gt_id=e["gt_id"],
                                 hyp_id=e["hyp_id"])
                            for e in events if e["source_frame"] in covered_frames]
        require(actual["covered_events"] == expected_covered,
                f"triage covered-event records mismatch: {kind}")


def execute(study: Path, cache: Path, labels: Path, baseline: Path,
            rescore: Path, output: Path) -> dict:
    require(not output.exists() and not output.is_symlink(), "new audit file required")
    require(output.parent.is_dir() and not output.resolve().is_relative_to(ROOT) and
            not output.resolve().is_relative_to(ROOT.parent / "visiontrack-cpp"),
            "audit output must be outside both repositories")
    method, summary, warnings = verified_study(study)
    _, _, intake, raw, failures, _ = validated_inputs(cache, labels, baseline, rescore)
    require(method["cache_and_labels"] == intake["input_sha256"],
            "study intake fingerprint mismatch")
    seq = CachedSequence(cache)
    tracker = ByteTracker(TrackerConfig())
    previous = []
    components = 0
    for source_frame, (saved, warning) in enumerate(zip(raw, warnings, strict=True), start=1):
        detections = seq.frame(source_frame).detections()
        check_frame_input(source_frame, detections, saved)
        rows = [dict(xyxy=det.xyxy.tolist(), score=float(det.score), class_id=det.class_id)
                for det in detections]
        require(warning["source_frame"] == source_frame and
                warning["frame"] == source_frame - 1, "warning frame drift")
        audit_frame(source_frame - 1, previous, rows, warning)
        observations = tracker.update(detections)
        check_frame_output(source_frame, observations, saved)
        previous = sorted((dict(frame=source_frame - 1, track_id=int(obs.track_id),
                                xyxy=obs.xyxy.tolist(), score=float(obs.score),
                                class_id=int(obs.class_id)) for obs in observations),
                          key=lambda row: row["track_id"])
        components += len(warning["components"])
    check_summary_independently(summary, warnings, failures)
    report = dict(schema="visiontrack.continuity-warning-mot17-audit/v1",
                  study_manifest_sha256=sha(study / "manifest.json"),
                  frames_checked=FRAME_COUNT, components_checked=components,
                  warning_frames_checked=summary["warning_frame_count"],
                  corrected_events_checked=dict(Counter(e["event_type"] for e in failures)),
                  complete_saved_record_and_scalar_geometry_check=True,
                  tracker_public_outputs_match_sealed_baseline=True,
                  triage_arithmetic_checked=True, independent_physical_labels=False,
                  untouched_validation=False)
    write_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "cache", "labels", "baseline", "rescore", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.study, args.cache, args.labels, args.baseline,
                             args.rescore, args.output), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
