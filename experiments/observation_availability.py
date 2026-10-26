"""Fixed small observation study; no tracker candidate, images or real-data claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from numbers import Integral
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_intake import require
from experiments.traffic_runner import _check_import_origins, _environment, _git, _verify_tree
from visiontrack.detection.base import Detection
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "experiments/observation_availability_v1.json"
RECIPE_SHA = "2b66b7cc1cc0a6113d31a434e9a7358a690ed029c5f89d602c1ffa0b269de558"
FROZEN_FILES = (
    "experiments/observation_availability.py", "experiments/observation_availability_v1.json",
    "tests/test_observation_availability.py", "docs/OBSERVATION_AVAILABILITY_PROTOCOL.md",
    "experiments/mot17_case_baseline.py", "experiments/mot17_case_intake.py",
    "experiments/traffic_runner.py",
)


def load_recipe():
    require(sha(RECIPE) == RECIPE_SHA, "frozen recipe drift")
    spec = json.loads(RECIPE.read_text())
    require(asdict(TrackerConfig()) == spec["tracker_config"], "default configuration drift")
    return spec


def scene(spec, duration, condition):
    require(type(duration) is int and duration in spec["durations"], "unregistered duration")
    require(condition in spec["conditions"], "unregistered condition")
    g = spec["geometry"]
    start = spec["warmup_frames"]
    frames = []
    for frame in range(start + duration + spec["recovery_frames"]):
        x = g["x"] + frame * g["velocity_x"]
        truth = [[x + dx, g["y"], x + dx + g["width"], g["y"] + g["height"]]
                 for dx in (0, g["second_dx"])]
        boxes = [b.copy() for b in truth]
        if start <= frame < start + duration:
            if condition == "missing_second":
                boxes = boxes[:1]
            elif condition == "shared_union":
                boxes = [[truth[0][0], g["y"], truth[1][2], g["y"] + g["height"]]]
        frames.append(dict(frame=frame, reference_ids=spec["reference_ids"].copy(),
                           truth=truth, detections=boxes))
    return frames


def replay(tracker, inputs, spec):
    require(tracker.frame_index == -1, "cold start required")
    rows = []
    for row in inputs:
        # Only detector payloads enter update; never truth or reference IDs.
        observations = tracker.update([
            Detection(np.array(box, dtype=np.float64), spec["score"], spec["class_id"])
            for box in row["detections"]])
        require(tracker.frame_index == row["frame"], "frame mismatch")
        require(all(isinstance(o.track_id, Integral) and not isinstance(o.track_id, bool) and
                    isinstance(o.class_id, Integral) and not isinstance(o.class_id, bool) and
                    o.frame == row["frame"] for o in observations), "public metadata mismatch")
        output = [dict(track_id=int(o.track_id), xyxy=o.xyxy.tolist(),
                       score=float(o.score), class_id=int(o.class_id)) for o in observations]
        ids = [r["track_id"] for r in output]
        require(len(set(ids)) == len(ids) and all(i > 0 for i in ids), "invalid public IDs")
        for observation in output:
            box = np.asarray(observation["xyxy"])
            require(box.shape == (4,) and bool(np.isfinite(box).all()) and
                    bool((box[2:] > box[:2]).all()) and
                    np.isfinite(observation["score"]) and 0 <= observation["score"] <= 1 and
                    observation["class_id"] == spec["class_id"], "invalid public observation")
        rows.append(dict(frame=row["frame"], observations=output))
    return rows


def score(inputs, outputs, spec, duration):
    require(len(inputs) == len(outputs) == spec["warmup_frames"] + duration +
            spec["recovery_frames"], "complete input/output required")
    accumulator = MotAccumulator(spec["evaluation_iou"])
    history, failures = [], []
    for frame, (truth, output) in enumerate(zip(inputs, outputs, strict=True)):
        require(truth["frame"] == output["frame"] == frame, "ordered frames required")
        observations = output["observations"]
        events = accumulator.update(
            np.array(truth["reference_ids"]), np.array(truth["truth"]),
            np.array([o["track_id"] for o in observations], dtype=np.int64),
            np.array([o["xyxy"] for o in observations], dtype=float).reshape(-1, 4))
        missed = {e.gt_id for e in events if e.event_type == "miss"}
        # Existing evaluator history, read only AFTER excluding current misses.
        matches = {str(i): int(accumulator._last_hyp[i]) if i not in missed else None
                   for i in spec["reference_ids"]}
        history.append(dict(frame=frame, matches=matches))
        failures.extend(asdict(e) for e in events)
    start, end = spec["warmup_frames"], spec["warmup_frames"] + duration
    strata = {}
    for name, a, b in (("startup", 0, spec["tracker_config"]["n_init"] - 1),
                       ("settled_warmup", spec["tracker_config"]["n_init"] - 1, start),
                       ("episode", start, end), ("recovery", end, len(inputs))):
        strata[name] = dict(frame_range=[a, b], **{
            kind: sum(e["event_type"] == kind and a <= e["frame_index"] < b for e in failures)
            for kind in ("miss", "false_positive", "id_switch", "fragmentation")})
    recovery = {}
    for identity in map(str, spec["reference_ids"]):
        previous = history[start - 1]["matches"][identity]
        resumed = next((h for h in history[end:] if h["matches"][identity] is not None), None)
        current = resumed["matches"][identity] if resumed else None
        recovery[identity] = dict(before_id=previous, first_recovery_id=current,
                                  first_recovery_frame=resumed["frame"] if resumed else None,
                                  delay_frames=resumed["frame"] - end if resumed else None,
                                  same_id=(current == previous) if resumed and previous is not None
                                  else None)
    return dict(metrics=asdict(accumulator.result()), strata=strata, recovery=recovery,
                history=history, failures=failures)


def provenance(spec):
    _check_import_origins()
    sources = {}
    for name in FROZEN_FILES:
        data = (ROOT / name).read_bytes()
        require(_git(ROOT, "show", f"HEAD:{name}") == data, "commit study sources before replay")
        sources[name] = sha(ROOT / name)
    return dict(revision=_git(ROOT, "rev-parse", "HEAD").decode().strip(),
                sources=sources, package=_verify_tree(ROOT, spec["baseline_revision"]),
                environment=_environment())


def execute(output):
    require(not output.exists() and not output.is_symlink(), "new output required")
    require(output.parent.is_dir() and not any(output.resolve().is_relative_to(repo) for repo in
            (ROOT, ROOT.parent / "visiontrack-cpp")), "external existing parent required")
    spec = load_recipe()
    identity = provenance(spec)
    output.mkdir()
    write_json(output / "method.json", dict(recipe=spec, recipe_sha256=RECIPE_SHA,
                                            code=identity, independent_validation=False))
    results = []
    try:
        for duration in spec["durations"]:
            control_input = control_result = None
            for condition in spec["conditions"]:
                directory = output / f"{duration:02d}-{condition}"
                directory.mkdir()
                inputs = scene(spec, duration, condition)
                original = encoded(inputs)
                write_json(directory / "inputs.json", inputs)
                tracker = ByteTracker(TrackerConfig(**spec["tracker_config"]))
                runs = []
                for index in range(3):
                    if index == 1:
                        tracker.reset()
                    elif index == 2:
                        tracker = ByteTracker(TrackerConfig(**spec["tracker_config"]))
                    runs.append(replay(tracker, inputs, spec))
                    write_json(directory / f"outputs-{index + 1}.json", runs[-1])
                    require(encoded(inputs) == original, "input mutation")
                require(encoded(runs[0]) == encoded(runs[1]) == encoded(runs[2]),
                        "fresh/reset mismatch")
                result = score(inputs, runs[0], spec, duration)
                write_json(directory / "scored.json", result)
                if condition == "distinct":
                    control_input, control_result = original, result
                elif condition == "unchanged_control":
                    require(original == control_input and result == control_result and
                            (directory / "outputs-1.json").read_bytes() ==
                            (output / f"{duration:02d}-distinct/outputs-1.json").read_bytes(),
                            "unchanged control mismatch")
                delta = {key: result["metrics"][key] - control_result["metrics"][key]
                         for key in ("false_negatives", "false_positives", "id_switches",
                                     "fragmentations")}
                results.append(dict(duration=duration, condition=condition,
                                    input_sha256=hashlib.sha256(original.encode()).hexdigest(),
                                    metrics=result["metrics"], strata=result["strata"],
                                    recovery=result["recovery"], delta_from_distinct=delta))
        require(len(results) == 12 and provenance(spec) == identity and load_recipe() == spec,
                "incomplete coverage or source/config drift")
        write_json(output / "summary.json", dict(cells=results, passes=36,
                   tracker_changed=False, real_data_validation=False, independent_review=False))
    except BaseException as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    write_json(output / "manifest.json", {
        str(p.relative_to(output)): dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.rglob("*")) if p.is_file()})
    print(encoded(dict(output=str(output), cells=len(results), passes=36)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(encoded(load_recipe()))
        return
    require(args.output is not None, "explicit output required")
    execute(args.output)


if __name__ == "__main__":
    main()
