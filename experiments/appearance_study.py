"""RQ1 appearance study on MOT17: does an appearance cost help association?

Runs the tracker over MOT17 val-half at several appearance weights ``w_app``
(0 = motion-only baseline) using cached detections + cached embeddings, and
reports each metric as a paired comparison against the ``w_app=0`` baseline
across the 7 sequences (the pairing unit), with a Wilcoxon p-value.

    python -m experiments.appearance_study --detector FRCNN --embedder colorhist

Requires both caches (see data/cache/precompute.py and precompute_embeddings.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.datasets.cache import CachedSequence  # noqa: E402
from visiontrack.datasets.splits import load_split  # noqa: E402
from visiontrack.eval.mot17 import evaluate_sequences  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402


def _readers(cache_dir: Path, detector: str, embedder: str, split):
    readers = []
    for vid in split.video_ids():
        det = cache_dir / f"{vid}-{detector}.npz"
        emb = cache_dir / f"{vid}-{detector}.{embedder}.emb.npz"
        if det.exists() and emb.exists():
            readers.append(CachedSequence(det, emb_path=emb))
    return readers


def _run(readers, split, subset, w_app: float):
    cfg = TrackerConfig(w_app=w_app)
    overall, reports = evaluate_sequences(readers, cfg, split, subset, per_sequence=True)
    per = {r.name: r.metrics for r in reports}
    return overall, per


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ1 appearance study on MOT17")
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--embedder", default="colorhist")
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--split", default="val", choices=["train", "val", "all"])
    parser.add_argument("--split-file", default="mot17_val_half")
    parser.add_argument("--weights", default="0.0,0.15,0.3,0.6", help="comma-separated w_app")
    parser.add_argument("--metrics", default="HOTA,IDF1,AssA,MOTA,IDSW")
    parser.add_argument("--out-fig", default=None, help="save a Δ-metric vs w_app figure")
    args = parser.parse_args(argv)

    split = load_split(args.split_file)
    readers = _readers(Path(args.cache_dir), args.detector, args.embedder, split)
    if not readers:
        print("No matching detection+embedding caches found. Run precompute.py and "
              "precompute_embeddings.py first.")
        return 1

    weights = [float(w) for w in args.weights.split(",")]
    metrics = args.metrics.split(",")
    seqs = [r.name for r in readers]
    print(f"RQ1 appearance study | MOT17 {args.split} | detector={args.detector} | "
          f"embedder={args.embedder} | {len(readers)} sequences\n")

    # Baseline (motion only).
    base_overall, base_per = _run(readers, split, args.split, 0.0)

    header = f"{'w_app':>6} | " + " | ".join(f"{m:>16}" for m in metrics)
    print(header)
    print("-" * len(header))

    overalls = {}
    for w in weights:
        overall, per = _run(readers, split, args.split, w) if w != 0.0 else (base_overall, base_per)
        overalls[w] = overall
        cells = []
        for m in metrics:
            mean = overall[m]
            if w == 0.0:
                cells.append(f"{mean:>16.3f}")
            else:
                a = [per[s][m] for s in seqs]
                b = [base_per[s][m] for s in seqs]
                c = compare(a, b, seed=0)
                star = "*" if c.p_wilcoxon < 0.05 else ""
                cells.append(f"{mean:>7.3f} {c.delta:+.3f}{star:>1}")
        print(f"{w:>6} | " + " | ".join(cells))

    print("\nΔ and * (p<0.05, Wilcoxon over sequences) are vs the w_app=0 baseline.")

    if args.out_fig:
        _save_figure(overalls, weights, args.out_fig, args.detector, args.embedder)
        print(f"wrote figure -> {args.out_fig}")
    return 0


def _save_figure(overalls, weights, path, detector, embedder):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = overalls[0.0]
    d_assa = [overalls[w]["AssA"] - base["AssA"] for w in weights]
    d_idf1 = [overalls[w]["IDF1"] - base["IDF1"] for w in weights]
    idsw = [overalls[w]["IDSW"] for w in weights]

    fig, ax1 = plt.subplots(figsize=(6.5, 4), dpi=110)
    ax1.plot(weights, d_assa, "o-", color="#4c9aff", label="Δ AssA")
    ax1.plot(weights, d_idf1, "s-", color="#37b679", label="Δ IDF1")
    ax1.axhline(0, color="#888", lw=0.8)
    ax1.set_xlabel("appearance weight  w_app")
    ax1.set_ylabel("Δ vs motion-only")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(weights, idsw, "^--", color="#e8833a", label="IDSW")
    ax2.set_ylabel("ID switches", color="#e8833a")
    ax2.tick_params(axis="y", colors="#e8833a")

    ax1.set_title(f"RQ1: appearance on MOT17 val ({detector}, {embedder})")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
