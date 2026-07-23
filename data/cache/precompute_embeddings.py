#!/usr/bin/env python3
"""Precompute appearance embeddings for cached MOT17 detections.

Reads the detection cache (boxes) written by ``precompute.py``, crops each
detection from the corresponding ``img1`` frame, embeds it, and writes an
``.emb.npz`` whose rows are **aligned one-for-one** with the detection cache.
This is the "compute embeddings once" step: after it runs, appearance
experiments read cached embeddings and never touch images again.

    python data/cache/precompute_embeddings.py --data-root ~/Downloads/MOT17 \
        --detector FRCNN --cache-dir data/cache/mot17 --embedder colorhist

Default embedder is the from-scratch HSV colour histogram (no model download).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def _human(n: int) -> str:
    v = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if v < 1024 or u == "GB":
            return f"{v:.1f}{u}"
        v /= 1024
    return f"{v:.1f}GB"


def _load_image(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from visiontrack.appearance.embedder import make_embedder

    parser = argparse.ArgumentParser(description="Precompute MOT17 appearance embeddings")
    parser.add_argument("--data-root", required=True, help="MOT17 root (contains train/)")
    parser.add_argument("--split", default="train")
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--cache-dir", default="data/cache/mot17", help="detection cache dir")
    parser.add_argument("--embedder", default="colorhist", choices=["colorhist", "spatial", "onnx"])
    parser.add_argument("--model-path", default=None,
                        help="path to a re-ID .onnx (required when --embedder onnx)")
    parser.add_argument("--glob", default=None,
                        help="cache glob (default '*-DETECTOR.npz'; e.g. 'dancetrack*.npz')")
    args = parser.parse_args(argv)

    from visiontrack.detection.dancetrack_loader import frame_filename

    embedder = make_embedder(args.embedder, model_path=args.model_path)
    cache_dir = Path(args.cache_dir)
    pattern = args.glob or f"*-{args.detector}.npz"
    npzs = sorted(cache_dir.glob(pattern))
    npzs = [p for p in npzs if not p.name.endswith(".emb.npz")]
    if not npzs:
        print(f"No detection caches '{pattern}' in {cache_dir}; run the precompute first")
        return 1

    total = 0
    print(f"Embedding {len(npzs)} sequence(s) with '{args.embedder}' (dim={embedder.dim})")
    for npz in npzs:
        with np.load(npz, allow_pickle=False) as z:
            name = str(z["name"])
            det_frame = z["det_frame"]
            det_xyxy = z["det_xyxy"].astype(np.float64)

        img_dir = Path(args.data_root) / args.split / name / "img1"
        feats = np.zeros((det_xyxy.shape[0], embedder.dim), dtype=np.float32)

        # Group detection rows by frame, embed all of a frame's crops at once.
        by_frame: dict[int, list[int]] = {}
        for i, f in enumerate(det_frame.tolist()):
            by_frame.setdefault(int(f), []).append(i)

        for frame_idx, rows in by_frame.items():
            img_path = frame_filename(img_dir, frame_idx)  # 6- or 8-digit, auto
            if img_path is None or not img_path.exists():
                continue
            image = _load_image(img_path)
            rows_arr = np.asarray(rows)
            feats[rows_arr] = embedder.embed(image, det_xyxy[rows_arr]).astype(np.float32)

        out = npz.with_suffix("")  # strip .npz
        out = out.with_name(out.name + f".{args.embedder}.emb.npz")
        np.savez_compressed(out, emb=feats, emb_frame=det_frame.astype(np.int32),
                            embedder=args.embedder, dim=embedder.dim)
        size = out.stat().st_size
        total += size
        print(f"  {name:<18} {det_xyxy.shape[0]:>6} dets -> {_human(size)}")

    print(f"\nTotal embedding cache: {_human(total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
