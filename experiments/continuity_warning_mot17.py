"""Exploratory, complete MOT17 replay of the frozen offline continuity observer.

The known sequence is not an untouched validation set. No pixels, tuning,
alternative tracker or production warning behavior are involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.continuity_warning import ContinuityObserver
from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import audit, require
from experiments.mot17_coverage_v2 import RESCORE_MANIFEST, read_packet
from experiments.traffic_runner import _check_import_origins, _git
from visiontrack.datasets.cache import CachedSequence
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

ROOT = Path(__file__).resolve().parents[1]
METHOD_FILES = (
    "docs/CONTINUITY_WARNING_MOT17_PLAN.md",
    "experiments/continuity_warning_mot17.py",
    "tests/test_continuity_warning_mot17.py",
)
FRAME_COUNT = 1050
WINDOW_AFTER_WARNING = 2
EVENT_TYPES = ("id_switch", "fragmentation")


def committed_method() -> dict:
    """Require a clean, committed method before consulting the known outcomes."""
    _check_import_origins()
    require(_git(ROOT, "status", "--porcelain") == b"", "commit a clean method before replay")
    sources = {}
    for name in METHOD_FILES:
        path = ROOT / name
        require(not path.is_symlink(), f"symlink method source: {name}")
        payload = path.read_bytes()
        require(_git(ROOT, "show", f"HEAD:{name}") == payload,
                f"method source is not committed: {name}")
        sources[name] = hashlib.sha256(payload).hexdigest()
    return dict(revision=_git(ROOT, "rev-parse", "HEAD").decode().strip(), sources=sources)


def validated_inputs(cache: Path, labels: Path, baseline: Path, rescore: Path) -> tuple:
    original = read_bundle(baseline)
    corrected = read_packet(rescore, RESCORE_MANIFEST)
    require(set(corrected) == {"method.json", "score.json", "event-changes.json",
                                "reference-check.json", "failures.jsonl"},
            "unexpected v2 packet inventory")
    plan = json.loads(original["plan.json"])
    intake = audit(cache, labels)
    require(intake == plan["intake"], "cache/labels differ from baseline intake")
    require(plan["scope"]["source_frames"] == [1, FRAME_COUNT] and
            plan["scope"]["embeddings"] is False, "baseline scope mismatch")
    require(plan["tracker_config"] == asdict(TrackerConfig()),
            "baseline default tracker settings drifted")
    source_hashes = plan["code"]["source_sha256"]
    for name, digest in source_hashes.items():
        if name.startswith(("src/visiontrack/tracking/", "src/visiontrack/core/",
                            "src/visiontrack/detection/", "src/visiontrack/datasets/")):
            require(sha(ROOT / name) == digest, f"baseline tracker/input drift: {name}")
    method = json.loads(corrected["method.json"])
    reference = json.loads(corrected["reference-check.json"])
    require(method["original_baseline_manifest_sha256"] == BASELINE_MANIFEST and
            method["evaluator"] == EVALUATOR and method["frames"] == [1, FRAME_COUNT],
            "v2 score lineage mismatch")
    require(reference["all_reported_checks_agree"] is True and
            reference["num_checks"] == 45, "v2 metric reference check did not pass")
    raw = [json.loads(line) for line in original["run-1/raw.jsonl"].splitlines()]
    failures = [json.loads(line) for line in corrected["failures.jsonl"].splitlines()]
    metrics = json.loads(corrected["score.json"])["metrics"]
    require(len(raw) == FRAME_COUNT and
            all(row["source_frame"] == i for i, row in enumerate(raw, start=1)),
            "baseline frame coverage mismatch")
    require(all(1 <= row["source_frame"] <= FRAME_COUNT and
                row["frame_index"] == row["source_frame"] - 1 for row in failures),
            "corrected event frame mismatch")
    counts = Counter(row["event_type"] for row in failures)
    require(counts["id_switch"] == metrics["IDSW"] and
            counts["fragmentation"] == metrics["Frag"],
            "corrected event inventory mismatch")
    return original, corrected, intake, raw, failures, metrics


def check_frame_input(source_frame: int, detections: list, saved: dict) -> None:
    require(saved["source_frame"] == source_frame, "saved source frame mismatch")
    require([det.xyxy.tolist() for det in detections] == saved["detections_xyxy"] and
            [float(det.score) for det in detections] == saved["detection_scores"],
            f"saved detection drift at source frame {source_frame}")
    require(all(det.feature is None and det.class_id == 0 for det in detections),
            "unexpected appearance or class input")


def check_frame_output(source_frame: int, observations: list, saved: dict) -> None:
    require([obs.track_id for obs in observations] == saved["track_ids"] and
            [obs.xyxy.tolist() for obs in observations] == saved["track_xyxy"] and
            all(obs.frame == source_frame - 1 for obs in observations),
            f"unchanged public output mismatch at source frame {source_frame}")


def review_windows(warning_frames: list[int], count: int) -> list[list[int]]:
    """Merge inclusive, adjacent three-frame review intervals."""
    require(count >= 1 and warning_frames == sorted(set(warning_frames)) and
            all(1 <= frame <= count for frame in warning_frames), "invalid warning frames")
    merged: list[list[int]] = []
    for frame in warning_frames:
        end = min(frame + WINDOW_AFTER_WARNING, count)
        if merged and frame <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([frame, end])
    return merged


def triage_summary(warnings: list[dict], failures: list[dict], count: int) -> dict:
    require(len(warnings) == count and
            all(row["frame"] == i for i, row in enumerate(warnings)),
            "incomplete or reordered warning frames")
    frames = [i for i, row in enumerate(warnings, start=1) if row["warnings"]]
    windows = review_windows(frames, count)
    queued = {frame for first, last in windows for frame in range(first, last + 1)}
    result = dict(
        schema="visiontrack.continuity-warning-mot17-triage/v1",
        decision="queue frames w..w+2 for manual continuity inspection",
        frames=count,
        assessment_opportunity_frames=sum(bool(r["assessment_opportunity"]) for r in warnings),
        two_supported_previous_track_frames=sum(bool(r["two_supported_previous_tracks"])
                                                for r in warnings),
        warning_frames=frames,
        warning_frame_count=len(frames),
        warning_component_count=sum(len(r["warnings"]) for r in warnings),
        review_windows=windows,
        review_task_count=len(windows),
        review_frame_count=len(queued),
        review_frame_fraction=len(queued) / count,
        events={},
        known_opened_sequence=True,
        independent_physical_labels=False,
        count_or_flow_truth=False,
        practitioner_usefulness_tested=False,
    )
    for kind in EVENT_TYPES:
        events = [row for row in failures if row["event_type"] == kind]
        event_frames = {row["source_frame"] for row in events}
        require(all(1 <= frame <= count for frame in event_frames), "event outside sequence")
        covered = [row for row in events if row["source_frame"] in queued]
        result["events"][kind] = dict(
            count=len(events), unique_frames=len(event_frames),
            covered_count=len(covered), missed_count=len(events) - len(covered),
            covered_unique_frames=len(event_frames & queued),
            review_tasks_with_event=sum(any(first <= f <= last for f in event_frames)
                                        for first, last in windows),
            review_tasks_without_event=sum(not any(first <= f <= last for f in event_frames)
                                           for first, last in windows),
            covered_events=[dict(source_frame=row["source_frame"],
                                 gt_id=row["gt_id"], hyp_id=row["hyp_id"])
                            for row in covered],
        )
    return result


def execute(cache: Path, labels: Path, baseline: Path, rescore: Path, output: Path) -> dict:
    require(not output.exists() and not output.is_symlink(), "new output directory required")
    require(output.parent.is_dir(), "existing output parent required")
    target = output.resolve()
    require(not target.is_relative_to(ROOT) and
            not target.is_relative_to(ROOT.parent / "visiontrack-cpp"),
            "result directory must be outside both repositories")
    method = committed_method()
    original, corrected, intake, raw, failures, metrics = validated_inputs(
        cache, labels, baseline, rescore)
    seq = CachedSequence(cache)
    require(seq.length == FRAME_COUNT and seq.name == "MOT17-04-FRCNN",
            "unexpected cached sequence")
    require(committed_method() == method, "method changed during intake")
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.continuity-warning-mot17-method/v1",
        committed=method, baseline_manifest_sha256=BASELINE_MANIFEST,
        rescore_manifest_sha256=RESCORE_MANIFEST,
        cache_and_labels=intake["input_sha256"],
        runtime=dict(python=sys.version, numpy=np.__version__, platform=platform.platform()),
        frame_range=[1, FRAME_COUNT], warning_window_after=WINDOW_AFTER_WARNING,
        exploratory_known_sequence=True, tracker_candidate=False, images_read=False,
    ))
    try:
        tracker, observer, warnings = ByteTracker(TrackerConfig()), ContinuityObserver(), []
        with (output / "warnings.jsonl").open("x") as stream:
            for source_frame, saved in enumerate(raw, start=1):
                fd = seq.frame(source_frame)
                require(fd.frame == source_frame, "cached source frame drift")
                detections = fd.detections()
                check_frame_input(source_frame, detections, saved)
                record = observer.inspect(source_frame - 1, detections)
                observations = tracker.update(detections)
                require(tracker.frame_index == source_frame - 1, "tracker frame drift")
                check_frame_output(source_frame, observations, saved)
                observer.advance(source_frame - 1, observations)
                stream.write(encoded(dict(source_frame=source_frame, **record)))
                warnings.append(record)
                if source_frame % 250 == 0:
                    print(f"warning replay: {source_frame}/{FRAME_COUNT}", flush=True)
        summary = triage_summary(warnings, failures, FRAME_COUNT)
        require(summary["events"]["id_switch"]["count"] == metrics["IDSW"] and
                summary["events"]["fragmentation"]["count"] == metrics["Frag"],
                "corrected metric counts changed")
        require(committed_method() == method and
                read_bundle(baseline) == original and
                read_packet(rescore, RESCORE_MANIFEST) == corrected and
                audit(cache, labels) == intake, "method or input drift during replay")
        write_json(output / "summary.json", summary)
        write_json(output / "manifest.json", {
            p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(output.iterdir()) if p.is_file()})
        return summary
    except Exception as exc:
        write_json(output / "failure.json", dict(error_type=type(exc).__name__,
                                                  message=str(exc), complete=False))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache", "labels", "baseline", "rescore", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    summary = execute(args.cache, args.labels, args.baseline, args.rescore, args.output)
    print(encoded(dict(output=str(args.output), summary=summary)), flush=True)


if __name__ == "__main__":
    main()
