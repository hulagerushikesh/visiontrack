#!/usr/bin/env python3
"""Precompute the DanceTrack detection/GT cache (oracle-perturbed detections).

DanceTrack ships no public detections, so — unlike ``precompute.py`` — detections
are synthesized by perturbing the GT (jitter/drop/FP), isolating the association
question (RQ1) from detector quality. One compressed ``.npz`` per sequence, in the
same schema as the MOT17 cache, so every downstream reader works unchanged.

    python data/cache/precompute_dancetrack.py --data-root ~/Downloads/dancetrack \
        --split val --out data/cache/dancetrack
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
        DanceTrackDetectorSequence,
        DanceTrackSequence,
        discover_dancetrack,
    )
    from visiontrack.detection.noise import NoiseConfig

    parser = argparse.ArgumentParser(description="Precompute DanceTrack cache")
    parser.add_argument("--data-root", required=True, help="DanceTrack root (contains val/)")
    parser.add_argument("--split", default="val")
    parser.add_argument("--out", default="data/cache/dancetrack")
    parser.add_argument("--seed", type=int, default=0, help="perturbation seed (fixes detections)")
    parser.add_argument("--jitter-std", type=float, default=8.0)
    parser.add_argument("--drop-prob", type=float, default=0.15)
    parser.add_argument("--fp-rate", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0, help="cap #sequences (0 = all)")
    # Real-detector mode: run an actual YOLOX ONNX over the frames instead of
    # perturbing the GT — removes the oracle-perturbed caveat from the RQ1 test.
    parser.add_argument("--detector-model", default=None,
                        help="path to a YOLOX ONNX; if set, use REAL detections "
                             "(not perturbed GT). Suggest --out data/cache/dancetrack_yolox")
    parser.add_argument("--input-size", type=int, default=416)
    parser.add_argument("--conf", type=float, default=0.1,
                        help="detector confidence gate (low, to feed ByteTrack's low band)")
    parser.add_argument("--seqs", default=None,
                        help="comma-separated sequence names to include (default: all)")
    args = parser.parse_args(argv)

    seq_dirs = discover_dancetrack(args.data_root, args.split)
    if not seq_dirs:
        print(f"No DanceTrack sequences under {args.data_root}/{args.split}")
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
    print(f"Caching {len(seq_dirs)} DanceTrack sequence(s) ({mode}) -> {out_dir}")
    for seq_dir in seq_dirs:
        if detector is not None:
            seq = DanceTrackDetectorSequence(seq_dir, detector)
        else:
            seq = DanceTrackSequence(seq_dir, noise_cfg=cfg, seed=args.seed)
        out_path = out_dir / f"{seq.name}.npz"
        save_sequence_cache(seq, out_path)
        size = out_path.stat().st_size
        total += size
        print(f"  {seq.name:<18} {seq.info.length:>5} frames  ->  {_human(size)}")

    print(f"\nTotal cache size: {_human(total)}  ({len(seq_dirs)} sequences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
