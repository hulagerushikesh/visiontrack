"""GRAM-RTM Urban1 junction test (docs/GRAM_RTM_URBAN1_TEST_PROTOCOL.md).

The dataset stays owner-local. Expected layout under <root> (the GRAM-RTM intake folder):
  extracted/GRAM-RTMv4/Annotations/Urban1/xml/<k>.xml   (labels, from 0)
  extracted/GRAM-RTMv4/ROI/Urban1-map.jpg               (dark = not labelled)
  images/Urban1.zip                                     (the 23,435 frames)

Frames are addressed by position: image 1 is the archive's lowest-numbered JPEG,
whatever its file name, and the numbers must run without gaps.

Steps, each run on its own:
  python -m experiments.urban1_gate lines   --root <root>   (exclusion map only)
  python -m experiments.urban1_gate turning --root <root>   (labels only)
  python -m experiments.urban1_gate check   --root <root>   (image count and size)
  python -m experiments.urban1_gate time    --root <root> --model models/yolox_x.onnx
  python -m experiments.urban1_gate detect  --root <root> --max-minutes 40
    (resumable: repeat the same command until it reports status complete)
  python -m experiments.urban1_gate run     --root <root> --output <json>
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS
from experiments.crossing_rules import cancel_reversals
from experiments.gram_rtm_gate import (
    detect_sequence,
    detector,
    iou,
    keep_outside,
    kit,
    sha256,
)
from experiments.roundabouthd_gate import crossings
from experiments.svmot_gate import digest, id_switches, replay
from visiontrack.core.assignment import linear_assignment

SEQ = "Urban1"
FRAMES, WIDTH, HEIGHT = 23435, 600, 360
WINDOW = 30  # cancel-reversals window, as on M-30; Urban1's frame rate is not stated
MAX_FRAMES = 6
PX_FRACTION = 0.039  # of frame width: 23.4 pixels at 600
AXIS_RATIO = 1.5
MIN_CROSSINGS = 30
IDSW_LIMIT = 0.10
BLOCKS = 5
TURN_DEGREES = 45.0
MIN_MOVE_PX = 20.0
OFFSETS = (-1, 0, 1, 2)
EXPECTED_OFFSET = 1
OFFSET_LEAD = 0.01  # below this lead the expected offset is kept


# --- data -------------------------------------------------------------------------------

def load_labels(root: Path, count: int | None = None) -> dict[int, list[tuple[int, list[float]]]]:
    """Label frame k (from 0) -> [(id, [x1, y1, x2, y2])], every labelled vehicle."""
    count = FRAMES if count is None else count
    out = {}
    for k in range(count):
        tree = ET.parse(kit(root) / "Annotations" / SEQ / "xml" / f"{k}.xml").getroot()
        out[k] = [(int(o.findtext("ID")), [float(o.findtext(f"bndbox/{t}"))
                                           for t in ("xmin", "ymin", "xmax", "ymax")])
                  for o in tree.findall("object")]
    return out


def reference_boxes(labels: dict, offset: int, count: int | None = None) -> dict:
    """{(image frame, id): box} with label k placed on image k + offset."""
    count = FRAMES if count is None else count
    return {(k + offset, ident): box for k, rows in labels.items() for ident, box in rows
            if 1 <= k + offset <= count}


def centres_of(boxes: dict) -> dict:
    return {k: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for k, b in boxes.items()}


def image_members(archive: zipfile.ZipFile) -> list[str]:
    """JPEG members in frame order; their numbers must run without gaps."""
    numbered = []
    for name in archive.namelist():
        if name.lower().endswith(".jpg") and not name.split("/")[-1].startswith("."):
            digits = re.findall(r"\d+", name.split("/")[-1])
            if not digits:
                raise ValueError(f"unnumbered image {name}")
            numbered.append((int(digits[-1]), name))
    numbered.sort()
    numbers = [n for n, _ in numbered]
    if not numbers or numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        raise ValueError("image numbers are missing or not consecutive")
    return [name for _, name in numbered]


def frames_from_zip(root: Path, seq: str, indices):
    """(position from 1, BGR frame) for each requested position."""
    from PIL import Image

    with zipfile.ZipFile(root / "images" / f"{seq}.zip") as archive:
        members = image_members(archive)
        for n in indices:
            rgb = np.asarray(Image.open(io.BytesIO(archive.read(members[n - 1]))).convert("RGB"))
            yield n, rgb[:, :, ::-1].copy()  # BGR, the channel order YOLOX was trained on


def format_check(root: Path) -> dict:
    """Image count must equal the label count; every image must be 600x360."""
    from PIL import Image

    labels = len(list((kit(root) / "Annotations" / SEQ / "xml").glob("*.xml")))
    sizes: dict[str, int] = {}
    with zipfile.ZipFile(root / "images" / f"{SEQ}.zip") as archive:
        members = image_members(archive)
        for name in members:
            with Image.open(io.BytesIO(archive.read(name))) as img:
                key = f"{img.size[0]}x{img.size[1]}"
            sizes[key] = sizes.get(key, 0) + 1
    ok = len(members) == labels == FRAMES and sizes == {f"{WIDTH}x{HEIGHT}": FRAMES}
    return {"images": len(members), "labels": labels, "sizes": sizes, "passed": ok,
            "image_zip_sha256": sha256(root / "images" / f"{SEQ}.zip")}


# --- exclusion map and lines --------------------------------------------------------------

def excluded_mask(root: Path) -> np.ndarray:
    """True where vehicles were not labelled (map darker than 128), at frame size."""
    from PIL import Image

    grey = Image.open(kit(root) / "ROI" / f"{SEQ}-map.jpg").convert("L").resize((WIDTH, HEIGHT))
    return np.asarray(grey) < 128


def _span(pts: np.ndarray, centre: np.ndarray, direction: np.ndarray) -> list[list[float]]:
    proj = (pts - centre) @ direction
    a, b = centre + proj.min() * direction, centre + proj.max() * direction
    return [[round(float(a[0]), 2), round(float(a[1]), 2)],
            [round(float(b[0]), 2), round(float(b[1]), 2)]]


def two_lines(labelled: np.ndarray) -> dict:
    """Two lines through the labelled area's centroid: across and along its principal
    axis, each spanning the area; horizontal and vertical if the axes differ by < 1.5."""
    ys, xs = np.nonzero(labelled)
    if len(xs) < 2:
        raise ValueError("no labelled area in the exclusion map")
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    centre = pts.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov((pts - centre).T))
    major = vectors[:, int(np.argmax(values))]
    ratio = float(np.sqrt(values.max() / max(values.min(), 1e-12)))
    if ratio < AXIS_RATIO:
        across, along, rule = np.array([1.0, 0.0]), np.array([0.0, 1.0]), "horizontal and vertical"
    else:
        across, along, rule = np.array([-major[1], major[0]]), major, "across and along the axis"
    return {"lines": {"across": _span(pts, centre, across), "along": _span(pts, centre, along)},
            "centroid": [round(float(c), 2) for c in centre],
            "axis_ratio": round(ratio, 3), "rule": rule}


# --- turning vehicles -------------------------------------------------------------------

def classify_tracks(centres: dict) -> dict[int, str]:
    """'turning', 'straight' or 'unclassified' per labelled vehicle.

    Direction of the first half = mean centre of its 2nd quarter minus that of its 1st;
    likewise for the second half. Turning if the two differ by more than 45 degrees.
    Unclassified if either half moves less than 20 pixels or the track has < 4 frames.
    """
    tracks: dict[int, list[tuple[int, tuple[float, float]]]] = {}
    for (frame, ident), p in centres.items():
        tracks.setdefault(ident, []).append((frame, p))
    out = {}
    for ident, rows in tracks.items():
        pts = np.array([p for _, p in sorted(rows)], dtype=np.float64)
        if len(pts) < 4:
            out[ident] = "unclassified"
            continue
        q = np.array_split(pts, 4)
        first = q[1].mean(axis=0) - q[0].mean(axis=0)
        second = q[3].mean(axis=0) - q[2].mean(axis=0)
        if min(np.hypot(*first), np.hypot(*second)) < MIN_MOVE_PX:
            out[ident] = "unclassified"
            continue
        angle = abs(math.degrees(math.atan2(second[1], second[0]) -
                                 math.atan2(first[1], first[0])))
        angle = min(angle, 360.0 - angle)
        out[ident] = "turning" if angle > TURN_DEGREES else "straight"
    return out


# --- counting and matching ---------------------------------------------------------------

def count(centres: dict, line, excluded: np.ndarray) -> list[dict]:
    """Cancel-reversals crossings whose point is outside the excluded area."""
    return cancel_reversals(keep_outside(crossings(centres, line), excluded), WINDOW)


def match_pairs(reference: list[dict], predicted: list[dict], max_px: float) -> list[tuple]:
    """One-to-one pairs within the frame and pixel limits (as gram_rtm_gate.match)."""
    if not (reference and predicted):
        return []
    cost = np.zeros((len(reference), len(predicted)))
    for i, r in enumerate(reference):
        for j, p in enumerate(predicted):
            df = abs(r["frame"] - p["frame"])
            dist = ((r["x"] - p["x"]) ** 2 + (r["y"] - p["y"]) ** 2) ** 0.5
            if r["dir"] == p["dir"] and df <= MAX_FRAMES and dist <= max_px:
                cost[i, j] = df - 1000.0
    rows, cols = linear_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(rows, cols, strict=True) if cost[i, j] < 0]


def block_of(frame: int, count: int | None = None) -> int:
    count = FRAMES if count is None else count
    return min(BLOCKS - 1, (frame - 1) * BLOCKS // count)


def score(reference: dict, predicted: dict, kinds: dict, max_px: float) -> dict:
    """Pool both lines. Per block: tp and fn by reference frame, fp by predicted frame.
    Missed crossings are also split by the reference vehicle's turning class."""
    out = {"tp": 0, "fp": 0, "fn": 0, "blocks": [{"tp": 0, "fp": 0, "fn": 0}
                                                 for _ in range(BLOCKS)],
           "missed_by_kind": {"turning": 0, "straight": 0, "unclassified": 0}}
    for name in reference:
        ref, pred = reference[name], predicted[name]
        pairs = match_pairs(ref, pred, max_px)
        hit_r, hit_p = {i for i, _ in pairs}, {j for _, j in pairs}
        for i, r in enumerate(ref):
            key = "tp" if i in hit_r else "fn"
            out[key] += 1
            out["blocks"][block_of(r["frame"])][key] += 1
            if key == "fn":
                out["missed_by_kind"][kinds.get(r["id"], "unclassified")] += 1
        for j, p in enumerate(pred):
            if j not in hit_p:
                out["fp"] += 1
                out["blocks"][block_of(p["frame"])]["fp"] += 1
    return out


