"""Extend the SAME first-event trace using v2's corrected prior-match history.

Reuses the existing bounded actual-call observer without weakening its legacy
entry-point guard. One fresh unchanged full replay, no retry or intervention.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import audit, require
from experiments.mot17_case_trace import STAGES, replay, selection
from experiments.mot17_coverage_v2 import RESCORE_MANIFEST, read_packet
from visiontrack.datasets.cache import CachedSequence
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.eval.mot17 import MOT17_PREPROCESSING
from visiontrack.tracking.config import TrackerConfig


def prepare(contents, rescore):
    require(json.loads(rescore["method.json"])["evaluator"] == EVALUATOR, "v2 metrics required")
    checked = json.loads(rescore["reference-check.json"])
    require(checked["all_reported_checks_agree"] and checked["num_checks"] == 45,
            "passing metric receipt required")
    events = [json.loads(line) for line in rescore["failures.jsonl"].splitlines()]
    first = next((e for e in events if e["event_type"] == "id_switch"), None)
    historical = json.loads(contents["run-1/summary.json"])["first_chronological_switch"]
    require(first is not None and historical is not None, "first switch required")
    require(all(first[k] == historical[k] for k in (
        "source_frame", "gt_id", "previous_hyp_id", "hyp_id")), "same first event required")
    summary = json.loads(rescore["score.json"])
    summary["first_chronological_switch"] = first
    # In-memory substitution only: raw/scored outputs remain the original bytes.
    current = dict(contents)
    current["run-1/summary.json"] = encoded(summary).encode()
    current["run-1/failures.jsonl"] = rescore["failures.jsonl"]
    selected = selection(current)
    old = selection(contents)
    return current, dict(**selected, legacy_last_scored_match=old["last_scored_match"],
                         legacy_source_window=old["source_window"])


def overview(path, selected):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    first, last = selected["source_window"]
    expected = set(range(first, last + 1))
    require({r["source_frame"] for r in rows} == expected, "trace window incomplete")
    old_id = selected["event"]["previous_hyp_id"]
    old_rows = []
    for frame in sorted(expected):
        events = [r for r in rows if r["source_frame"] == frame]
        require(sum(r["kind"] == "frame_start" for r in events) == 1 and
                sum(r["kind"] == "frame_end" for r in events) == 1,
                "incomplete frame boundary trace")
        stages = [r["stage"] for r in events if r["kind"] == "_match"]
        require(stages == list(STAGES), "incomplete stage trace")
        end = next(r for r in events if r["kind"] == "frame_end")
        state = next((t for t in end["tracks"] if t["track_id"] == old_id), None)
        updates = [r for r in events if r["kind"] == "_apply_match" and
                   r["before"]["track_id"] == old_id]
        old_rows.append(dict(source_frame=frame, present=state is not None,
                             time_since_update=state["time_since_update"] if state else None,
                             state=state["state"] if state else None,
                             public=old_id in end["public_ids"],
                             actual_detection_rows=[r["detection_row"] for r in updates]))
    return dict(event_counts=dict(Counter(r["kind"] for r in rows)), old_id=old_id,
                old_id_observed_frames=old_rows,
                old_id_continuously_updated_and_public=all(
                    r["present"] and r["time_since_update"] == 0 and r["public"] and
                    len(r["actual_detection_rows"]) == 1 for r in old_rows),
                physical_identity_established=False)


def execute(baseline, rescore_path, preprocessing_path, preprocessing_digest,
            cache, labels, output):
    require(not output.exists() and not output.is_symlink(), "new output required")
    contents = read_bundle(baseline)
    rescore = read_packet(rescore_path, RESCORE_MANIFEST)
    prep = read_packet(preprocessing_path, preprocessing_digest)
    prep_summary, prep_method = (json.loads(prep[n]) for n in ("summary.json", "method.json"))
    require(prep_summary["all_frames_agree"] and prep_summary["frames"] == 1050 and
            prep_summary["preprocessing"] == MOT17_PREPROCESSING and
            prep_method["baseline_manifest_sha256"] == BASELINE_MANIFEST and
            prep["reference-scored.jsonl"] == contents["run-1/scored.jsonl"],
            "same-input v2 preprocessing pass required")
    plan = json.loads(contents["plan.json"])
    require(plan["tracker_config"] == asdict(TrackerConfig()), "unchanged defaults required")
    require(audit(cache, labels) == plan["intake"], "source admission changed")
    current, selected = prepare(contents, rescore)
    root = Path(__file__).resolve().parents[1]
    paths = list((root / "src/visiontrack").rglob("*.py"))
    paths += [Path(__file__).resolve(), Path(cache), Path(labels)]
    paths += [root / f"experiments/{name}.py" for name in (
        "mot17_case_trace", "mot17_case_baseline", "mot17_case_coverage", "mot17_coverage_v2")]
    hashes = {str(p): sha(p) for p in paths}
    original = {n: d for n, d in plan["code"]["source_sha256"].items() if n.startswith(tuple(
        f"src/visiontrack/{part}/" for part in ("tracking", "core", "datasets", "detection")))}

    def guard():
        require(read_bundle(baseline) == contents, "historical baseline changed")
        require(read_packet(rescore_path, RESCORE_MANIFEST) == rescore, "metric receipt changed")
        require(read_packet(preprocessing_path, preprocessing_digest) == prep,
                "preprocessing receipt changed")
        for name, digest in {**hashes, **prep_method["source_sha256"]}.items():
            require(sha(Path(name)) == digest, "implementation/input changed")
        for name, digest in original.items():
            require(sha(root / name) == digest, "tracker implementation changed")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.mot17-first-switch-trace/v2", evaluator=EVALUATOR,
        preprocessing=MOT17_PREPROCESSING, selected=selected, source_sha256=hashes,
        baseline_manifest_sha256=BASELINE_MANIFEST, rescore_manifest_sha256=RESCORE_MANIFEST,
        preprocessing_manifest_sha256=preprocessing_digest, tracker_sha256=original,
        settings=asdict(TrackerConfig()),
        scope="same event, same window selection rule under v2 correspondence; "
              "one full replay, exact raw/scored/v2-failure parity; "
              "no tuning or physical ID claim"))
    write_json(output / "attempt.json", dict(started=True, retry_allowed=False))
    try:
        result = replay(CachedSequence(cache), current, selected, output)
        result["actual_trace_overview"] = overview(output / "events.jsonl", selected)
        guard()
    except Exception as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error),
                                                interpretation_allowed=False))
        raise
    write_json(output / "summary.json", result)
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "rescore", "preprocessing-check", "cache", "labels", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--preprocessing-manifest-sha256", required=True)
    args = parser.parse_args()
    execute(args.baseline, args.rescore, args.preprocessing_check,
            args.preprocessing_manifest_sha256, args.cache, args.labels, args.output)


if __name__ == "__main__":
    main()
