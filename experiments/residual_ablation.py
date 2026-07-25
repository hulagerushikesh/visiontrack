"""RQ2 tracking-level ablation: Kalman vs Kalman+residual, per dataset.

Runs the tracker with and without the learned motion residual on the cached
sequences and reports the paired Δ per metric. The isolated trajectory result
(experiments/train_residual.py) predicts the residual helps on DanceTrack
(non-linear) and is neutral-to-harmful on MOT17 (near-linear); this checks
whether that carries through to tracking metrics.

    python -m experiments.residual_ablation --model models/motion_residual.npz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.datasets.cache import CachedSequence  # noqa: E402
from visiontrack.datasets.splits import load_split  # noqa: E402
from visiontrack.eval.mot17 import evaluate_frames, run_sequence  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402

METRICS = ["HOTA", "IDF1", "AssA", "MOTA", "IDSW"]


def _ablate(name: str, readers_ranges, model: str):
    off = {m: [] for m in METRICS}
    on = {m: [] for m in METRICS}
    for r, (a, b) in readers_ranges:
        mo = evaluate_frames(run_sequence(r, TrackerConfig(), a, b))
        mr = evaluate_frames(run_sequence(r, TrackerConfig(motion_residual_path=model), a, b))
        for m in METRICS:
            off[m].append(mo[m])
            on[m].append(mr[m])
    print(f"\n{name} ({len(readers_ranges)} seqs) — Δ = residual − baseline; * = p<0.05")
    for m in METRICS:
        c = compare(on[m], off[m], seed=0)
        star = "*" if c.p_wilcoxon < 0.05 else " "
        base = np.mean(off[m])
        print(f"  {m:<5} base {base:+8.3f}   Δ {c.delta:+7.3f}  p{c.p_wilcoxon:.2f}{star}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ2 residual tracking ablation")
    parser.add_argument("--model", default="models/motion_residual.npz")
    args = parser.parse_args(argv)

    dt = [(CachedSequence(p), (1, len(CachedSequence(p))))
          for p in sorted(Path("data/cache/dancetrack").glob("dancetrack*.npz"))
          if not p.name.endswith(".emb.npz")]
    if dt:
        _ablate("DanceTrack", dt, args.model)

    split = load_split("mot17_val_half")
    mot = []
    for vid in split.video_ids():
        p = Path("data/cache/mot17") / f"{vid}-FRCNN.npz"
        if p.exists():
            r = CachedSequence(p)
            a, b = split.range_for(r.name, "val")
            mot.append((r, (a, b)))
    if mot:
        _ablate("MOT17-FRCNN val", mot, args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
