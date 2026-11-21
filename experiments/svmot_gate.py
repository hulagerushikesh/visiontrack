"""SVMOT motion-gate test (docs/SVMOT_GATE_TEST_PROTOCOL.md).

The dataset stays owner-local. Expected layout under <root>:
  data/<seq>/img/NNNN.jpg      (from 1)
  data/<seq>/gt/gt.txt         (frame, id, left, top, width, height, flag, class, visibility)
  data/<seq>/seqinfo.ini
  data/<seq>/roi_mask.png      (white = labelled road)
  download-receipt.json        (per-file SHA-256 from the range-read)

Steps, each run on its own:
  python -m experiments.svmot_gate lines  --root <root>
  python -m experiments.svmot_gate detect --root <root> --max-minutes 40
    (resumable across all nine sequences: repeat until every one is complete)
  python -m experiments.svmot_gate run    --root <root> --output <json>
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS, make_tracker
from experiments.crossing_rules import cancel_reversals
from experiments.gram_rtm_gate import (
    CHUNK,
    CLASSES,
    CONF,
    INPUT_SIZE,
    MODEL_SHA256,
    NMS,
    detector,
    keep_outside,
    match,
    sha256,
)
from experiments.roundabouthd_gate import crossings
from visiontrack.detection.base import Detection

TEST_SEQUENCES = (
    "seq_22_morning", "seq_23_morning", "seq_24_morning", "seq_25_morning",
    "seq_26_evening", "seq_27_evening", "seq_28_evening", "seq_29_evening", "seq_30_evening",
)
FPS = 30
WINDOW = 30  # cancel-reversals window: one second
MAX_FRAMES = 6  # 0.2 s
PX_FRACTION = 0.039  # of frame width
AXIS_RATIO = 1.5  # below this the mask has no clear direction: horizontal line
MIN_CROSSINGS = 30  # pooled reference crossings needed for a verdict
IDSW_LIMIT = 0.10  # pooled ID switches may rise by at most 10%


def seq_dir(root: Path, seq: str) -> Path:
    return root / "data" / seq


def seq_info(root: Path, seq: str) -> tuple[int, int, int]:
    """(frames, width, height) from seqinfo.ini; the folder name identifies the sequence."""
    parser = configparser.ConfigParser()
    parser.read(seq_dir(root, seq) / "seqinfo.ini")
    s = parser["Sequence"]
    return int(s["seqlength"]), int(s["imwidth"]), int(s["imheight"])


def road_mask(root: Path, seq: str) -> np.ndarray:
    from PIL import Image

    _, width, height = seq_info(root, seq)
    grey = Image.open(seq_dir(root, seq) / "roi_mask.png").convert("L")
    if grey.size != (width, height):
        grey = grey.resize((width, height), Image.NEAREST)
    return np.asarray(grey) >= 128


def line_from_mask(mask: np.ndarray) -> dict:
    """Counting line from the mask alone: through the centroid, perpendicular to the
    principal axis, spanning the mask; horizontal if the axes differ by < AXIS_RATIO."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 2:
        raise ValueError("empty road mask")
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    centre = pts.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov((pts - centre).T))
    major = vectors[:, int(np.argmax(values))]
    ratio = float(np.sqrt(values.max() / max(values.min(), 1e-12)))
    if ratio < AXIS_RATIO:
        direction = np.array([1.0, 0.0])
        rule = "horizontal"
    else:
        direction = np.array([-major[1], major[0]])
        rule = "perpendicular"
    proj = (pts - centre) @ direction
    a, b = centre + proj.min() * direction, centre + proj.max() * direction
    return {"line": [[round(float(a[0]), 2), round(float(a[1]), 2)],
                     [round(float(b[0]), 2), round(float(b[1]), 2)]],
            "centroid": [round(float(c), 2) for c in centre],
            "axis_ratio": round(ratio, 3), "rule": rule}


