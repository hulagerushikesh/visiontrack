"""Why the motion gate misses fast vehicles (plan item R1).

Explains results that already exist; it tests nothing and changes no verdict.
It replays the saved GRAM-RTM and SVMOT detections through the gate-on tracker
exactly as the frozen tests did, and records every association the motion gate
refused although the boxes overlapped enough to match. Each refusal is split
into the four box terms of the gate distance: centre x, centre y, aspect
ratio (width over height) and height. Then, for every reference crossing the
gate-on tracker missed, it looks for a refusal on that vehicle in the second
before the crossing and records the vehicle's speed and box height.

The replay is checked against the frozen runs: the gate-on output digest and
the crossing counts must equal the saved results, or the script stops.

  python -m experiments.gate_miss_explanation \
      --gram-root <gram-rtm-intake folder> --svmot-root <svmot-test folder> \
      --output experiments/gate_miss_explanation_v1_result.json \
      --figure docs/assets/gate-miss-explanation.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import experiments.gram_rtm_gate as gram
import experiments.svmot_gate as svmot
from visiontrack.core.assignment import linear_assignment
from visiontrack.core.geometry import iou_matrix, xyah_to_xyxy
from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker

TERMS = ("centre_x", "centre_y", "aspect", "height")
LOOKBACK = 30  # frames: one second at 30 fps, before the crossing frame
VEHICLE_IOU = 0.5  # a refused detection belongs to the crossing vehicle at this overlap


class RecordingKalman(KalmanBoxTracker):
    """The default filter, unchanged, that also keeps every gate refusal."""

    def __init__(self, cfg: TrackerConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.frame = 0
        self.refusals: list[dict] = []
        self.diagonal_error = 0.0

    def gating_distance_batch(self, means, covariances, measurements):
        d2 = super().gating_distance_batch(means, covariances, measurements)
        gate = self.gate
        rows, cols = np.nonzero(d2 > gate)
        if len(rows):
            predicted = xyah_to_xyxy(means[:, :4])
            boxes = xyah_to_xyxy(np.asarray(measurements))
            overlap = iou_matrix(predicted, boxes)
            track_classes, det_classes = self.classes
            for t, d in zip(rows.tolist(), cols.tolist(), strict=True):
                if overlap[t, d] < self.cfg.match_iou_thresh:
                    continue  # the overlap test alone would refuse this pair
                a, b = track_classes[t], det_classes[d]
                if self.cfg.class_aware and a != b and a != -1 and b != -1:
                    continue  # the class test alone would refuse this pair
                proj_mean, proj_cov = self.project(means[t], covariances[t])
                off = proj_cov - np.diag(np.diag(proj_cov))
                self.diagonal_error = max(self.diagonal_error,
                                          float(np.abs(off).max() / np.diag(proj_cov).min()))
                innovation = np.asarray(measurements[d]) - proj_mean
                parts = innovation ** 2 / np.diag(proj_cov)
                self.refusals.append({
                    "frame": self.frame, "d2": float(d2[t, d]), "iou": float(overlap[t, d]),
                    "box": [float(v) for v in boxes[d]],
                    "terms": {name: float(p) for name, p in zip(TERMS, parts, strict=True)},
                    "track_height": float(means[t, 3])})
        return d2


class RecordingTracker(ByteTracker):
    """The default tracker, unchanged, that shows the filter each pair's classes."""

    def _match(self, tracks, dets, iou_thresh, gate):
        self.kf.classes = ([t.class_id for t in tracks], [d.class_id for d in dets])
        return super()._match(tracks, dets, iou_thresh, gate)


def gate_on_replay(array: np.ndarray, frames: int) -> tuple[dict, RecordingKalman]:
    """{(frame, id): [x1, y1, x2, y2]} of the default tracker, plus its refusals."""
    cfg = TrackerConfig()
    tracker = RecordingTracker(cfg)
    kf = RecordingKalman(cfg)
    kf.gate = tracker._gate
    tracker.kf = kf
    by_frame: dict[int, list[Detection]] = {}
    for n, x1, y1, x2, y2, s, c in array:
        by_frame.setdefault(int(n), []).append(
            Detection(np.array([x1, y1, x2, y2]), float(s), int(c)))
    boxes = {}
    for n in range(1, frames + 1):
        kf.frame = n
        for o in tracker.update(by_frame.get(n, [])):
            boxes[(n, int(o.track_id))] = [float(v) for v in o.xyxy.tolist()]
    return boxes, kf


def match_pairs(reference: list[dict], predicted: list[dict], max_px: float,
                max_frames: int) -> set[int]:
    """Indices of matched reference crossings, by the frozen tests' matching rule."""
    if not reference or not predicted:
        return set()
    cost = np.zeros((len(reference), len(predicted)))
    for i, r in enumerate(reference):
        for j, p in enumerate(predicted):
            df = abs(r["frame"] - p["frame"])
            dist = ((r["x"] - p["x"]) ** 2 + (r["y"] - p["y"]) ** 2) ** 0.5
            if r["dir"] == p["dir"] and df <= max_frames and dist <= max_px:
                cost[i, j] = df - 1000.0
    rows, cols = linear_assignment(cost)
    return {int(i) for i, j in zip(rows, cols, strict=True) if cost[i, j] < 0}


