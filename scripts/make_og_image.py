#!/usr/bin/env python3
"""Generate the Open-Graph / social preview card (``assets/og-image.png``).

A 1200x630 branded card (the size Facebook/LinkedIn/Twitter/Slack expect) that
renders when ``visiontrack.hulage.in`` is shared. It is drawn from scratch with
Pillow — a dark card matching the site theme, the wordmark, the headline, a
synthetic tracking motif (coloured boxes with per-object id chips, mirroring what
the tracker actually emits), and the URL. License-clean: nothing but generated
shapes and text, no real imagery.

    python scripts/make_og_image.py

Reproducible: the motif uses a fixed RNG seed, so re-running is byte-stable.
Requires Pillow (the ``[viz]`` / ``[appearance]`` / ``[video]`` extra).
"""
from __future__ import annotations

import colorsys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "assets" / "og-image.png"

W, H = 1200, 630
SCALE = 2  # supersample then downscale for crisp anti-aliased text/edges

# Site dark theme (web/index.html :root dark).
BG = (11, 14, 20)
SURFACE = (20, 25, 34)
BORDER = (38, 48, 60)
INK = (231, 235, 241)
INK2 = (183, 192, 205)
MUTED = (135, 146, 161)
ACCENT = (90, 162, 255)
GOOD = (55, 192, 126)

# Candidate system fonts, most-preferred first; falls back to Pillow's default.
_SANS = ["/System/Library/Fonts/Supplemental/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf"]
_SANS_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "Arial Bold.ttf"]
_MONO = ["/System/Library/Fonts/Menlo.ttc",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "Menlo.ttc"]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _color_for_id(i: int) -> tuple[int, int, int]:
    """Golden-ratio hue palette — the same idea the tracker uses for track ids."""
    h = (i * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.62, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def _rounded(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def _motif(draw: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int) -> None:
    """A synthetic tracking scene: coloured boxes with id chips + faint trails.

    Mirrors the tracker's real output (boxes in, stable per-id colours out) so the
    card previews the thing itself, not a stock graphic. Fixed seed => stable.
    """
    _rounded(draw, (x0, y0, x0 + w, y0 + h), 20 * SCALE, fill=(6, 8, 12),
             outline=BORDER, width=2 * SCALE)
    # faint dot grid inside the "screen"
    step = 34 * SCALE
    for gx in range(x0 + step, x0 + w, step):
        for gy in range(y0 + step, y0 + h, step):
            draw.point((gx, gy), fill=(28, 35, 46))

    rng = np.random.default_rng(7)
    chip_font = _font(_MONO, 15 * SCALE)
    n = 6
    for i in range(n):
        bw = rng.integers(60, 96) * SCALE
        bh = int(bw * rng.uniform(1.7, 2.2))
        bx = int(x0 + 26 * SCALE + rng.uniform(0, w - bw - 52 * SCALE))
        by = int(y0 + 26 * SCALE + rng.uniform(0, h - bh - 52 * SCALE))
        col = _color_for_id(i + 1)
        # motion trail: a few fading ghost boxes trailing up-left
        for t in range(1, 4):
            gx = bx - t * 12 * SCALE
            gy = by - t * 5 * SCALE
            fade = tuple(int(c * (0.16 + 0.04 * (3 - t))) for c in col)
            draw.rectangle((gx, gy, gx + bw, gy + bh), outline=fade, width=1 * SCALE)
        draw.rectangle((bx, by, bx + bw, by + bh), outline=col, width=3 * SCALE)
        # id chip in the top-left corner of the box
        label = f"ID {i + 1}"
        tb = draw.textbbox((0, 0), label, font=chip_font)
        cw, ch = tb[2] - tb[0], tb[3] - tb[1]
        pad = 6 * SCALE
        _rounded(draw, (bx, by - ch - 2 * pad, bx + cw + 2 * pad, by), 6 * SCALE, fill=col)
        draw.text((bx + pad, by - ch - pad - tb[1]), label, font=chip_font, fill=(6, 8, 12))


def main() -> int:
    img = Image.new("RGB", (W * SCALE, H * SCALE), BG)
    d = ImageDraw.Draw(img)

    # subtle top accent hairline
    d.rectangle((0, 0, W * SCALE, 6 * SCALE), fill=ACCENT)

    pad = 64 * SCALE
    # ---- wordmark ----
    dot_r = 9 * SCALE
    cy = pad + 12 * SCALE
    d.ellipse((pad, cy - dot_r, pad + 2 * dot_r, cy + dot_r), fill=ACCENT)
    mark_font = _font(_MONO, 26 * SCALE)
    d.text((pad + 2 * dot_r + 16 * SCALE, cy - 18 * SCALE), "VisionTrack",
           font=mark_font, fill=INK)

    # ---- headline (left column) ----
    hx = pad
    hy = pad + 92 * SCALE
    head_font = _font(_SANS_BOLD, 58 * SCALE)
    for i, line in enumerate(["When do the field's",
                              "standard tricks",
                              "actually help tracking?"]):
        d.text((hx, hy + i * 70 * SCALE), line, font=head_font, fill=INK)

    sub_font = _font(_SANS, 25 * SCALE)
    sy = hy + 3 * 70 * SCALE + 26 * SCALE
    for i, line in enumerate(["A from-scratch NumPy multi-object tracker,",
                              "used as a reproducible, significance-tested study."]):
        d.text((hx, sy + i * 34 * SCALE), line, font=sub_font, fill=INK2)

    # ---- fact chips ----
    chip_font = _font(_MONO, 18 * SCALE)
    chips = [("Kalman · Hungarian · ByteTrack", INK2),
             ("333 tests · cross-checked", GOOD)]
    cxy = sy + 2 * 34 * SCALE + 34 * SCALE
    cx = hx
    for text, tint in chips:
        tb = d.textbbox((0, 0), text, font=chip_font)
        cw = tb[2] - tb[0]
        box = (cx, cxy, cx + cw + 34 * SCALE, cxy + 40 * SCALE)
        _rounded(d, box, 10 * SCALE, fill=SURFACE, outline=BORDER, width=2 * SCALE)
        d.text((cx + 17 * SCALE, cxy + 9 * SCALE), text, font=chip_font, fill=tint)
        cx = box[2] + 14 * SCALE

    # ---- tracking motif (right column) ----
    mw, mh = 380 * SCALE, 400 * SCALE
    mx = W * SCALE - pad - mw
    my = pad + 78 * SCALE
    _motif(d, mx, my, mw, mh)

    # ---- footer URL ----
    url_font = _font(_MONO, 22 * SCALE)
    ub = d.textbbox((0, 0), "visiontrack.hulage.in", font=url_font)
    d.text((pad, H * SCALE - pad - (ub[3] - ub[1]) - 6 * SCALE),
           "visiontrack.hulage.in", font=url_font, fill=ACCENT)
    tag = "from-scratch · numpy-only core · MIT"
    tb = d.textbbox((0, 0), tag, font=url_font)
    d.text((W * SCALE - pad - (tb[2] - tb[0]), H * SCALE - pad - (tb[3] - tb[1]) - 6 * SCALE),
           tag, font=url_font, fill=MUTED)

    out = img.resize((W, H), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