def load_gt(root: Path, seq: str) -> np.ndarray:
    return np.loadtxt(seq_dir(root, seq) / "gt" / "gt.txt", delimiter=",", ndmin=2)


def gt_boxes(gt: np.ndarray) -> dict:
    """{(frame, id): [x1, y1, x2, y2]} for every labelled row, zero visibility included."""
    return {(int(r[0]), int(r[1])): [r[2], r[3], r[2] + r[4], r[3] + r[5]] for r in gt}


def centres_of(boxes: dict) -> dict:
    return {k: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for k, b in boxes.items()}


def frames_from_folder(root: Path, seq: str, indices):
    from PIL import Image

    folder = seq_dir(root, seq) / "img"
    for n in indices:
        rgb = np.asarray(Image.open(folder / f"{n:04d}.jpg").convert("RGB"))
        yield n, rgb[:, :, ::-1].copy()  # BGR, the channel order YOLOX was trained on


def _part_path(cache: Path, seq: str, first: int, last: int) -> Path:
    return cache / f"{seq}-parts" / f"frames-{first:06d}-{last:06d}.npy"


def images_sha256(root: Path, seq: str) -> str:
    """Hash of the sequence's per-image SHA-256 list from the download receipt."""
    receipt = json.loads((root / "download-receipt.json").read_text())
    files = receipt["sequences"][seq]["sha256"]
    text = json.dumps(sorted((k, v) for k, v in files.items() if k.startswith("img/")))
    return hashlib.sha256(text.encode()).hexdigest()


def finish(root: Path, seq: str, cache: Path, spans, chunk: int) -> dict:
    array = np.concatenate([np.load(_part_path(cache, seq, *s)) for s in spans])
    path = cache / f"{seq}-detections.npy"
    np.save(path, array)
    receipt = {"sequence": seq, "status": "complete", "frames": spans[-1][1],
               "detections": int(len(array)), "parts": len(spans), "chunk": chunk,
               "model_sha256": MODEL_SHA256, "input_size": INPUT_SIZE, "conf": CONF,
               "nms": NMS, "classes": sorted(CLASSES), "preprocessing": "legacy, BGR",
               "images_sha256": images_sha256(root, seq), "detections_sha256": sha256(path)}
    (cache / f"{seq}-detections.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def detect_all(root: Path, model: Path, cache: Path, max_minutes: float | None = None,
               det=None, chunk: int = CHUNK, sequences=TEST_SEQUENCES) -> dict:
    """Detect every frame of every sequence in saved parts; resumable, time-boxed."""
    det = det if det is not None else detector(model)
    start = time.perf_counter()
    status = {}
    for seq in sequences:
        count = seq_info(root, seq)[0]
        spans = [(a, min(a + chunk - 1, count)) for a in range(1, count + 1, chunk)]
        (cache / f"{seq}-parts").mkdir(parents=True, exist_ok=True)
        for i, (first, last) in enumerate(spans, 1):
            path = _part_path(cache, seq, first, last)
            if path.exists():
                continue
            if max_minutes is not None and (time.perf_counter() - start) / 60 >= max_minutes:
                break
            rows = [[n, *map(float, d.xyxy), float(d.score), int(d.class_id)]
                    for n, img in frames_from_folder(root, seq, range(first, last + 1))
                    for d in det.detect(img)]
            tmp = path.with_suffix(".tmp")
            with tmp.open("wb") as handle:
                np.save(handle, np.asarray(rows, dtype=np.float64).reshape(-1, 7))
            tmp.replace(path)
            print(f"{seq}: part {i}/{len(spans)} saved, frames {first}-{last} of {count}, "
                  f"{(time.perf_counter() - start) / 60:.1f} min this session", flush=True)
        done = sum(_part_path(cache, seq, *s).exists() for s in spans)
        if done == len(spans):
            receipt_path = cache / f"{seq}-detections.json"
            status[seq] = (json.loads(receipt_path.read_text()) if receipt_path.exists()
                           else finish(root, seq, cache, spans, chunk))["status"]
        else:
            status[seq] = f"partial {done}/{len(spans)}"
    complete = sum(v == "complete" for v in status.values())
    return {"status": "complete" if complete == len(sequences) else "partial",
            "sequences_complete": complete, "sequences": status}


