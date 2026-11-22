"""UA-DETRAC motion-gate test (docs/UA_DETRAC_TEST_PROTOCOL.md).

Written before the terms are confirmed and before any file is downloaded, so
the file layout below is the one the dataset's public description gives. The
format check may show a different layout; the parsers are then adjusted, and
the change recorded in the protocol, before the first tracker run.

The dataset stays owner-local. Expected layout under <root>:
  annotations/<seq>.xml                       (DETRAC-XML, one per sequence)
  detections/<SET>/<seq>_Det_<SET>.txt        (frame, n, left, top, width, height, score)
  images/<seq>/img00001.jpg                   (optional: only frame count and size)

Steps, each run on its own:
  python -m experiments.ua_detrac_gate check --root <root>    (format check, no counting)
  python -m experiments.ua_detrac_gate run   --root <root> --output <json>
"""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS
from experiments.crossing_rules import cancel_reversals
from experiments.roundabouthd_gate import crossings
from experiments.svmot_gate import centres_of, digest, id_switches, replay
from visiontrack.core.assignment import linear_assignment

SETS = ("R-CNN", "CompACT", "ACF", "DPM")  # fixed order of preference
WIDTH, HEIGHT = 960, 540
WINDOW = 25  # cancel-reversals window: one second at 25 fps
MAX_FRAMES = 5  # 0.2 s
MAX_PX = 38.0  # at 960 pixels wide; scales with width
LINE_FRACTIONS = {"main": 0.5, "sensitivity_40": 0.4, "sensitivity_60": 0.6}
FALSE_ALLOWANCE = 2  # or 10% of the gain in correct crossings, whichever is larger
SIGN_LEVEL = 0.05
IDSW_LIMIT = 0.10  # amendment 2026-11-22: pooled ID switches may rise by at most 10%
CLASS_ID = 0  # supplied detections have no vehicle type: one shared class


def sequences(root: Path) -> list[str]:
    return sorted(p.stem for p in (root / "annotations").glob("*.xml"))


def load_annotation(root: Path, seq: str) -> dict:
    """{"boxes": {(frame, id): [x1, y1, x2, y2]}, "ignored": [[x1, y1, x2, y2], ...]}"""
    tree = ET.parse(root / "annotations" / f"{seq}.xml").getroot()

    def xyxy(box):
        x, y = float(box.get("left")), float(box.get("top"))
        return [x, y, x + float(box.get("width")), y + float(box.get("height"))]

    ignored = [xyxy(b) for region in tree.iter("ignored_region") for b in region.iter("box")]
    boxes = {}
    for frame in tree.iter("frame"):
        n = int(frame.get("num"))
        for target in frame.iter("target"):
            boxes[(n, int(target.get("id")))] = xyxy(target.find("box"))
    return {"boxes": boxes, "ignored": ignored}


def detection_path(root: Path, det_set: str, seq: str) -> Path:
    return root / "detections" / det_set / f"{seq}_Det_{det_set}.txt"


def load_detections(root: Path, det_set: str, seq: str) -> np.ndarray:
    """Rows (frame, x1, y1, x2, y2, score, class), as the tracker replay expects."""
    raw = np.loadtxt(detection_path(root, det_set, seq), delimiter=",", ndmin=2)
    if raw.size == 0:
        return np.zeros((0, 7))
    x, y, w, h = raw[:, 2], raw[:, 3], raw[:, 4], raw[:, 5]
    return np.stack([raw[:, 0], x, y, x + w, y + h, raw[:, 6],
                     np.full(len(raw), CLASS_ID)], axis=1)


def frame_info(root: Path, seq: str, annotation: dict, dets: np.ndarray) -> tuple[int, int, int]:
    """(frames, width, height): from the image folder if present, else labels and detections."""
    folder = root / "images" / seq
    images = sorted(folder.glob("img*.jpg")) if folder.exists() else []
    if images:
        from PIL import Image

        with Image.open(images[0]) as first:
            width, height = first.size
        return len(images), width, height
    last = max([k[0] for k in annotation["boxes"]] + [int(dets[:, 0].max()) if len(dets) else 0])
    return last, WIDTH, HEIGHT


