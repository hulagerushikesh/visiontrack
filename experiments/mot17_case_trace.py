"""Observe the pinned first MOT17 switch under unchanged defaults, not a trial.

One fresh full-sequence replay; actual Python call locals in a predeclared window.
Never patch tracker methods, change gates, load pixels or retry a failed replay.
The earlier frozen synthetic observer/study files are deliberately left intact.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, pair_record, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import audit, require
from visiontrack.core.assignment import associate
from visiontrack.datasets.cache import CachedSequence
from visiontrack.eval.mot import MotAccumulator
from visiontrack.eval.mot17 import preprocess_frame
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.cost import build_association_cost
from visiontrack.tracking.track import Track
from visiontrack.tracking.tracker import ByteTracker

STAGES = ("confirmed_high", "confirmed_low_recovery", "tentative_leftover_high")


def array(value):
    if value is None:
        return None
    value = np.asarray(value)
    require(value.size <= 256 * 256 and bool(np.isfinite(value).all()),
            "unbounded/nonfinite trace array")
    return value.tolist()


def state(track):
    return dict(track_id=track.track_id, state=track.state.name, hits=track.hits,
                age=track.age, time_since_update=track.time_since_update,
                start_frame=track.start_frame, score=track.score, class_id=track.class_id,
                xyxy=array(track.to_xyxy()), mean=array(track.mean),
                covariance=array(track.covariance))


def states(tracks):
    require(len(tracks) <= 256, "track budget exceeded")
    return [state(t) for t in tracks]


class Observer:
    """Copies actual stage inputs, cost masks, proposals and lifecycle transitions."""

    def __init__(self, tracker, detections, source_frame, emit):
        self.tracker, self.emit, self.frame = tracker, emit, source_frame
        self.ordinals = {id(d): i + 1 for i, d in enumerate(detections)}
        require(len(detections) <= 256 and len(self.ordinals) == len(detections),
                "bounded distinct detections required")
        self.stages, self.active = 0, {}
        self.codes = {getattr(ByteTracker, n).__code__: n for n in (
            "_match", "_apply_match", "_spawn")}
        self.codes[Track.mark_missed.__code__] = "mark_missed"

    def add(self, kind, **record):
        self.emit(dict(source_frame=self.frame, kind=kind, **record))

    def __call__(self, frame, event, result):
        parent = frame.f_back
        if (event == "return" and parent is not None
                and parent.f_code is ByteTracker._match.__code__
                and parent.f_locals.get("self") is self.tracker):
            record = self.active[id(parent)]
            if frame.f_code is build_association_cost.__code__:
                record["forbidden"] = array(frame.f_locals["forbidden"])
            elif frame.f_code is associate.__code__:
                record["proposed_rows"] = array(frame.f_locals.get("row_ind"))
                record["proposed_columns"] = array(frame.f_locals.get("col_ind"))
        name = self.codes.get(frame.f_code)
        if name is None or event not in ("call", "return"):
            return
        local, owner = frame.f_locals, frame.f_locals.get("self")
        if owner is not self.tracker and not (
                name == "mark_missed" and any(owner is t for t in self.tracker.tracks)):
            return
        if event == "call":
            if name == "_match":
                require(self.stages < 3, "unexpected match stage")
                record = dict(stage=STAGES[self.stages], tracks=states(local["tracks"]),
                              detection_rows=[self.ordinals[id(d)] for d in local["dets"]],
                              iou_threshold=local["iou_thresh"], gate_requested=local["gate"])
                self.stages += 1
            elif name == "_apply_match":
                record = dict(before=state(local["track"]),
                              detection_row=self.ordinals[id(local["det"])])
            elif name == "_spawn":
                record = dict(before_ids=[t.track_id for t in self.tracker.tracks],
                              detection_row=self.ordinals[id(local["det"])])
            else:
                record = dict(before=state(owner))
            self.active[id(frame)] = record
            return
        record = self.active.pop(id(frame))
        if name == "_match":
            require(result is not None, "association did not return normally")
            record.update(matrices={key: array(local.get(key)) for key in (
                "ious", "class_mismatch", "gating_d2", "cost")},
                gate_threshold=local.get("gate_thresh"), max_cost=local.get("max_cost"),
                matches=array(result[0]), unmatched_tracks=array(result[1]),
                unmatched_detections=array(result[2]))
        elif name == "_spawn":
            record["created"] = [state(t) for t in self.tracker.tracks
                                 if t.track_id not in record["before_ids"]]
        else:
            record["after"] = state(local["track"] if name == "_apply_match" else owner)
        self.add(name, **record)


def observed_update(tracker, detections, source_frame, emit):
    require(threading.current_thread() is threading.main_thread(), "main thread required")
    require(sys.getprofile() is None and sys.gettrace() is None,
            "do not replace an existing profiler/debugger")
    require(type(tracker) is ByteTracker and asdict(tracker.cfg) == asdict(TrackerConfig()),
            "exact default tracker required")
    observer = Observer(tracker, detections, source_frame, emit)
    observer.add("frame_start", tracks=states(tracker.tracks), detections=[
        dict(row=i + 1, xyxy=array(d.xyxy), score=d.score, class_id=d.class_id)
        for i, d in enumerate(detections)])
    try:
        sys.setprofile(observer)
        output = tracker.update(detections)
    finally:
        sys.setprofile(None)
    require(observer.stages == 3 and not observer.active, "incomplete observed frame")
    observer.add("frame_end", tracks=states(tracker.tracks),
                 public_ids=[o.track_id for o in output])
    return output


def selection(contents):
    """Same first event; include one frame before its last scored match, then +3."""
    summary = json.loads(contents["run-1/summary.json"])
    event = summary["first_chronological_switch"]
    require(event is not None, "no first switch to inspect")
    failures = [json.loads(line) for line in contents["run-1/failures.jsonl"].splitlines()]
    switches = [f for f in failures if f["event_type"] == "id_switch"]
    require(switches and switches[0] == event, "first switch does not reconcile")
    missed = {f["source_frame"] for f in failures
              if f["event_type"] == "miss" and f["gt_id"] == event["gt_id"]}
    prior = []
    for line in contents["run-1/scored.jsonl"].splitlines():
        row = json.loads(line)
        if (row["source_frame"] < event["source_frame"] and event["gt_id"] in row["gt_ids"]
                and row["source_frame"] not in missed):
            prior.append(row["source_frame"])
    require(bool(prior), "missing prior scored reference match")
    window = [max(1, prior[-1] - 1), min(1050, event["source_frame"] + 3)]
    require(window[1] - window[0] < 32, "bounded same-event window exceeded")
    return dict(event=event, last_scored_match=prior[-1], source_window=window,
                rule="one frame before last scored match through first switch +3; no second event")


def replay(seq, contents, selected, output):
    tracker, accumulator = ByteTracker(TrackerConfig()), MotAccumulator(iou_threshold=0.5)
    first, last = selected["source_window"]
    saved_raw = contents["run-1/raw.jsonl"].splitlines(keepends=True)
    saved_scored = contents["run-1/scored.jsonl"].splitlines(keepends=True)
    require(seq.length == len(saved_raw) == len(saved_scored), "incomplete source length")
    events, public_boxes = 0, 0
    with (output / "events.jsonl").open("x") as trace, \
            (output / "raw.jsonl").open("x") as raw, \
            (output / "scored.jsonl").open("x") as scored, \
            (output / "failures.jsonl").open("x") as failures:
        def emit(record):
            nonlocal events
            require(events < 8192, "trace event budget exceeded")
            trace.write(encoded(record))
            events += 1

        count = 0
        for count, fd in enumerate(seq.iter_range(1, seq.length), start=1):
            require(fd.frame == count and fd.det_features is None, "invalid source frame/features")
            expected = json.loads(saved_raw[count - 1])
            input_record = dict(
                source_frame=count, detections_xyxy=fd.det_xyxy.tolist(),
                detection_scores=fd.det_scores.tolist(), gt_ids=fd.gt_ids.tolist(),
                gt_xyxy=fd.gt_xyxy.tolist(), gt_classes=fd.gt_classes.tolist(),
                gt_consider=fd.gt_conf.tolist(), gt_visibility=fd.gt_vis.tolist())
            require(encoded(input_record) == encoded({k: expected[k] for k in input_record}),
                    f"source input changed at {count}")
            dets = fd.detections()
            require(all(d.class_id == 0 and d.feature is None for d in dets),
                    "baseline detection adapter changed")
            observations = (observed_update(tracker, dets, count, emit)
                            if first <= count <= last else tracker.update(dets))
            ids = np.array([o.track_id for o in observations], dtype=np.int64)
            boxes = np.array([o.xyxy for o in observations], dtype=np.float64).reshape(-1, 4)
            actual_raw = encoded(dict(**input_record, track_ids=ids.tolist(),
                                      track_xyxy=boxes.tolist()))
            raw.write(actual_raw)  # retain actual evidence before checking parity
            require(actual_raw.encode() == saved_raw[count - 1], f"raw replay mismatch at {count}")
            pairs = preprocess_frame(fd.gt_xyxy, fd.gt_ids, fd.gt_classes, fd.gt_conf, boxes, ids)
            actual_scored = encoded(pair_record(count, pairs))
            scored.write(actual_scored)
            require(actual_scored.encode() == saved_scored[count - 1],
                    f"scored replay mismatch at {count}")
            for event in accumulator.update(*pairs):
                failures.write(encoded(dict(source_frame=count, **asdict(event))))
            public_boxes += len(ids)
            if count % 250 == 0:
                print(f"unchanged trace replay {count}/{seq.length}", flush=True)
    require(count == seq.length, "incomplete source traversal")
    require((output / "failures.jsonl").read_bytes() == contents["run-1/failures.jsonl"],
            "canonical failure replay mismatch")
    clear = accumulator.result().as_dict()
    expected_metrics = json.loads(contents["run-1/summary.json"])["metrics"]
    require(all(expected_metrics[k] == v for k, v in clear.items()), "CLEAR mismatch")
    require(asdict(tracker.cfg) == asdict(TrackerConfig()), "configuration changed")
    return dict(frame_count=count, raw_public_boxes=public_boxes, trace_events=events,
                selected=selected, exact_raw_and_scored_parity=True, exact_failures_parity=True,
                clear=clear, images_read=False, tracker_modified=False, improvement_tested=False,
                independent_implementation=False, visual_cause_established=False)


def execute(baseline, cache, labels, output):
    require(not output.exists() and not output.is_symlink(), "new output required")
    contents = read_bundle(baseline)
    plan = json.loads(contents["plan.json"])
    require(plan["tracker_config"] == asdict(TrackerConfig()), "baseline defaults changed")
    require(audit(cache, labels) == plan["intake"], "baseline source admission changed")
    selected = selection(contents)
    root = Path(__file__).resolve().parents[1]
    hashes = dict(plan["code"]["source_sha256"])
    hashes.update({p: sha(root / p) for p in (
        "experiments/mot17_case_trace.py", "experiments/mot17_case_coverage.py")})

    def guard():
        for name, digest in hashes.items():
            require(sha(root / name) == digest, f"implementation changed: {name}")
        require(read_bundle(baseline) == contents, "baseline changed")
        require(audit(cache, labels) == plan["intake"], "source changed")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.mot17-first-switch-trace/v1",
        baseline_manifest_sha256=BASELINE_MANIFEST,
        source_sha256=hashes, selected=selected, settings=asdict(TrackerConfig()),
        git_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        git_status=subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
        environment=dict(python=sys.version, numpy=np.__version__, platform=platform.platform()),
        scope="post-baseline mechanism diagnostic; one fresh full replay; no candidate or tuning",
        detection_row_convention="one-based frame-local source row, not a person identity",
        frame_convention="source_frame is one-based; Track.start_frame is zero-based"))
    write_json(output / "attempt.json", dict(started=True, retry_allowed=False))
    try:
        result = replay(CachedSequence(cache), contents, selected, output)
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
    for name in ("baseline", "cache", "labels", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    execute(args.baseline, args.cache, args.labels, args.output)


if __name__ == "__main__":
    main()
