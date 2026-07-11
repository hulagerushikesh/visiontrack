#!/usr/bin/env python3
"""Precompute the compact MOT17 detection/GT cache.

Reads raw MOT17 annotations (``det/det.txt``, ``gt/gt.txt``, ``seqinfo.ini``)
once and writes one compressed ``.npz`` per sequence. After this runs, the
multi-GB ``img1/`` frame directories can be deleted — every tracking experiment
reads only the cache.

Usage::

    python data/cache/precompute.py --data-root ~/datasets/MOT17 \
        --split train --detector FRCNN --out data/cache/mot17

Prints the size of each cache file and the total, so you can confirm it is
small (a few MB for all of MOT17-train).
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
    # Make the package importable when run as a plain script from the repo root.
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from visiontrack.datasets.cache import save_sequence_cache
    from visiontrack.detection.mot_loader import MOT17Sequence, discover_sequences

    parser = argparse.ArgumentParser(description="Precompute MOT17 detection cache")
    parser.add_argument("--data-root", required=True, help="path to MOT17 root (contains train/)")
    parser.add_argument("--split", default="train", help="dataset split directory (default: train)")
    parser.add_argument(
        "--detector",
        default="FRCNN",
        choices=["DPM", "FRCNN", "SDP", "all"],
        help="public detector variant to cache (default: FRCNN)",
    )
    parser.add_argument("--out", default="data/cache/mot17", help="output cache directory")
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="keep raw detector scores instead of per-sequence min-max to [0,1]",
    )
    args = parser.parse_args(argv)

    detector = None if args.detector == "all" else args.detector
    seq_dirs = discover_sequences(args.data_root, args.split, detector)
    if not seq_dirs:
        print(f"No sequences found under {args.data_root}/{args.split} (detector={args.detector})")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    print(f"Caching {len(seq_dirs)} sequence(s) -> {out_dir}")
    for seq_dir in seq_dirs:
        seq = MOT17Sequence(seq_dir, normalize_scores=not args.no_normalize)
        out_path = out_dir / f"{seq.name}.npz"
        save_sequence_cache(seq, out_path)
        size = out_path.stat().st_size
        total += size
        print(f"  {seq.name:<18} {seq.info.length:>5} frames  ->  {_human(size)}")

    print(f"\nTotal cache size: {_human(total)}  ({len(seq_dirs)} sequences)")
    print("You can now delete the raw img1/ frame directories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