def judge(result: dict, candidate: str) -> str:
    if result["reference_crossings"] < MIN_CROSSINGS:
        return "inconclusive"
    on, cand = result["crossings"]["gate_on"], result["crossings"][candidate]
    idsw_on, idsw_c = result["id_switches"]["gate_on"], result["id_switches"][candidate]
    idsw_ok = idsw_c <= idsw_on * (1 + IDSW_LIMIT)
    turning_ok = cand["missed_by_kind"]["turning"] - on["missed_by_kind"]["turning"] <= 2
    allowance = max(2.0, 0.1 * (cand["tp"] - on["tp"]))
    blocks_ok = all(c["fp"] + c["fn"] - o["fp"] - o["fn"] <= 2
                    for o, c in zip(on["blocks"], cand["blocks"], strict=True))
    if (cand["fn"] < on["fn"] and cand["fp"] - on["fp"] <= allowance and blocks_ok and
            turning_ok and idsw_ok):
        return "supported"
    if (cand["fp"] + cand["fn"]) - (on["fp"] + on["fn"]) <= 2 and turning_ok and idsw_ok:
        return "no harm"
    return "harmful"


def prefer(result: dict, verdicts: dict) -> str | None:
    if "inconclusive" in verdicts.values():
        return None
    passing = [v for v in ("aspect_free_gate", "gate_off")
               if verdicts[v] in ("supported", "no harm")]
    if len(passing) < 2:
        return passing[0] if passing else "gate_on"
    c = result["crossings"]
    err = {v: c[v]["fp"] + c[v]["fn"] for v in passing}
    if err["gate_off"] <= 0.9 * err["aspect_free_gate"] and \
            c["gate_off"]["fp"] <= c["aspect_free_gate"]["fp"]:
        return "gate_off"
    return "aspect_free_gate"


