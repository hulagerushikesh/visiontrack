"""GRAM-RTM backup motion-gate test (docs/GRAM_RTM_TEST_PROTOCOL.md).

The dataset stays owner-local. Expected layout under <root>:
  extracted/GRAM-RTMv4/Annotations/<seq>/xml/<k>.xml   (labels, from 0)
  extracted/GRAM-RTMv4/Results/Detection/<seq>/detection_results.txt (2013, from 1)
  extracted/GRAM-RTMv4/ROI/<seq>-map.jpg
  images/<seq>.zip  holding <seq>/imageNNNNNN.jpg (from 1)

Steps, each run on its own:
  python -m experiments.gram_rtm_gate offset --root <root>
  python -m experiments.gram_rtm_gate time   --root <root> --model models/yolox_x.onnx
  python -m experiments.gram_rtm_gate detect --root <root> --seq M-30 \
      --max-minutes 40
    (resumable: repeat the same command until it reports status complete)
  python -m experiments.gram_rtm_gate run    --root <root> --output <json>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

from experiments.aspect_gate import VARIANTS, make_tracker
from experiments.crossing_rules import cancel_reversals
from experiments.roundabouthd_gate import crossings
from visiontrack.core.assignment import linear_assignment
from visiontrack.detection.base import Detection

SEQUENCES = {"M-30": (7520, 800, 480), "M-30-HD": (9390, 1200, 720)}
MODEL_SHA256 = "c892d7aaf1c4746d8a4d675bec669a4db4f434b4ee1efb654bc9b353379c7c55"
INPUT_SIZE, CONF, NMS = 640, 0.10, 0.45
CLASSES = {2, 3, 5, 7}  # COCO car, motorcycle, bus, truck
FPS = 30
WINDOW = 30  # cancel-reversals window: one second
MAX_FRAMES = 6  # 0.2 s
PX_FRACTION = 0.039  # of frame width
OFFSETS = (-1, 0, 1, 2)
EXPECTED_OFFSET = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def kit(root: Path) -> Path:
    return root / "extracted" / "GRAM-RTMv4"


def load_labels(root: Path, seq: str) -> dict[int, list[tuple[int, list[float]]]]:
    """Label frame k (from 0) -> [(id, [x1, y1, x2, y2])]."""
    count = SEQUENCES[seq][0]
    out = {}
    for k in range(count):
        tree = ET.parse(kit(root) / "Annotations" / seq / "xml" / f"{k}.xml").getroot()
        out[k] = [(int(o.findtext("ID")), [float(o.findtext(f"bndbox/{t}"))
                                           for t in ("xmin", "ymin", "xmax", "ymax")])
                  for o in tree.findall("object")]
    return out


def iou(a, b) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def offset_check(root: Path) -> dict:
    """Mean best IoU of label boxes against the authors' 2013 detections per offset."""
    result = {}
    for seq, (count, _, _) in SEQUENCES.items():
        labels = load_labels(root, seq)
        authors: dict[int, list[list[float]]] = {}
        path = kit(root) / "Results" / "Detection" / seq / "detection_results.txt"
        for line in path.read_text().splitlines():
            if line.strip():
                f, x1, y1, x2, y2, _ = line.split()
                authors.setdefault(int(f), []).append([float(x1), float(y1), float(x2), float(y2)])
        sample = [int(round(i)) for i in np.linspace(2, count - 3, 200)]
        result[seq] = {}
        for off in OFFSETS:
            scores = [max((iou(box, d) for d in authors.get(k + off, [])), default=0.0)
                      for k in sample for _, box in labels[k]]
            result[seq][str(off)] = round(float(np.mean(scores)), 4)
        result[seq]["best"] = int(max(OFFSETS, key=lambda o: result[seq][str(o)]))
    return result


def frames_from_zip(root: Path, seq: str, indices):
    from PIL import Image

    with zipfile.ZipFile(root / "images" / f"{seq}.zip") as archive:
        for n in indices:
            data = archive.read(f"{seq}/image{n:06d}.jpg")
            rgb = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
            yield n, rgb[:, :, ::-1].copy()  # BGR, the channel order YOLOX was trained on


def detector(model: Path):
    from visiontrack.detection.yolox_onnx import YoloxDetector

    if sha256(model) != MODEL_SHA256:
        raise ValueError("detector model fingerprint mismatch")
    return YoloxDetector(str(model), input_size=INPUT_SIZE, conf_threshold=CONF,
                         iou_threshold=NMS, class_filter=CLASSES)


