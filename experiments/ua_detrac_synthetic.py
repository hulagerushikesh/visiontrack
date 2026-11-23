"""Made-up UA-DETRAC-shaped files for timing the gate runner (plan item B4).

Nothing here comes from UA-DETRAC. It writes files in the layout that
experiments/ua_detrac_gate.py expects, at the size the dataset paper gives for
the test split: 40 sequences and about 56,000 frames at 960x540, with about
nine labelled vehicles per frame. The numbers it produces mean nothing; the
point is how long a full run takes and how much memory it uses.

  python -m experiments.ua_detrac_synthetic --root <empty folder>
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

WIDTH, HEIGHT = 960, 540
SETS = ("R-CNN",)  # the first set in the runner's order; its scores stay in [0, 1]


def sequence_lengths(count: int, total: int, rng: np.random.Generator) -> list[int]:
    raw = rng.uniform(0.5, 1.5, count)
    lengths = np.maximum(1, np.round(raw / raw.sum() * total)).astype(int)
    lengths[-1] += total - int(lengths.sum())
    return lengths.tolist()


def vehicles(frames: int, per_frame: float, rng: np.random.Generator) -> dict:
    """{(frame, id): [x1, y1, x2, y2]} for vehicles driving down or up the image."""
    boxes: dict = {}
    next_id = 1
    live: list[dict] = []
    for n in range(1, frames + 1):
        while len(live) < rng.poisson(per_frame):
            down = rng.random() < 0.5
            live.append({"id": next_id, "x": rng.uniform(80, WIDTH - 160),
                         "y": 0.0 if down else float(HEIGHT),
                         "vy": rng.uniform(2, 9) * (1 if down else -1),
                         "aspect": rng.uniform(1.1, 1.8)})
            next_id += 1
        kept = []
        for v in live:
            v["y"] += v["vy"]
            h = 20 + 80 * min(max(v["y"], 0.0), HEIGHT) / HEIGHT  # nearer is bigger
            w = h * v["aspect"]
            if -h < v["y"] < HEIGHT + h:
                boxes[(n, v["id"])] = [v["x"], v["y"] - h / 2, v["x"] + w, v["y"] + h / 2]
                kept.append(v)
        live = kept
    return boxes


def write_annotation(path: Path, name: str, frames: int, boxes: dict) -> None:
    by_frame: dict[int, list] = {}
    for (n, tid), (x1, y1, x2, y2) in boxes.items():
        by_frame.setdefault(n, []).append((tid, x1, y1, x2 - x1, y2 - y1))
    lines = ['<?xml version="1.0" encoding="utf-8"?>', f'<sequence name="{name}">',
             '<ignored_region><box left="0" top="0" width="60" height="120"/></ignored_region>']
    for n in range(1, frames + 1):
        targets = "".join(
            f'<target id="{tid}"><box left="{x:.2f}" top="{y:.2f}" '
            f'width="{w:.2f}" height="{h:.2f}"/></target>'
            for tid, x, y, w, h in sorted(by_frame.get(n, [])))
        lines.append(f'<frame density="{len(by_frame.get(n, []))}" num="{n}">'
                     f"<target_list>{targets}</target_list></frame>")
    lines.append("</sequence>")
    path.write_text("\n".join(lines) + "\n")


def write_detections(path: Path, frames: int, boxes: dict, rng: np.random.Generator) -> None:
    rows = []
    for (n, _), (x1, y1, x2, y2) in sorted(boxes.items()):
        if rng.random() < 0.1:  # missed detection
            continue
        jitter = rng.normal(0, 1.5, 4)
        x, y = x1 + jitter[0], y1 + jitter[1]
        w, h = max(4.0, x2 - x1 + jitter[2]), max(4.0, y2 - y1 + jitter[3])
        rows.append((n, x, y, w, h, rng.uniform(0.3, 1.0)))
    for n in range(1, frames + 1):  # a few low-score false boxes per frame
        for _ in range(rng.poisson(3)):
            rows.append((n, rng.uniform(0, WIDTH - 60), rng.uniform(0, HEIGHT - 40),
                         rng.uniform(20, 60), rng.uniform(15, 40), rng.uniform(0.0, 0.5)))
    rows.sort(key=lambda r: r[0])
    counter: dict[int, int] = {}
    out = []
    for n, x, y, w, h, s in rows:
        counter[n] = counter.get(n, 0) + 1
        out.append(f"{n},{counter[n]},{x:.2f},{y:.2f},{w:.2f},{h:.2f},{s:.4f}")
    path.write_text("\n".join(out) + "\n")


def build(root: Path, sequences: int = 40, total_frames: int = 56_000,
          per_frame: float = 9.0, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    (root / "annotations").mkdir(parents=True, exist_ok=False)
    for det_set in SETS:
        (root / "detections" / det_set).mkdir(parents=True)
    labels = 0
    for i, frames in enumerate(sequence_lengths(sequences, total_frames, rng)):
        name = f"SYN_{i + 1:03d}"
        boxes = vehicles(frames, per_frame, rng)
        labels += len(boxes)
        write_annotation(root / "annotations" / f"{name}.xml", name, frames, boxes)
        for det_set in SETS:
            write_detections(root / "detections" / det_set / f"{name}_Det_{det_set}.txt",
                             frames, boxes, rng)
    return {"sequences": sequences, "frames": total_frames, "label_rows": labels}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sequences", type=int, default=40)
    parser.add_argument("--frames", type=int, default=56_000)
    args = parser.parse_args()
    print(build(args.root, args.sequences, args.frames))


if __name__ == "__main__":
    main()