# --- steps -----------------------------------------------------------------------------

def lines_step(root: Path) -> dict:
    return two_lines(~excluded_mask(root))


def turning_step(root: Path, offset: int = EXPECTED_OFFSET) -> dict:
    kinds = classify_tracks(centres_of(reference_boxes(load_labels(root), offset)))
    totals = {k: sum(1 for v in kinds.values() if v == k)
              for k in ("turning", "straight", "unclassified")}
    return {"vehicles": len(kinds), **totals}


def time_step(root: Path, model: Path, n: int = 20) -> dict:
    """Time the pinned detector on n spread frames and score the label offsets."""
    det = detector(model)
    labels = load_labels(root)
    indices = [int(round(i)) for i in np.linspace(4, FRAMES - 3, n)]
    start = time.perf_counter()
    found = {i: [d.xyxy.tolist() for d in det.detect(img)]
             for i, img in frames_from_zip(root, SEQ, indices)}
    seconds = time.perf_counter() - start
    offsets = {}
    for off in OFFSETS:  # label k belongs to image k + off
        scores = [max((iou(box, d) for d in found[i]), default=0.0)
                  for i in indices if 0 <= i - off < FRAMES for _, box in labels[i - off]]
        offsets[str(off)] = round(float(np.mean(scores)), 4) if scores else 0.0
    return {"frames": n, "seconds": round(seconds, 2),
            "seconds_per_frame": round(seconds / n, 3),
            "full_run_minutes": round(seconds / n * FRAMES / 60, 1),
            "offset_mean_best_iou": offsets, "offset": choose_offset(offsets)}