def choose_set(root: Path, seqs: list[str]) -> dict:
    """First set, in the fixed order, whose scores all lie in [0, 1] on every sequence."""
    report = {}
    for det_set in SETS:
        lo, hi, missing = math.inf, -math.inf, []
        for seq in seqs:
            if not detection_path(root, det_set, seq).exists():
                missing.append(seq)
                continue
            scores = load_detections(root, det_set, seq)[:, 5]
            if len(scores):
                lo, hi = min(lo, float(scores.min())), max(hi, float(scores.max()))
        ok = not missing and 0.0 <= lo and hi <= 1.0
        report[det_set] = {"min": lo, "max": hi, "missing": missing, "passes": ok}
        if ok:
            return {"chosen": det_set, "checked": report}
    return {"chosen": None, "checked": report}


def check(root: Path) -> dict:
    """Format check: counts, sizes, score ranges. No counting, tracking or inspection."""
    seqs = sequences(root)
    out = {"sequences": len(seqs), "per_sequence": {}}
    for seq in seqs:
        ann = load_annotation(root, seq)
        frames, width, height = frame_info(root, seq, ann, np.zeros((0, 7)))
        out["per_sequence"][seq] = {
            "frames": frames, "size": [width, height], "label_rows": len(ann["boxes"]),
            "ids": len({k[1] for k in ann["boxes"]}), "ignored_regions": len(ann["ignored"]),
            "first_label_frame": min((k[0] for k in ann["boxes"]), default=None)}
    out["detection_sets"] = choose_set(root, seqs)
    return out


def line_at(fraction: float, width: int, height: int):
    y = fraction * height
    return ((0.0, y), (float(width), y))


def outside_ignored(events: list[dict], ignored: list) -> list[dict]:
    def inside(e, b):
        return b[0] <= e["x"] <= b[2] and b[1] <= e["y"] <= b[3]

    return [e for e in events if not any(inside(e, b) for b in ignored)]


def count(centres: dict, line, ignored: list) -> dict[str, list[dict]]:
    plain = outside_ignored(crossings(centres, line), ignored)
    return {"cancel": cancel_reversals(plain, WINDOW), "plain": plain}


def match(reference: list[dict], predicted: list[dict], max_px: float) -> dict:
    """One-to-one: same direction, at most MAX_FRAMES apart, points at most max_px apart."""
    pairs = []
    if reference and predicted:
        cost = np.zeros((len(reference), len(predicted)))
        for i, r in enumerate(reference):
            for j, p in enumerate(predicted):
                df = abs(r["frame"] - p["frame"])
                dist = ((r["x"] - p["x"]) ** 2 + (r["y"] - p["y"]) ** 2) ** 0.5
                if r["dir"] == p["dir"] and df <= MAX_FRAMES and dist <= max_px:
                    cost[i, j] = df - 1000.0
        rows, cols = linear_assignment(cost)
        pairs = [(int(i), int(j)) for i, j in zip(rows, cols, strict=True) if cost[i, j] < 0]
    return {"tp": len(pairs), "fp": len(predicted) - len(pairs), "fn": len(reference) - len(pairs)}


def sign_test(wins: int, losses: int) -> float:
    """One-sided p-value: P(at least `wins` of wins+losses under a fair coin)."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def judge(seqs: dict, candidate: str, line: str = "main", rule: str = "cancel") -> dict:
    """The protocol's four conditions for `candidate` against gate on."""
    def get(seq, variant, key):
        return seqs[seq]["lines"][line][rule][variant][key]

    names = list(seqs)
    pooled = {v: {k: sum(get(s, v, k) for s in names) for k in ("tp", "fp", "fn")}
              for v in ("gate_on", candidate)}
    gain = pooled[candidate]["tp"] - pooled["gate_on"]["tp"]
    diffs = [(get(s, candidate, "fp") + get(s, candidate, "fn")) -
             (get(s, "gate_on", "fp") + get(s, "gate_on", "fn")) for s in names]
    wins, losses = sum(d < 0 for d in diffs), sum(d > 0 for d in diffs)
    p = sign_test(wins, losses)
    idsw = {v: sum(seqs[s]["id_switches"][v] for s in names) for v in ("gate_on", candidate)}
    conditions = {
        "missed_fall": pooled[candidate]["fn"] < pooled["gate_on"]["fn"],
        "false_within_allowance": pooled[candidate]["fp"] - pooled["gate_on"]["fp"]
        <= max(FALSE_ALLOWANCE, 0.1 * gain),
        "sign_test": p < SIGN_LEVEL,
        "id_switches_within_limit": idsw[candidate] <= idsw["gate_on"] * (1 + IDSW_LIMIT),
    }
    return {"verdict": "supported" if all(conditions.values()) else "not supported",
            "conditions": conditions, "pooled": pooled, "sign_test": {
                "fewer_errors": wins, "more_errors": losses, "p": p}, "id_switches": idsw}


