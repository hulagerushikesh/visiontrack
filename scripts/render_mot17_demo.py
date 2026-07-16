#!/usr/bin/env python3
"""Render the tracker on a real MOT17 clip as an animated GIF.

Runs the from-scratch ByteTracker over a sequence's cached public detections,
draws each confirmed track's box + id over the actual ``img1`` frame, and
assembles a downscaled GIF — the README's real-data hero visual.

    python scripts/render_mot17_demo.py --data-root ~/Downloads/MOT17 \
        --seq MOT17-09-FRCNN --first 263 --last 362 --out assets/mot17_demo.gif
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _color(track_id: int) -> tuple[int, int, int]:
    import colorsys

    hue = (track_id * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.98)
    return int(r * 255), int(g * 255), int(b * 255)


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "src"))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="~/Downloads/MOT17")
    parser.add_argument("--split", default="train")
    parser.add_argument("--seq", default="MOT17-09-FRCNN")
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--first", type=int, default=263)
    parser.add_argument("--last", type=int, default=362)
    parser.add_argument("--scale", type=float, default=0.5, help="downscale factor")
    parser.add_argument("--step", type=int, default=1, help="keep every Nth frame")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--colors", type=int, default=128, help="GIF palette size")
    parser.add_argument("--out", default="assets/mot17_demo.gif")
    args = parser.parse_args(argv)

    from PIL import Image, ImageDraw

    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    cache = CachedSequence(Path(args.cache_dir) / f"{args.seq}.npz")
    img_dir = Path(args.data_root).expanduser() / args.split / args.seq / "img1"
    tracker = ByteTracker(TrackerConfig())

    frames = []
    for idx in range(args.first, args.last + 1):
        obs = tracker.update(cache.frame(idx).detections())
        if (idx - args.first) % args.step != 0:
            continue
        img_path = img_dir / f"{idx:06d}.jpg"
        if not img_path.exists():
            continue
        with Image.open(img_path) as im:
            im = im.convert("RGB")
            w, h = int(im.width * args.scale), int(im.height * args.scale)
            im = im.resize((w, h))
        draw = ImageDraw.Draw(im)
        for o in obs:
            x1, y1, x2, y2 = (o.xyxy * args.scale).tolist()
            color = _color(o.track_id)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            label = f"#{o.track_id}"
            ty = max(0, y1 - 12)
            draw.rectangle([x1, ty, x1 + 8 * len(label), ty + 12], fill=color)
            draw.text((x1 + 1, ty), label, fill=(0, 0, 0))
        draw.text((5, 5), f"{args.seq}  frame {idx}", fill=(255, 255, 0))
        frames.append(im)

    if not frames:
        print("No frames rendered — check --data-root / img1 path.")
        return 1

    # Quantize to a shared adaptive palette — keeps the GIF small enough for a
    # README (full-colour photo frames are otherwise huge).
    pal = frames[0].quantize(colors=args.colors, method=Image.MEDIANCUT)
    frames = [f.quantize(colors=args.colors, palette=pal, dither=Image.NONE) for f in frames]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out, save_all=True, append_images=frames[1:],
        duration=int(1000 / args.fps), loop=0, optimize=True,
    )
    size_mb = out.stat().st_size / 1e6
    print(f"wrote {len(frames)} frames -> {out}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
