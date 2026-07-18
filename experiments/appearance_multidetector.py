"""RQ1 deep-dive: multi-detector significance + failure-regime stratification.

The Phase 3 appearance result (deep re-ID helps identity on MOT17-FRCNN) is
directionally strong but not significant over the 7 FRCNN val sequences. This
script deepens RQ1 *without new data*:

1. **Statistical power.** Run appearance-on vs appearance-off across **all three
   public detectors** (DPM / FRCNN / SDP), giving 3 x 7 = **21 paired
   (sequence x detector) units** instead of 7. A paired Wilcoxon over the pooled
   21 either reaches significance or shows the effect is genuinely small.
2. **Where does it help?** Each (sequence x detector) unit gets two GT-derived
   covariates — crowd **density** (mean active GT boxes / frame) and **occlusion**
   (fraction of GT with visibility < 0.5) — and we plot appearance's per-unit
   Delta against them. This is the RQ1 "money figure": appearance is expected to
   help more in dense, heavily-occluded regimes.

    python -m experiments.appearance_multidetector --embedder onnx --w-app 0.6 \
        --out-fig assets/appearance_mot17_stratified.png

GT is detector-independent (MOT17-02-DPM/FRCNN/SDP share one gt.txt), so the
covariates are per-sequence (7 values); the Delta is per-unit (21 values), which
also exposes the detector spread at each density/occlusion level.
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
from visiontrack.eval.mot17 import evaluate_sequences  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402

DETECTORS = ("DPM", "FRCNN", "SDP")


def _readers(cache_dir: Path, detector: str, embedder: str, split):
    readers = []
    for vid in split.video_ids():
        det = cache_dir / f"{vid}-{detector}.npz"
        emb = cache_dir / f"{vid}-{detector}.{embedder}.emb.npz"
        if det.exists() and emb.exists():
            readers.append(CachedSequence(det, emb_path=emb))
    return readers


def _per_seq_metrics(readers, split, subset, w_app):
    cfg = TrackerConfig(w_app=w_app)
    _overall, reports = evaluate_sequences(readers, cfg, split, subset, per_sequence=True)
    return {r.name: r.metrics for r in reports}


def density_occlusion(frame_gts, vis_thresh: float = 0.5) -> tuple[float, float]:
    """Pure covariate math over a sequence of per-frame (conf, vis) GT arrays.

    density   = mean number of active (conf>0) GT boxes per frame
    occlusion = fraction of active GT boxes with visibility < ``vis_thresh``
    Kept free of any cache/reader type so it is directly unit-testable.
    """
    per_frame_counts, n_boxes, n_occluded = [], 0, 0
    for conf, vis in frame_gts:
        conf = np.asarray(conf)
        active = conf > 0
        k = int(active.sum())
        per_frame_counts.append(k)
        n_boxes += k
        if k:
            n_occluded += int((np.asarray(vis)[active] < vis_thresh).sum())
    density = float(np.mean(per_frame_counts)) if per_frame_counts else 0.0
    occlusion = (n_occluded / n_boxes) if n_boxes else 0.0
    return density, occlusion


def _covariates(reader: CachedSequence, split, subset) -> tuple[float, float]:
    """(density, occlusion) over the eval range from GT already in the cache."""
    first, last = split.range_for(reader.name, subset)
    frame_gts = ((fd.gt_conf, fd.gt_vis) for fd in reader.iter_range(first, last))
    return density_occlusion(frame_gts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ1 multi-detector + stratification")
    parser.add_argument("--embedder", default="onnx")
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--split", default="val", choices=["train", "val", "all"])
    parser.add_argument("--split-file", default="mot17_val_half")
    parser.add_argument("--w-app", type=float, default=0.6)
    parser.add_argument("--metrics", default="HOTA,IDF1,AssA,MOTA,IDSW")
    parser.add_argument("--detectors", default="DPM,FRCNN,SDP")
    parser.add_argument("--out-fig", default=None)
    args = parser.parse_args(argv)

    split = load_split(args.split_file)
    metrics = args.metrics.split(",")
    detectors = [d for d in args.detectors.split(",") if d]

    # Collect per-unit on/off metrics and per-unit covariates.
    units: list[dict] = []  # each: {seq, det, on{metric}, off{metric}, density, occ}
    covar_cache: dict[str, tuple[float, float]] = {}
    for det in detectors:
        readers = _readers(Path(args.cache_dir), det, args.embedder, split)
        if not readers:
            print(f"  ! no {det} caches for embedder={args.embedder}; skipping")
            continue
        off = _per_seq_metrics(readers, split, args.split, 0.0)
        on = _per_seq_metrics(readers, split, args.split, args.w_app)
        for r in readers:
            if r.name not in covar_cache:
                covar_cache[r.name] = _covariates(r, split, args.split)
            dens, occ = covar_cache[r.name]
            units.append({"seq": r.name, "det": det, "on": on[r.name],
                          "off": off[r.name], "density": dens, "occ": occ})

    if not units:
        print("No units evaluated — are the embedding caches present?")
        return 1

    print(f"RQ1 multi-detector | embedder={args.embedder} | w_app={args.w_app} | "
          f"{len(units)} (seq x detector) units\n")

    # -- Significance: per-detector and pooled paired Wilcoxon ----------------
    def _cmp(sel_units, m):
        a = [u["on"][m] for u in sel_units]
        b = [u["off"][m] for u in sel_units]
        return compare(a, b, seed=0)

    header = f"{'group':>10} | {'n':>2} | " + " | ".join(f"{m:>14}" for m in metrics)
    print(header)
    print("-" * len(header))
    groups = [(d, [u for u in units if u["det"] == d]) for d in detectors]
    groups.append(("POOLED", units))
    for name, sel in groups:
        if not sel:
            continue
        cells = []
        for m in metrics:
            c = _cmp(sel, m)
            star = "*" if c.p_wilcoxon < 0.05 else " "
            cells.append(f"{c.delta:+.3f} p{c.p_wilcoxon:.2f}{star}")
        print(f"{name:>10} | {len(sel):>2} | " + " | ".join(f"{x:>14}" for x in cells))

    print("\nDelta = mean(appearance_on - off) per unit; * = p<0.05 (Wilcoxon, paired).")
    print("IDSW delta negative = fewer switches = better.")

    if args.out_fig:
        _save_figure(units, detectors, args.out_fig, args.embedder, args.w_app)
        print(f"\nwrote figure -> {args.out_fig}")
    return 0


def _save_figure(units, detectors, path, embedder, w_app):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"DPM": "#e8833a", "FRCNN": "#4c9aff", "SDP": "#37b679"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), dpi=110)

    # Panel 1 — the finding: appearance's ID-switch reduction BY DETECTOR.
    # Detection quality gates whether re-ID crops are usable, so appearance is
    # inert on DPM (noisy boxes) and helps on FRCNN/SDP.
    ax0 = axes[0]
    groups = [(d, [u for u in units if u["det"] == d]) for d in detectors]
    groups.append(("POOLED", units))
    labels, vals, bar_colors, stars = [], [], [], []
    for name, sel in groups:
        if not sel:
            continue
        on = [u["on"]["IDSW"] for u in sel]
        off = [u["off"]["IDSW"] for u in sel]
        c = compare(on, off, seed=0)
        labels.append(f"{name}\n(n={len(sel)})")
        vals.append(c.delta)
        bar_colors.append(colors.get(name, "#555"))
        stars.append("*" if c.p_wilcoxon < 0.05 else "")
    bars = ax0.bar(labels, vals, color=bar_colors, edgecolor="white")
    for bar, s in zip(bars, stars, strict=True):
        if s:
            ax0.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 0.15,
                     "*", ha="center", va="top", fontsize=15, color="white", fontweight="bold")
    ax0.axhline(0, color="#bbb", lw=0.8)
    ax0.set_ylabel("Δ ID switches (appearance on − off)")
    ax0.set_title("Appearance helps only where crops are clean\n(* = p<0.05, paired Wilcoxon)")
    ax0.grid(alpha=0.3, axis="y")

    # Panels 2-3 — honest null: the benefit does NOT stratify by density/occlusion.
    for ax, (xkey, xlabel) in zip(
        axes[1:], [("density", "crowd density (mean GT / frame)"),
                   ("occ", "occlusion (fraction GT vis < 0.5)")], strict=True
    ):
        for det in detectors:
            sel = [u for u in units if u["det"] == det]
            if not sel:
                continue
            x = [u[xkey] for u in sel]
            dy = [u["on"]["AssA"] - u["off"]["AssA"] for u in sel]
            ax.scatter(x, dy, c=colors.get(det, "#888"), label=det, s=45,
                       edgecolors="white", linewidths=0.6, zorder=3)
        allx = np.array([u[xkey] for u in units])
        ally = np.array([u["on"]["AssA"] - u["off"]["AssA"] for u in units])
        if len(allx) >= 2 and np.ptp(allx) > 0:
            m, b = np.polyfit(allx, ally, 1)
            xs = np.array([allx.min(), allx.max()])
            ax.plot(xs, m * xs + b, "--", color="#666", lw=1.2, zorder=2,
                    label=f"trend (slope {m:+.3f})")
        ax.axhline(0, color="#bbb", lw=0.8, zorder=1)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Δ AssA (appearance on − off)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    axes[2].set_title("…but does NOT trend with density or occlusion")
    fig.suptitle(f"RQ1: when does deep re-ID help? MOT17 val ({embedder}, w_app={w_app}, "
                 f"{len(units)} seq×detector units)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