def prefer(seqs: dict, verdicts: dict) -> str:
    passing = [v for v in ("aspect_free_gate", "gate_off") if verdicts[v] == "supported"]
    if len(passing) < 2:
        return passing[0] if passing else "gate_on"

    def pooled(v, k):
        return sum(seqs[s]["lines"]["main"]["cancel"][v][k] for s in seqs)

    err = {v: pooled(v, "fp") + pooled(v, "fn") for v in passing}
    if err["gate_off"] <= 0.9 * err["aspect_free_gate"] and \
            pooled("gate_off", "fp") <= pooled("aspect_free_gate", "fp"):
        return "gate_off"
    return "aspect_free_gate"


def run_sequence(root: Path, seq: str, det_set: str) -> dict:
    ann = load_annotation(root, seq)
    dets = load_detections(root, det_set, seq)
    frames, width, height = frame_info(root, seq, ann, dets)
    max_px = MAX_PX * width / WIDTH
    reference_centres = centres_of(ann["boxes"])
    lines = {name: line_at(f, width, height) for name, f in LINE_FRACTIONS.items()}
    reference = {name: count(reference_centres, ln, ann["ignored"]) for name, ln in lines.items()}
    result = {"frames": frames, "size": [width, height], "detections": int(len(dets)),
              "lines": {name: {rule: {"reference": len(reference[name][rule])}
                               for rule in ("cancel", "plain")} for name in lines},
              "id_switches": {}, "public_ids": {}, "output_sha256": {}}
    for variant in VARIANTS:
        boxes = replay(dets, frames, variant)
        if digest(boxes) != digest(replay(dets, frames, variant)):
            raise ValueError(f"{seq} {variant}: repeatability mismatch")
        centres = centres_of(boxes)
        for name, ln in lines.items():
            tracked = count(centres, ln, ann["ignored"])
            for rule in ("cancel", "plain"):
                result["lines"][name][rule][variant] = match(
                    reference[name][rule], tracked[rule], max_px)
        result["id_switches"][variant] = id_switches(ann["boxes"], boxes, frames)
        result["public_ids"][variant] = len({k[1] for k in boxes})
        result["output_sha256"][variant] = digest(boxes)
    return result


def run(root: Path) -> dict:
    seqs = sequences(root)
    chosen = choose_set(root, seqs)
    if chosen["chosen"] is None:
        raise ValueError("no supplied detection set passes the 0-to-1 score rule: "
                         "the protocol stops for a dated amendment")
    results = {}
    for seq in seqs:  # one sequence at a time
        results[seq] = run_sequence(root, seq, chosen["chosen"])
        main = results[seq]["lines"]["main"]["cancel"]
        print(seq, main, results[seq]["id_switches"], flush=True)
    judged = {c: judge(results, c) for c in ("aspect_free_gate", "gate_off")}
    verdicts = {c: j["verdict"] for c, j in judged.items()}
    sensitivity = {name: {c: judge(results, c, line=name)["verdict"] for c in verdicts}
                   for name in LINE_FRACTIONS if name != "main"}
    return {"protocol": "docs/UA_DETRAC_TEST_PROTOCOL.md", "detection_set": chosen,
            "sequences": results, "decision": judged, "verdicts": verdicts,
            "preferred": prefer(results, verdicts), "sensitivity_lines": sensitivity,
            "plain_counter": {c: judge(results, c, rule="plain")["verdict"] for c in verdicts}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("check", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.root) if args.step == "check" else run(args.root)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
