"""Precompute per-frame global camera translations (RQ4 GMC), cached to disk.

Phase correlation is the only image-touching step; like detections and Re-ID
embeddings it runs **once per sequence** and serializes, so tracking experiments
read the small ``<seq>.gmc.npz`` and never load frames. Frames are downsampled
before correlation (global translation survives downsampling) for speed.

    python data/cache/precompute_gmc.py \
        --frames ~/Downloads/MOT17/train/MOT17-05-FRCNN/img1 \
        --out data/cache/mot17/MOT17-05-FRCNN.gmc.npz

Output: an ``(N, 2)`` float array of ``(sx, sy)`` full-resolution shifts, one per
frame (frame 0 is ``(0, 0)``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from visiontrack.tracking.motion.gmc import estimate_translation, hann_window  # noqa: E402


def _load_gray(path: Path, width: int) -> tuple[np.ndarray, float]:
    from PIL import Image

    img = Image.open(path).convert("L")
    scale = width / img.width
    small = img.resize((width, max(1, round(img.height * scale))))
    return np.asarray(small, dtype=np.float64), scale


def precompute(frames_dir: Path, out: Path, width: int = 320, glob: str = "*.jpg") -> Path:
    paths = sorted(frames_dir.glob(glob))
    if not paths:
        raise FileNotFoundError(f"no frames matching {glob} in {frames_dir}")

    shifts = [(0.0, 0.0)]
    prev, scale = _load_gray(paths[0], width)
    window = hann_window(prev.shape)
    for p in paths[1:]:
        cur, _ = _load_gray(p, width)
        if cur.shape != prev.shape:  # guard against odd sizing
            window = hann_window(cur.shape)
        sx, sy = estimate_translation(prev, cur, window)
        shifts.append((sx / scale, sy / scale))  # back to full-res pixels
        prev = cur

    arr = np.asarray(shifts, dtype=np.float64)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, shifts=arr)
    mag = np.linalg.norm(arr, axis=1)
    print(f"{frames_dir.name}: {len(arr)} frames, mean |shift|={mag.mean():.2f}px, "
          f"max={mag.max():.1f}px -> {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precompute per-frame GMC shifts")
    parser.add_argument("--frames", required=True, help="path to an img1/ frames dir")
    parser.add_argument("--out", required=True, help="output .gmc.npz path")
    parser.add_argument("--width", type=int, default=320, help="downsample width")
    parser.add_argument("--glob", default="*.jpg")
    args = parser.parse_args(argv)
    precompute(Path(args.frames).expanduser(), Path(args.out), args.width, args.glob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