def centres(boxes: dict) -> dict:
    return {k: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for k, b in boxes.items()}


def explain(reference_boxes: dict, reference: list[dict], missed: list[int],
            refusals: list[dict], rescued: set[int]) -> list[dict]:
    by_frame: dict[int, list[dict]] = {}
    for item in refusals:
        by_frame.setdefault(item["frame"], []).append(item)
    rows = []
    for index in missed:
        event = reference[index]
        f, ident = event["frame"], event["id"]
        now, before = reference_boxes.get((f, ident)), reference_boxes.get((f - 1, ident))
        speed = None
        if now is not None and before is not None:
            (ax, ay), (bx, by) = centres({0: before})[0], centres({0: now})[0]
            speed = float(np.hypot(bx - ax, by - ay))
        height = float(now[3] - now[1]) if now is not None else None
        found = None
        for frame in range(f, f - LOOKBACK - 1, -1):
            truth = reference_boxes.get((frame, ident))
            if truth is None:
                continue
            for item in by_frame.get(frame, []):
                if iou_matrix(np.array([truth]), np.array([item["box"]]))[0, 0] >= VEHICLE_IOU:
                    found = item
                    break
            if found:
                break
        row = {"frame": f, "id": ident, "speed_px_per_frame": speed, "height_px": height,
               "rescued_by_gate_off": index in rescued, "refusal": None}
        if found:
            total = sum(found["terms"].values())
            row["refusal"] = {
                "frames_before_crossing": f - found["frame"], "d2": found["d2"],
                "iou": found["iou"], "share": {k: v / total for k, v in found["terms"].items()},
                "driver": max(found["terms"], key=found["terms"].get)}
        rows.append(row)
    return rows


def summarise(rows: list[dict], refusals: list[dict]) -> dict:
    def drivers(items):
        out = dict.fromkeys(TERMS, 0)
        for item in items:
            out[item] += 1
        return out

    explained = [r for r in rows if r["refusal"]]
    return {
        "missed": len(rows),
        "rescued_by_gate_off": sum(r["rescued_by_gate_off"] for r in rows),
        "with_refusal": len(explained),
        "driver_of_missed": drivers(r["refusal"]["driver"] for r in explained),
        "driver_of_rescued": drivers(r["refusal"]["driver"] for r in explained
                                     if r["rescued_by_gate_off"]),
        "all_refusals": len(refusals),
        "driver_of_all_refusals": drivers(max(i["terms"], key=i["terms"].get) for i in refusals),
    }


def run_gram(root: Path, saved: dict) -> dict:
    out = {}
    for seq, (frames, width, height) in gram.SEQUENCES.items():
        array = np.load(root / "gate-cache" / f"{seq}-detections.npy")
        boxes, kf = gate_on_replay(array, frames)
        if gram.digest(centres(boxes)) != saved[seq]["output_sha256"]["gate_on"]:
            raise ValueError(f"{seq}: replay differs from the frozen gate-on run")
        labels = gram.load_labels(root, seq)
        reference_boxes = {(k + gram.EXPECTED_OFFSET, ident): b
                           for k, rows in labels.items() for ident, b in rows}
        mask = gram.excluded_mask(root, seq)
        line = ((0.0, 0.5 * height), (float(width), 0.5 * height))
        reference = gram.count(centres(reference_boxes), line, mask)["cancel"]
        max_px = gram.PX_FRACTION * width
        on = gram.count(centres(boxes), line, mask)["cancel"]
        off_centres = gram.replay(array, frames, "gate_off")
        off = gram.count(off_centres, line, mask)["cancel"]
        hit_on = match_pairs(reference, on, max_px, gram.MAX_FRAMES)
        hit_off = match_pairs(reference, off, max_px, gram.MAX_FRAMES)
        if len(reference) - len(hit_on) != saved[seq]["main"]["cancel"]["gate_on"]["fn"]:
            raise ValueError(f"{seq}: missed count differs from the frozen run")
        missed = sorted(set(range(len(reference))) - hit_on)
        rows = explain(reference_boxes, reference, missed, kf.refusals, hit_off - hit_on)
        out[seq] = {"rows": rows, "summary": summarise(rows, kf.refusals),
                    "diagonal_error": kf.diagonal_error}
        print("GRAM-RTM", seq, out[seq]["summary"], flush=True)
    return out