def time_detector(root: Path, model: Path, n: int = 20) -> dict:
    """Time the pinned detector; also repeat the offset check with its boxes."""
    det = detector(model)
    out = {}
    for seq, (count, _, _) in SEQUENCES.items():
        labels = load_labels(root, seq)
        indices = [int(round(i)) for i in np.linspace(4, count - 3, n)]
        start = time.perf_counter()
        found = {i: [d.xyxy.tolist() for d in det.detect(img)]
                 for i, img in frames_from_zip(root, seq, indices)}
        seconds = time.perf_counter() - start
        offsets = {}
        for off in OFFSETS:  # label k belongs to image k + off
            scores = [max((iou(box, d) for d in found[i]), default=0.0)
                      for i in indices for _, box in labels[i - off]]
            offsets[str(off)] = round(float(np.mean(scores)), 4)
        out[seq] = {"frames": n, "seconds": round(seconds, 2),
                    "seconds_per_frame": round(seconds / n, 3),
                    "boxes": sum(map(len, found.values())),
                    "full_run_minutes": round(seconds / n * count / 60, 1),
                    "offset_mean_best_iou": offsets,
                    "best_offset": int(max(OFFSETS, key=lambda o: offsets[str(o)]))}
    out["total_full_run_minutes"] = round(sum(v["full_run_minutes"] for v in out.values()), 1)
    return out


CHUNK = 500  # frames per saved part, so a stopped run loses at most one part


def _part_path(cache: Path, seq: str, first: int, last: int) -> Path:
    return cache / f"{seq}-parts" / f"frames-{first:06d}-{last:06d}.npy"


