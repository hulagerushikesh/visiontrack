"""RQ4: does global motion compensation (GMC) help — and *when*?

Hypothesis: GMC helps on **moving-camera** sequences (the tracker's static-camera
prediction is wrong there) and is a no-op on **static-camera** sequences. MOT17
gives a clean natural contrast: 05/10/11/13 are handheld/moving, 02/04/09 are
static. We run the from-scratch phase-correlation GMC (translation-only) on/off
over the val-half of each sequence and compare per group.

    python -m experiments.gmc_study --detector FRCNN

Reads the detection caches (data/cache/mot17) and the GMC caches
(<seq>.gmc.npz from data/cache/precompute_gmc.py). Sequences without a GMC cache
are skipped with a note.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from visiontrack.datasets.cache import CachedSequence  # noqa: E402
from visiontrack.datasets.splits import load_split  # noqa: E402
from visiontrack.eval.mot17 import evaluate_frames, run_sequence  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402

MOVING = ["MOT17-05", "MOT17-10", "MOT17-11", "MOT17-13"]
STATIC = ["MOT17-02", "MOT17-04", "MOT17-09"]
_METRICS = ["MOTA", "IDF1", "HOTA", "IDSW"]


def _run(seq_base, detector, cache_dir, split, use_gmc):
    name = f"{seq_base}-{detector}"
    det = Path(cache_dir) / f"{name}.npz"
    gmc = Path(cache_dir) / f"{name}.gmc.npz"
    if not det.exists() or not gmc.exists():
        return None
    first, last = split.range_for(name, "val")
    shifts = np.load(gmc)["shifts"][first - 1:last] if use_gmc else None
    cfg = TrackerConfig(use_gmc=use_gmc)
    frames = run_sequence(CachedSequence(det), cfg, first, last, camera_shifts=shifts)
    return evaluate_frames(frames)


def _group(seqs, detector, cache_dir, split):
    """Return (per_seq_off, per_seq_on) metric dicts for sequences that exist."""
    off, on = {}, {}
    for s in seqs:
        m_off = _run(s, detector, cache_dir, split, use_gmc=False)
        if m_off is None:
            continue
        off[s] = m_off
        on[s] = _run(s, detector, cache_dir, split, use_gmc=True)
    return off, on


def _report_group(title, off, on) -> str:
    lines = [f"### {title}  ({len(off)} sequences)", ""]
    if not off:
        return "\n".join(lines + ["_no GMC caches found — run precompute_gmc.py_", ""])
    lines.append("| metric | GMC off | GMC on | Δ (p) |")
    lines.append("|---|---|---|---|")
    seqs = list(off)
    for m in _METRICS:
        a = np.array([on[s][m] for s in seqs], float)
        b = np.array([off[s][m] for s in seqs], float)
        c = compare(a, b, seed=0)
        star = "*" if c.p_wilcoxon < 0.05 else ""
        lines.append(f"| {m} | {b.mean():.3f} | {a.mean():.3f} | "
                     f"{c.delta:+.3f} (p={c.p_wilcoxon:.2f}{star}) |")
    return "\n".join(lines + [""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ4 global motion compensation study")
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--split-file", default="mot17_val_half")
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args(argv)

    split = load_split(args.split_file)
    print(f"RQ4 GMC study | detector={args.detector}\n")
    m_off, m_on = _group(MOVING, args.detector, args.cache_dir, split)
    s_off, s_on = _group(STATIC, args.detector, args.cache_dir, split)

    report = ["# RQ4: global motion compensation (translation-only, from scratch)", "",
              "Δ = GMC on − off, paired over sequences (Wilcoxon). `*` = p<0.05.", "",
              _report_group("Moving camera (05/10/11/13)", m_off, m_on),
              _report_group("Static camera (02/04/09)", s_off, s_on)]
    text = "\n".join(report)
    print(text)
    if args.out_md:
        Path(args.out_md).write_text(text + "\n")
        print(f"\nwrote report -> {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