def replay(array: np.ndarray, count: int, variant: str) -> dict:
    """{(frame, track_id): [x1, y1, x2, y2]} of the public tracker output."""
    tracker = make_tracker(variant)
    by_frame: dict[int, list[Detection]] = {}
    for n, x1, y1, x2, y2, s, c in array:
        by_frame.setdefault(int(n), []).append(
            Detection(np.array([x1, y1, x2, y2]), float(s), int(c)))
    boxes = {}
    for n in range(1, count + 1):
        for o in tracker.update(by_frame.get(n, [])):
            boxes[(n, int(o.track_id))] = [float(v) for v in o.xyxy.tolist()]
    return boxes


def digest(boxes: dict) -> str:
    text = json.dumps(sorted((list(k), v) for k, v in boxes.items()))
    return hashlib.sha256(text.encode()).hexdigest()


def id_switches(reference: dict, tracked: dict, frames: int) -> int:
    """TrackEval CLEAR ID switches at IoU 0.5 over all frames."""
    for name, builtin in (("float", float), ("int", int), ("bool", bool)):
        if not hasattr(np, name):
            setattr(np, name, builtin)
    import trackeval
    from trackeval.datasets._base_dataset import _BaseDataset

    def per_frame(boxes):
        out = {n: ([], []) for n in range(1, frames + 1)}
        for (n, ident), b in sorted(boxes.items()):
            out[n][0].append(ident)
            out[n][1].append(b)
        return out

    gt, tr = per_frame(reference), per_frame(tracked)
    gt_map = {g: i for i, g in enumerate(sorted({k[1] for k in reference}))}
    tr_map = {t: i for i, t in enumerate(sorted({k[1] for k in tracked}))}
    gt_ids, tr_ids, sims = [], [], []
    for n in range(1, frames + 1):
        g_ids, g_boxes = gt[n]
        t_ids, t_boxes = tr[n]
        gt_ids.append(np.array([gt_map[x] for x in g_ids], dtype=int))
        tr_ids.append(np.array([tr_map[x] for x in t_ids], dtype=int))
        sims.append(_BaseDataset._calculate_box_ious(
            np.asarray(g_boxes, dtype=float).reshape(-1, 4),
            np.asarray(t_boxes, dtype=float).reshape(-1, 4), box_format="x0y0x1y1"))
    data = dict(num_gt_ids=len(gt_map), num_tracker_ids=len(tr_map),
                num_gt_dets=len(reference), num_tracker_dets=len(tracked),
                num_timesteps=frames, gt_ids=gt_ids, tracker_ids=tr_ids, similarity_scores=sims)
    clear = trackeval.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    return int(clear["IDSW"])


def count(centres: dict, line, mask: np.ndarray) -> list[dict]:
    """Cancel-reversals crossings whose point lies on the labelled road."""
    return cancel_reversals(keep_outside(crossings(centres, line), ~mask), WINDOW)


def judge(seqs: dict, candidate: str) -> str:
    def get(seq, variant, key):
        return seqs[seq]["crossings"][variant][key]

    names = list(seqs)
    if sum(seqs[s]["crossings"]["reference"] for s in names) < MIN_CROSSINGS:
        return "inconclusive"
    pooled = {v: {k: sum(get(s, v, k) for s in names) for k in ("tp", "fp", "fn")}
              for v in ("gate_on", candidate)}
    idsw = {v: sum(seqs[s]["id_switches"][v] for s in names) for v in ("gate_on", candidate)}
    idsw_ok = idsw[candidate] <= idsw["gate_on"] * (1 + IDSW_LIMIT)
    gain = pooled[candidate]["tp"] - pooled["gate_on"]["tp"]
    allowance = max(2.0, 0.1 * gain)
    errors = {v: pooled[v]["fp"] + pooled[v]["fn"] for v in pooled}
    per_seq_ok = all(get(s, candidate, "fp") + get(s, candidate, "fn") -
                     get(s, "gate_on", "fp") - get(s, "gate_on", "fn") <= 2 for s in names)
    if (pooled[candidate]["fn"] < pooled["gate_on"]["fn"] and
            pooled[candidate]["fp"] - pooled["gate_on"]["fp"] <= allowance and
            per_seq_ok and idsw_ok):
        return "supported"
    if errors[candidate] - errors["gate_on"] <= 2 and idsw_ok:
        return "no harm"
    return "harmful"