def run_svmot(root: Path, saved: dict) -> dict:
    out = {}
    for seq in svmot.TEST_SEQUENCES:
        frames, width, _ = svmot.seq_info(root, seq)
        array = np.load(root / "gate-cache" / f"{seq}-detections.npy")
        boxes, kf = gate_on_replay(array, frames)
        if svmot.digest(boxes) != saved[seq]["output_sha256"]["gate_on"]:
            raise ValueError(f"{seq}: replay differs from the frozen gate-on run")
        mask = svmot.road_mask(root, seq)
        line = tuple(tuple(p) for p in svmot.line_from_mask(mask)["line"])
        reference_boxes = svmot.gt_boxes(svmot.load_gt(root, seq))
        reference = svmot.count(centres(reference_boxes), line, mask)
        max_px = svmot.PX_FRACTION * width
        on = svmot.count(centres(boxes), line, mask)
        off = svmot.count(centres(svmot.replay(array, frames, "gate_off")), line, mask)
        hit_on = match_pairs(reference, on, max_px, svmot.MAX_FRAMES)
        hit_off = match_pairs(reference, off, max_px, svmot.MAX_FRAMES)
        if len(reference) - len(hit_on) != saved[seq]["crossings"]["gate_on"]["fn"]:
            raise ValueError(f"{seq}: missed count differs from the frozen run")
        missed = sorted(set(range(len(reference))) - hit_on)
        rows = explain(reference_boxes, reference, missed, kf.refusals, hit_off - hit_on)
        out[seq] = {"rows": rows, "summary": summarise(rows, kf.refusals),
                    "diagonal_error": kf.diagonal_error}
        print("SVMOT", seq, out[seq]["summary"], flush=True)
    return out


def pooled(venue: dict) -> dict:
    rows = [r for seq in venue.values() for r in seq["rows"]]
    total = summarise(rows, [])
    total["all_refusals"] = sum(s["summary"]["all_refusals"] for s in venue.values())
    keys = TERMS
    total["driver_of_all_refusals"] = {
        k: sum(s["summary"]["driver_of_all_refusals"][k] for s in venue.values()) for k in keys}
    return total


def figure(result: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"centre_x": "#2a6fdb", "centre_y": "#18a999", "aspect": "#e8590c",
               "height": "#7048e8"}
    labels = {"centre_x": "left-right position", "centre_y": "up-down position",
              "aspect": "width-to-height ratio", "height": "height"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, (venue, data) in zip(axes, result["venues"].items(), strict=True):
        rows = [r for seq in data.values() for r in seq["rows"]]
        drawn = set()
        for r in rows:
            if r["speed_px_per_frame"] is None or r["height_px"] is None:
                continue
            driver = r["refusal"]["driver"] if r["refusal"] else None
            colour = colours.get(driver, "#adb5bd")
            label = labels.get(driver, "no gate refusal found")
            ax.scatter(r["height_px"], r["speed_px_per_frame"], s=36 if r["rescued_by_gate_off"]
                       else 18, color=colour, edgecolor="black" if r["rescued_by_gate_off"]
                       else "none", linewidth=0.6, label=None if label in drawn else label)
            drawn.add(label)
        ax.set_title(f"{venue}: crossings the gate-on tracker missed")
        ax.set_xlabel("vehicle box height (pixels)")
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("vehicle speed (pixels per frame)")
    from matplotlib.lines import Line2D

    shown = [d for d in (*TERMS, None)
             if any(labels.get(d, "no gate refusal found") == n
                    for ax in axes for n in ax.get_legend_handles_labels()[1])]
    handles = [Line2D([], [], marker="o", linestyle="", markersize=6,
                      color=colours.get(d, "#adb5bd")) for d in shown]
    names = [f"gate refused on {labels[d]}" if d else "no gate refusal found" for d in shown]
    fig.legend(handles, names, loc="lower center", ncol=3, frameon=False)
    fig.text(0.5, 0.005, "Outlined points were caught with the gate off.", ha="center",
             fontsize=8, color="#495057")
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gram-root", type=Path, required=True)
    parser.add_argument("--svmot-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path)
    args = parser.parse_args()
    here = Path(__file__).parent
    saved_gram = json.loads((here / "gram_rtm_gate_v1_result.json").read_text())["sequences"]
    saved_svmot = json.loads((here / "svmot_gate_v1_result.json").read_text())["sequences"]
    venues = {"GRAM-RTM": run_gram(args.gram_root, saved_gram),
              "SVMOT": run_svmot(args.svmot_root, saved_svmot)}
    result = {"plan_item": "R1", "explains": ["docs/GRAM_RTM_TEST_PROTOCOL.md",
                                              "docs/SVMOT_GATE_TEST_PROTOCOL.md"],
              "lookback_frames": LOOKBACK, "vehicle_iou": VEHICLE_IOU,
              "pooled": {v: pooled(d) for v, d in venues.items()}, "venues": venues}
    args.output.write_text(json.dumps(result, indent=1) + "\n")
    if args.figure:
        figure(result, args.figure)
    print(json.dumps(result["pooled"], indent=1))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