def detect_sequence(root: Path, model: Path, seq: str, cache: Path,
                    max_minutes: float | None = None, det=None, chunk: int = CHUNK) -> dict:
    """Detect every frame, saving one part per `chunk` frames.

    Parts already on disk are skipped, so a stopped run resumes where it left
    off. With `max_minutes`, no new part starts once that time has passed. The
    final detections file and receipt are written only when every part exists.
    """
    det = det if det is not None else detector(model)
    count = SEQUENCES[seq][0]
    spans = [(a, min(a + chunk - 1, count)) for a in range(1, count + 1, chunk)]
    (cache / f"{seq}-parts").mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    for i, (first, last) in enumerate(spans, 1):
        path = _part_path(cache, seq, first, last)
        if path.exists():
            continue
        minutes = (time.perf_counter() - start) / 60
        if max_minutes is not None and minutes >= max_minutes:
            break
        rows = [[n, *map(float, d.xyxy), float(d.score), int(d.class_id)]
                for n, img in frames_from_zip(root, seq, range(first, last + 1))
                for d in det.detect(img)]
        tmp = path.with_suffix(".tmp")
        with tmp.open("wb") as handle:
            np.save(handle, np.asarray(rows, dtype=np.float64).reshape(-1, 7))
        tmp.replace(path)  # a part exists only once fully written
        print(f"{seq}: part {i}/{len(spans)} saved, frames {first}-{last} of {count}, "
              f"{(time.perf_counter() - start) / 60:.1f} min this session", flush=True)
    done = [s for s in spans if _part_path(cache, seq, *s).exists()]
    if len(done) < len(spans):
        return {"sequence": seq, "status": "partial", "parts_done": len(done),
                "parts_total": len(spans), "frames_done": sum(b - a + 1 for a, b in done)}
    array = np.concatenate([np.load(_part_path(cache, seq, *s)) for s in spans])
    path = cache / f"{seq}-detections.npy"
    np.save(path, array)
    receipt = {"sequence": seq, "status": "complete", "frames": count,
               "detections": int(len(array)), "parts": len(spans), "chunk": chunk,
               "model_sha256": MODEL_SHA256, "input_size": INPUT_SIZE, "conf": CONF,
               "nms": NMS, "classes": sorted(CLASSES), "preprocessing": "legacy, BGR",
               "image_zip_sha256": sha256(root / "images" / f"{seq}.zip"),
               "detections_sha256": sha256(path)}
    (cache / f"{seq}-detections.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def replay(array: np.ndarray, count: int, variant: str) -> dict:
    tracker = make_tracker(variant)
    by_frame: dict[int, list[Detection]] = {}
    for n, x1, y1, x2, y2, s, c in array:
        by_frame.setdefault(int(n), []).append(
            Detection(np.array([x1, y1, x2, y2]), float(s), int(c)))
    centres = {}
    for n in range(1, count + 1):
        for o in tracker.update(by_frame.get(n, [])):
            x1, y1, x2, y2 = o.xyxy.tolist()
            centres[(n, int(o.track_id))] = ((x1 + x2) / 2, (y1 + y2) / 2)
    return centres


def digest(centres: dict) -> str:
    text = json.dumps(sorted((list(k), list(v)) for k, v in centres.items()))
    return hashlib.sha256(text.encode()).hexdigest()


def excluded_mask(root: Path, seq: str) -> np.ndarray:
    from PIL import Image

    _, width, height = SEQUENCES[seq]
    grey = Image.open(kit(root) / "ROI" / f"{seq}-map.jpg").convert("L").resize((width, height))
    return np.asarray(grey) < 128


def keep_outside(events: list[dict], mask: np.ndarray) -> list[dict]:
    h, w = mask.shape
    return [e for e in events
            if not mask[min(h - 1, max(0, int(e["y"]))), min(w - 1, max(0, int(e["x"])))]]


def match(reference: list[dict], predicted: list[dict], max_px: float) -> dict:
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


def count(centres: dict, line, mask: np.ndarray) -> dict[str, list[dict]]:
    plain = keep_outside(crossings(centres, line), mask)
    return {"cancel": cancel_reversals(plain, WINDOW), "plain": plain}


def judge(seqs: dict, candidate: str, rule: str = "cancel") -> str:
    def get(seq, variant, key):
        return seqs[seq]["main"][rule][variant][key]

    names = list(seqs)
    pooled = {v: {k: sum(get(s, v, k) for s in names) for k in ("tp", "fp", "fn")}
              for v in ("gate_on", candidate)}
    gain = pooled[candidate]["tp"] - pooled["gate_on"]["tp"]
    allowance = max(2.0, 0.1 * gain)
    errors = {v: pooled[v]["fp"] + pooled[v]["fn"] for v in pooled}
    per_seq_ok = all(get(s, candidate, "fp") + get(s, candidate, "fn") -
                     get(s, "gate_on", "fp") - get(s, "gate_on", "fn") <= 2 for s in names)
    if (pooled[candidate]["fn"] < pooled["gate_on"]["fn"] and
            pooled[candidate]["fp"] - pooled["gate_on"]["fp"] <= allowance and per_seq_ok):
        return "supported"
    if errors[candidate] - errors["gate_on"] <= 2:
        return "no harm"
    return "harmful"


def run(root: Path, cache: Path) -> dict:
    seqs = {}
    for seq, (frames, width, height) in SEQUENCES.items():
        receipt = json.loads((cache / f"{seq}-detections.json").read_text())
        path = cache / f"{seq}-detections.npy"
        if sha256(path) != receipt["detections_sha256"]:
            raise ValueError("detections changed since they were computed")
        array = np.load(path)
        labels = load_labels(root, seq)
        reference_centres = {(k + EXPECTED_OFFSET, ident): ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                             for k, rows in labels.items() for ident, b in rows}
        mask = excluded_mask(root, seq)
        max_px = PX_FRACTION * width
        lines = {name: ((0.0, frac * height), (float(width), frac * height))
                 for name, frac in (("main", 0.5), ("at_40", 0.4), ("at_60", 0.6))}
        tracked = {}
        for variant in VARIANTS:
            first = replay(array, frames, variant)
            if digest(first) != digest(replay(array, frames, variant)):
                raise ValueError("repeatability mismatch")
            tracked[variant] = first
        seqs[seq] = {"detections": receipt}
        for name, line in lines.items():
            reference = count(reference_centres, line, mask)
            seqs[seq][name] = {r: {"reference": len(reference[r])} for r in reference}
            for variant, centres in tracked.items():
                predicted = count(centres, line, mask)
                for r in reference:
                    seqs[seq][name][r][variant] = match(reference[r], predicted[r], max_px)
        seqs[seq]["public_ids"] = {v: len({k[1] for k in c}) for v, c in tracked.items()}
        seqs[seq]["output_sha256"] = {v: digest(c) for v, c in tracked.items()}
        print(seq, seqs[seq]["main"]["cancel"], flush=True)
    verdicts = {"aspect_free_gate": judge(seqs, "aspect_free_gate"),
                "gate_off": judge(seqs, "gate_off")}
    return {"protocol": "docs/GRAM_RTM_TEST_PROTOCOL.md", "sequences": seqs,
            "verdicts": verdicts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("offset", "time", "detect", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("models/yolox_x.onnx"))
    parser.add_argument("--seq", choices=tuple(SEQUENCES))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-minutes", type=float,
                        help="detect: start no new part after this many minutes")
    args = parser.parse_args()
    cache = args.root / "gate-cache"
    cache.mkdir(exist_ok=True)
    if args.step == "offset":
        result = offset_check(args.root)
    elif args.step == "time":
        result = time_detector(args.root, args.model)
    elif args.step == "detect":
        result = detect_sequence(args.root, args.model, args.seq, cache, args.max_minutes)
    else:
        result = run(args.root, cache)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
