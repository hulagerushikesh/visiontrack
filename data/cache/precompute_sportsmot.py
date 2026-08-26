#!/usr/bin/env python3
"""Precompute the SportsMOT detection/GT cache.

SportsMOT (NeurIPS'22) is the second **non-linear-motion** dataset (after
DanceTrack) for RQ2: athletes move fast and change direction sharply, so the
constant-velocity prior is stressed hard — but, unlike dancers, players are
visually distinguishable, so it decouples "non-linear motion" from "uninformative
appearance". It ships in the standard MOT-Challenge layout, so the generic loader
reads it verbatim; one compressed ``.npz`` per sequence in the shared cache schema.

Perturbed-GT (isolates association from detector quality, like the DanceTrack
oracle protocol):

    python data/cache/precompute_sportsmot.py --data-root ~/Downloads/sportsmot \
        --split val --out data/cache/sportsmot

Real detector (detection quality is part of the measurement, like MOT17):

    python data/cache/precompute_sportsmot.py --data-root ~/Downloads/sportsmot \
        --split val --out data/cache/sportsmot_yolox \
        --detector-model models/yolox_nano.onnx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _human(nbytes: int) -> str:
    val = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024 or unit == "GB":
            return f"{val:.1f}{unit}"
        val /= 1024
    return f"{val:.1f}GB"


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from visiontrack.datasets.cache import save_sequence_cache
    from visiontrack.detection.dancetrack_loader import (
        MotDetectorSequence,
        MotSequence,
        discover_mot_sequences,
    )
    from visiontrack.detection.noise import NoiseConfig

    parser = argparse.ArgumentParser(description="Precompute SportsMOT cache")
    parser.add_argument("--data-root", required=True,
                        help="SportsMOT root (contains the split dir)")
    parser.add_argument("--split", default="val")
    parser.add_argument("--out", default="data/cache/sportsmot")
    parser.add_argument("--seed", type=int, default=0, help="perturbation seed (fixes detections)")
    parser.add_argument("--jitter-std", type=float, default=8.0)
    parser.add_argument("--drop-prob", type=float, default=0.15)
    parser.add_argument("--fp-rate", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0, help="cap #sequences (0 = all)")
    parser.add_argument("--detector-model", default=None,
                        help="path to a YOLOX ONNX; if set, use REAL detections "
                             "(not perturbed GT). Suggest --out data/cache/sportsmot_yolox")
    parser.add_argument("--input-size", type=int, default=416)
    parser.add_argument("--conf", type=float, default=0.1,
                        help="detector confidence gate (low, to feed ByteTrack's low band)")
    parser.add_argument("--seqs", default=None,
                        help="comma-separated sequence names to include (default: all)")
    args = parser.parse_args(argv)

    seq_dirs = discover_mot_sequences(args.data_root, args.split)
    if not seq_dirs:
        print(f"No SportsMOT sequences under {args.data_root}/{args.split}")
        return 1
    if args.seqs:
        wanted = {s.strip() for s in args.seqs.split(",")}
        seq_dirs = [d for d in seq_dirs if d.name in wanted]
    if args.limit:
        seq_dirs = seq_dirs[: args.limit]

    detector = None
    if args.detector_model:
        from visiontrack.detection.yolox_onnx import YoloxDetector
        detector = YoloxDetector(args.detector_model, input_size=args.input_size,
                                 conf_threshold=args.conf, class_filter={0})

    cfg = NoiseConfig(jitter_std=args.jitter_std, drop_prob=args.drop_prob, fp_rate=args.fp_rate)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode = f"REAL detector ({Path(args.detector_model).name})" if detector else \
        f"perturbed-GT, seed={args.seed}"
    total = 0
    print(f"Caching {len(seq_dirs)} SportsMOT sequence(s) ({mode}) -> {out_dir}")
    for seq_dir in seq_dirs:
        if detector is not None:
            seq = MotDetectorSequence(seq_dir, detector)
        else:
            seq = MotSequence(seq_dir, noise_cfg=cfg, seed=args.seed)
        out_path = out_dir / f"{seq.name}.npz"
        save_sequence_cache(seq, out_path)
        size = out_path.stat().st_size
        total += size
        print(f"  {seq.name:<22} {seq.info.length:>5} frames  ->  {_human(size)}")

    print(f"\nTotal cache size: {_human(total)}  ({len(seq_dirs)} sequences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
