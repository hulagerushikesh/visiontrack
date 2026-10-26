"""Single complete prospective development replay for continuity warning v1.

Run only after committing this module, its observer, scenes, tests and protocol.
The output directory must be new and outside both project repositories.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.continuity_warning import ContinuityObserver, _snapshot
from experiments.continuity_warning_scene import (
    RECIPE_SHA,
    ROOT,
    detector_payload,
    encoded,
    load_recipe,
    scene,
    validate_grid,
)
from experiments.mot17_case_baseline import sha, write_json
from experiments.traffic_runner import _check_import_origins, _environment, _git, _verify_tree
from visiontrack.detection.base import Detection
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

FROZEN_FILES = (
    "docs/CONTINUITY_WARNING_PROTOCOL.md",
    "experiments/continuity_warning_v1.json",
    "experiments/continuity_warning.py",
    "experiments/continuity_warning_scene.py",
    "experiments/continuity_warning_study.py",
    "experiments/continuity_warning_audit.py",
    "tests/test_continuity_warning.py",
    "tests/test_continuity_warning_study.py",
    "experiments/mot17_case_baseline.py",
    "experiments/traffic_runner.py",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def provenance(spec: dict) -> dict:
    _check_import_origins()
    require(_git(ROOT, "status", "--porcelain") == b"", "commit a clean method before replay")
    sources = {}
    for name in FROZEN_FILES:
        path = ROOT / name
        data = path.read_bytes()
        require(_git(ROOT, "show", f"HEAD:{name}") == data,
                f"method source is not committed: {name}")
        sources[name] = hashlib.sha256(data).hexdigest()
    return dict(revision=_git(ROOT, "rev-parse", "HEAD").decode().strip(),
                sources=sources, package=_verify_tree(ROOT, spec["baseline_revision"]),
                environment=_environment())


def replay(tracker, inputs: list[dict], *, monitored: bool) -> tuple[list[dict], list[dict]]:
    require(tracker.frame_index == -1, "cold tracker start required")
    observer = ContinuityObserver() if monitored else None
    outputs, warnings = [], []
    for frame, row in enumerate(inputs):
        require(row["frame"] == frame, "ordered zero-based inputs required")
        detections = [Detection(np.array(item["xyxy"], dtype=np.float64),
                                item["score"], item["class_id"])
                      for item in row["detections"]]
        if observer is not None:
            warnings.append(observer.inspect(frame, detections))
        observations = tracker.update(detections)
        require(tracker.frame_index == frame, "tracker frame drift")
        valid = _snapshot(observations, frame)
        by_id = {item["track_id"]: item for item in valid}
        # Preserve public list order for byte-for-byte monitored/off comparison.
        outputs.append(dict(frame=frame, observations=[by_id[item.track_id]
                                                        for item in observations]))
        if observer is not None:
            observer.advance(frame, observations)
    require(len(outputs) == len(inputs) and (not monitored or len(warnings) == len(inputs)),
            "incomplete replay")
    return outputs, warnings


def score(inputs: list[dict], outputs: list[dict], warnings: list[dict],
          spec: dict, duration: int) -> dict:
    count = spec["scene"]["frames"]
    require(len(inputs) == len(outputs) == len(warnings) == count, "complete frames required")
    accumulator = MotAccumulator(spec["scene"]["evaluation_iou"])
    matches, failures = [], []
    for frame, (source, output, warning) in enumerate(zip(inputs, outputs, warnings, strict=True)):
        require(source["frame"] == output["frame"] == warning["frame"] == frame,
                "ordered scoring frames required")
        truth = source["truth"]
        public = output["observations"]
        events = accumulator.update(
            np.array([item["reference_id"] for item in truth], dtype=np.int64),
            np.array([item["xyxy"] for item in truth], dtype=np.float64).reshape(-1, 4),
            np.array([item["track_id"] for item in public], dtype=np.int64),
            np.array([item["xyxy"] for item in public], dtype=np.float64).reshape(-1, 4))
        failures.extend(asdict(event) for event in events)
        # The canonical evaluator's current-step matching is recorded after update.
        # Its persistent last-match history is not substituted on an empty side.
        current = accumulator._previous if truth and public else {}
        truth_boxes = {item["reference_id"]: item["xyxy"] for item in truth}
        public_boxes = {item["track_id"]: item["xyxy"] for item in public}
        frame_matches = []
        for reference_id, track_id in sorted(current.items()):
            if reference_id not in truth_boxes or track_id not in public_boxes:
                continue
            from experiments.continuity_warning import _iou
            frame_matches.append(dict(reference_id=reference_id, track_id=track_id,
                                      iou=_iou(truth_boxes[reference_id],
                                               public_boxes[track_id])))
        matches.append(dict(frame=frame, matches=frame_matches))

    start = spec["scene"]["episode_start"]
    end = start + duration
    intervals = (("startup", 0, 2), ("settled", 2, start),
                 ("episode", start, end), ("recovery", end, count))
    strata = {}
    for name, a, b in intervals:
        frames = [row for row in warnings[a:b] if row["warnings"]]
        strata[name] = dict(frame_range=[a, b], warning_frames=len(frames),
                            warning_fraction=len(frames) / (b - a),
                            failures={kind: sum(event["event_type"] == kind and
                                                a <= event["frame_index"] < b
                                                for event in failures)
                                      for kind in ("miss", "false_positive",
                                                   "id_switch", "fragmentation")})
    warning_frames = [row["frame"] for row in warnings if row["warnings"]]
    episode_warning_frames = [frame for frame in warning_frames if start <= frame < end]
    outside_warning_frames = [frame for frame in warning_frames if frame < start or frame >= end]
    opportunity_frames = sum(row["two_supported_previous_tracks"] for row in warnings[3:])
    switches = [event["frame_index"] for event in failures if event["event_type"] == "id_switch"]
    proximity = [dict(switch_frame=frame,
                      warning_within_previous_two_frames=any(
                          max(0, frame - 2) <= w <= frame for w in warning_frames))
                 for frame in switches]
    return dict(metrics=asdict(accumulator.result()), matches=matches,
                failures=failures, strata=strata, warning_frames=warning_frames,
                episode_warning_frames=episode_warning_frames,
                first_episode_warning=episode_warning_frames[0] if episode_warning_frames else None,
                first_episode_warning_delay=(episode_warning_frames[0] - start
                                             if episode_warning_frames else None),
                outside_episode_warning_frames=outside_warning_frames,
                opportunity_frames=opportunity_frames,
                opportunity_fraction=opportunity_frames / (count - 3),
                switch_warning_proximity=proximity,
                switch_warning_fraction=(sum(r["warning_within_previous_two_frames"]
                                             for r in proximity) / len(proximity)
                                         if proximity else None))


def decision(results: list[dict], spec: dict) -> dict:
    screen = spec["development_screen"]
    issues = []
    by_key = {(row["family"], row["duration"]): row for row in results}
    if len(results) != spec["execution"]["cells"] or len(by_key) != len(results):
        issues.append("incomplete or duplicate grid")
    for row in results:
        family, duration = row["family"], row["duration"]
        if family in screen["target_families"]:
            delay = row["first_episode_warning_delay"]
            if len(row["episode_warning_frames"]) < 1 or delay is None or delay > 2:
                issues.append(f"target warning missing/late: {family}/{duration}")
        if family in screen["benign_families"]:
            if row["warning_frames"]:
                issues.append(f"benign warning: {family}/{duration}")
            if 10 * row["opportunity_frames"] < 9 * (spec["scene"]["frames"] - 3):
                issues.append(f"benign opportunity below 90%: {family}/{duration}")
    return dict(passed=not issues, issues=issues,
                interpretation=(screen["decision_if_pass"] if not issues else
                                screen["decision_if_fail"]))


def execute(output: Path) -> None:
    require(not output.exists() and not output.is_symlink(), "new non-symlink output required")
    require(output.parent.is_dir(), "existing output parent required")
    resolved = output.resolve()
    require(not any(resolved.is_relative_to(repo) for repo in
                    (ROOT, ROOT.parent / "visiontrack-cpp")), "output must be outside repos")
    spec = load_recipe()
    grid = validate_grid(spec)
    identity = provenance(spec)
    output.mkdir()
    write_json(output / "method.json", dict(recipe=spec, recipe_sha256=RECIPE_SHA,
                                            grid=grid, code=identity,
                                            independent_validation=False))
    results = []
    try:
        for duration in spec["scene"]["durations"]:
            cell_cache = {}
            for family in [item["name"] for item in spec["families"]]:
                folder = output / f"{duration:02d}-{family}"
                folder.mkdir()
                inputs = scene(spec, duration, family)
                original = encoded(inputs)
                write_json(folder / "inputs.json", inputs)
                tracker = ByteTracker(TrackerConfig(**spec["tracker_config"]))
                passes = []
                for index in range(4):
                    if index == 1:
                        tracker.reset()
                    elif index > 1:
                        tracker = ByteTracker(TrackerConfig(**spec["tracker_config"]))
                    outputs, warnings = replay(tracker, inputs, monitored=index != 3)
                    passes.append((outputs, warnings))
                    write_json(folder / f"outputs-{index + 1}.json", outputs)
                    if index != 3:
                        write_json(folder / f"warnings-{index + 1}.json", warnings)
                    require(encoded(inputs) == original, "input mutation")
                require(all(encoded(passes[0][0]) == encoded(item[0]) for item in passes[1:]),
                        "public output repeat/reset/noninterference mismatch")
                require(encoded(passes[0][1]) == encoded(passes[1][1]) ==
                        encoded(passes[2][1]), "observer repeat/reset mismatch")
                scored = score(inputs, passes[0][0], passes[0][1], spec, duration)
                write_json(folder / "scored.json", scored)
                for peer, must_match_truth in (("crossing_distinct", True),
                                               ("missing_second", False),
                                               ("coincident_two", False)):
                    if ((family == "unchanged_control" and peer == "crossing_distinct") or
                        (family == "exit_new_entrant" and peer == "missing_second") or
                        (family == "duplicate_single" and peer == "coincident_two")):
                        prior_inputs, prior_outputs, prior_warnings, prior_truth = cell_cache[peer]
                        require(detector_payload(inputs) == prior_inputs and
                                encoded(passes[0][0]) == prior_outputs and
                                encoded(passes[0][1]) == prior_warnings,
                                "same-observations public/warning mismatch")
                        require((encoded([r["truth"] for r in inputs]) == prior_truth) ==
                                must_match_truth, "semantic/control truth mismatch")
                cell_cache[family] = (detector_payload(inputs), encoded(passes[0][0]),
                                      encoded(passes[0][1]),
                                      encoded([r["truth"] for r in inputs]))
                results.append(dict(family=family, duration=duration,
                                    input_sha256=hashlib.sha256(original).hexdigest(),
                                    **{key: value for key, value in scored.items()
                                       if key not in {"matches", "failures"}}))
        require(len(results) == spec["execution"]["cells"] and
                provenance(spec) == identity and load_recipe() == spec,
                "incomplete grid or method drift")
        screen = decision(results, spec)
        write_json(output / "summary.json", dict(cells=results,
                   tracker_passes=spec["execution"]["tracker_passes"],
                   screen=screen, independent_validation=False,
                   tracker_changed=False, real_data_validation=False))
    except BaseException as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    write_json(output / "manifest.json", {
        str(path.relative_to(output)): dict(bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(output.rglob("*")) if path.is_file()})
    print(encoded(dict(output=str(output), cells=len(results), screen=screen)).decode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output)


if __name__ == "__main__":
    main()