def choose_offset(offsets: dict) -> int:
    ranked = sorted(OFFSETS, key=lambda o: offsets[str(o)], reverse=True)
    if offsets[str(ranked[0])] - offsets[str(ranked[1])] < OFFSET_LEAD:
        return EXPECTED_OFFSET
    return int(ranked[0])


def run(root: Path, cache: Path, offset: int = EXPECTED_OFFSET) -> dict:
    receipt = json.loads((cache / f"{SEQ}-detections.json").read_text())
    path = cache / f"{SEQ}-detections.npy"
    if sha256(path) != receipt["detections_sha256"]:
        raise ValueError("detections changed since they were computed")
    array = np.load(path)
    excluded = excluded_mask(root)
    line_info = two_lines(~excluded)  # from the map only, before labels are read
    lines = {k: tuple(tuple(p) for p in v) for k, v in line_info["lines"].items()}
    ref_boxes = reference_boxes(load_labels(root), offset)
    ref_centres = centres_of(ref_boxes)
    kinds = classify_tracks(ref_centres)
    reference = {k: count(ref_centres, line, excluded) for k, line in lines.items()}
    max_px = PX_FRACTION * WIDTH
    result = {"detections": receipt, "offset": offset, "lines": line_info,
              "reference_crossings": sum(map(len, reference.values())),
              "reference_by_kind": {k: sum(1 for evs in reference.values() for e in evs
                                           if kinds.get(e["id"], "unclassified") == k)
                                    for k in ("turning", "straight", "unclassified")},
              "crossings": {}, "id_switches": {}, "public_ids": {}, "output_sha256": {}}
    for variant in VARIANTS:
        boxes = replay(array, FRAMES, variant)
        if digest(boxes) != digest(replay(array, FRAMES, variant)):
            raise ValueError("repeatability mismatch")
        centres = centres_of(boxes)
        predicted = {k: count(centres, line, excluded) for k, line in lines.items()}
        result["crossings"][variant] = score(reference, predicted, kinds, max_px)
        result["id_switches"][variant] = id_switches(ref_boxes, boxes, FRAMES)
        result["public_ids"][variant] = len({k[1] for k in boxes})
        result["output_sha256"][variant] = digest(boxes)
        print(variant, {k: result["crossings"][variant][k] for k in ("tp", "fp", "fn")},
              result["id_switches"][variant], flush=True)
    verdicts = {"aspect_free_gate": judge(result, "aspect_free_gate"),
                "gate_off": judge(result, "gate_off")}
    return {"protocol": "docs/GRAM_RTM_URBAN1_TEST_PROTOCOL.md", "result": result,
            "verdicts": verdicts, "preferred": prefer(result, verdicts)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("lines", "turning", "check", "time", "detect", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("models/yolox_x.onnx"))
    parser.add_argument("--offset", type=int, default=EXPECTED_OFFSET,
                        help="label k belongs to image k + offset (from the time step)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-minutes", type=float,
                        help="detect: start no new part after this many minutes")
    args = parser.parse_args()
    cache = args.root / "gate-cache"
    cache.mkdir(exist_ok=True)
    if args.step == "lines":
        result = lines_step(args.root)
    elif args.step == "turning":
        result = turning_step(args.root, args.offset)
    elif args.step == "check":
        result = format_check(args.root)
    elif args.step == "time":
        result = time_step(args.root, args.model)
    elif args.step == "detect":
        result = detect_sequence(args.root, args.model, SEQ, cache, args.max_minutes,
                                 count=FRAMES, frames=frames_from_zip)
    else:
        result = run(args.root, cache, args.offset)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