def prefer(seqs: dict, verdicts: dict) -> str:
    passing = [v for v in ("aspect_free_gate", "gate_off")
               if verdicts[v] in ("supported", "no harm")]
    if len(passing) < 2:
        return passing[0] if passing else "gate_on"

    def pooled(v, k):
        return sum(seqs[s]["crossings"][v][k] for s in seqs)

    err = {v: pooled(v, "fp") + pooled(v, "fn") for v in passing}
    if err["gate_off"] <= 0.9 * err["aspect_free_gate"] and \
            pooled("gate_off", "fp") <= pooled("aspect_free_gate", "fp"):
        return "gate_off"
    return "aspect_free_gate"


def lines(root: Path) -> dict:
    return {seq: line_from_mask(road_mask(root, seq)) for seq in TEST_SEQUENCES}


def run(root: Path, cache: Path, sequences=TEST_SEQUENCES) -> dict:
    seqs = {}
    for seq in sequences:
        frames, width, _ = seq_info(root, seq)
        receipt = json.loads((cache / f"{seq}-detections.json").read_text())
        path = cache / f"{seq}-detections.npy"
        if sha256(path) != receipt["detections_sha256"]:
            raise ValueError("detections changed since they were computed")
        array = np.load(path)
        mask = road_mask(root, seq)
        line_info = line_from_mask(mask)  # from the mask only, before labels are read
        line = tuple(tuple(p) for p in line_info["line"])
        reference_boxes = gt_boxes(load_gt(root, seq))
        reference = count(centres_of(reference_boxes), line, mask)
        max_px = PX_FRACTION * width
        result = {"detections": receipt, "line": line_info,
                  "crossings": {"reference": len(reference)}, "id_switches": {},
                  "public_ids": {}, "output_sha256": {}}
        for variant in VARIANTS:
            boxes = replay(array, frames, variant)
            if digest(boxes) != digest(replay(array, frames, variant)):
                raise ValueError("repeatability mismatch")
            result["crossings"][variant] = match(reference, count(centres_of(boxes), line, mask),
                                                 max_px)
            result["id_switches"][variant] = id_switches(reference_boxes, boxes, frames)
            result["public_ids"][variant] = len({k[1] for k in boxes})
            result["output_sha256"][variant] = digest(boxes)
        seqs[seq] = result
        print(seq, result["crossings"], result["id_switches"], flush=True)
    verdicts = {"aspect_free_gate": judge(seqs, "aspect_free_gate"),
                "gate_off": judge(seqs, "gate_off")}
    return {"protocol": "docs/SVMOT_GATE_TEST_PROTOCOL.md", "sequences": seqs,
            "verdicts": verdicts, "preferred": prefer(seqs, verdicts)
            if "inconclusive" not in verdicts.values() else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("lines", "detect", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("models/yolox_x.onnx"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-minutes", type=float,
                        help="detect: start no new part after this many minutes")
    args = parser.parse_args()
    cache = args.root / "gate-cache"
    cache.mkdir(exist_ok=True)
    if args.step == "lines":
        result = lines(args.root)
    elif args.step == "detect":
        result = detect_all(args.root, args.model, cache, args.max_minutes)
    else:
        result = run(args.root, cache)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
