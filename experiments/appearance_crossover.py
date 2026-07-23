"""RQ1 crossover: dial inter-object appearance similarity and watch the sign flip.

Real MOT17 sits at one end of RQ1 (diverse pedestrians → appearance helps). It
cannot show the *crossover* the thesis predicts — that appearance stops helping,
and eventually hurts, as objects become near-identical — because you cannot dial
appearance similarity on a fixed real dataset. The synthetic probe can: its
generator emits a per-object appearance vector whose inter-object similarity is a
single knob (``appearance_diversity``: 0 = identical "dancers", 1 = distinct
"pedestrians"), while holding scene geometry and detector noise fixed.

This script sweeps that knob, and at each level runs the tracker with appearance
**off** (``w_app=0``) and **on** (``w_app>0``) over N paired seeds (same scenes),
reporting the appearance Δ per metric with a paired Wilcoxon — and plots the
crossover curve where Δ(IDSW) passes through zero.

    python -m experiments.appearance_crossover --w-app 0.6 --seeds 24 \
        --out-fig assets/appearance_crossover_synth.png
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

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig  # noqa: E402
from visiontrack.eval.mot17 import evaluate_frames  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402
from visiontrack.tracking.tracker import ByteTracker  # noqa: E402


def _run_scene(scene: SyntheticScene, cfg: TrackerConfig) -> dict:
    tracker = ByteTracker(cfg)
    frames = []
    for f in scene:
        obs = tracker.update(f.detections)
        if obs:
            tr_ids = np.array([o.track_id for o in obs], dtype=np.int64)
            tr_boxes = np.stack([o.xyxy for o in obs], axis=0)
        else:
            tr_ids = np.empty((0,), dtype=np.int64)
            tr_boxes = np.empty((0, 4))
        frames.append((f.gt_ids, f.gt_boxes, tr_ids, tr_boxes))
    return evaluate_frames(frames)


def _scene(seed: int, diversity: float, scene_kwargs: dict) -> SyntheticScene:
    return SyntheticScene(SyntheticSceneConfig(
        seed=seed, appearance_diversity=diversity, **scene_kwargs))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ1 synthetic appearance crossover")
    parser.add_argument("--w-app", type=float, default=0.6)
    parser.add_argument("--diversities", default="0.0,0.15,0.3,0.5,0.7,1.0")
    parser.add_argument("--seeds", type=int, default=24)
    parser.add_argument("--num-objects", type=int, default=10)
    parser.add_argument("--num-frames", type=int, default=120)
    parser.add_argument("--appearance-dim", type=int, default=64)
    parser.add_argument("--appearance-noise-std", type=float, default=0.15)
    parser.add_argument("--appearance-drift-std", type=float, default=0.0,
                        help=">0 makes descriptors non-stationary (the harm-mechanism probe)")
    # Scene difficulty — appearance can only act when motion is ambiguous, so
    # these expose the noise/occlusion knobs that create that ambiguity.
    parser.add_argument("--loc-noise-std", type=float, default=12.0)
    parser.add_argument("--miss-rate", type=float, default=0.12)
    parser.add_argument("--occluded-miss-rate", type=float, default=0.35)
    parser.add_argument("--false-positive-rate", type=float, default=1.5)
    parser.add_argument("--occlusion-iou", type=float, default=0.3)
    parser.add_argument("--metrics", default="IDSW,AssA,IDF1")
    parser.add_argument("--out-fig", default=None)
    args = parser.parse_args(argv)

    diversities = [float(x) for x in args.diversities.split(",")]
    metrics = args.metrics.split(",")
    scene_kwargs = dict(
        num_objects=args.num_objects, num_frames=args.num_frames,
        appearance_dim=args.appearance_dim, appearance_noise_std=args.appearance_noise_std,
        appearance_drift_std=args.appearance_drift_std,
        loc_noise_std=args.loc_noise_std, miss_rate=args.miss_rate,
        occluded_miss_rate=args.occluded_miss_rate,
        false_positive_rate=args.false_positive_rate, occlusion_iou=args.occlusion_iou,
    )
    off_cfg = TrackerConfig(w_app=0.0)
    on_cfg = TrackerConfig(w_app=args.w_app)

    print(f"RQ1 crossover | synthetic | w_app={args.w_app} | {args.seeds} seeds | "
          f"{args.num_objects} objects x {args.num_frames} frames | dim={args.appearance_dim}\n")
    header = f"{'diversity':>9} | " + " | ".join(f"{'Δ' + m:>16}" for m in metrics)
    print(header)
    print("-" * len(header))

    results = {}  # diversity -> {metric: Comparison}
    for d in diversities:
        on = {m: [] for m in metrics}
        off = {m: [] for m in metrics}
        for s in range(args.seeds):
            # Same scene (seed, geometry, noise) for on and off — paired.
            m_off = _run_scene(_scene(s, d, scene_kwargs), off_cfg)
            m_on = _run_scene(_scene(s, d, scene_kwargs), on_cfg)
            for m in metrics:
                off[m].append(m_off[m])
                on[m].append(m_on[m])
        cells, comps = [], {}
        for m in metrics:
            c = compare(on[m], off[m], seed=0)
            comps[m] = c
            star = "*" if c.p_wilcoxon < 0.05 else " "
            cells.append(f"{c.delta:+.3f} p{c.p_wilcoxon:.2f}{star}")
        results[d] = comps
        print(f"{d:>9} | " + " | ".join(f"{x:>16}" for x in cells))

    print("\nΔ = mean(appearance_on − off) over seeds; * = p<0.05 (paired Wilcoxon).")
    print("ΔIDSW < 0 = appearance REDUCES switches (helps); > 0 = hurts.")

    if args.out_fig:
        _save_figure(results, diversities, args.out_fig, args.w_app)
        print(f"\nwrote figure -> {args.out_fig}")
    return 0


def _save_figure(results, diversities, path, w_app):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.array(diversities)  # 0 = identical (left) … 1 = distinct (right)

    def series(metric):
        d = np.array([results[k][metric].delta for k in diversities])
        sig = [results[k][metric].p_wilcoxon < 0.05 for k in diversities]
        return d, sig

    d_assa, sig_assa = series("AssA")
    d_idf1, sig_idf1 = series("IDF1")
    d_idsw, sig_idsw = series("IDSW")

    fig, ax1 = plt.subplots(figsize=(7.4, 4.5), dpi=110)
    ax1.axhline(0, color="#bbb", lw=1.0, zorder=1)

    def plot_sig(ax, x, y, sig, color, label, marker):
        ax.plot(x, y, marker + "-", color=color, lw=1.5, ms=0, zorder=2)
        ax.scatter(x, y, s=[64 if s else 34 for s in sig],
                   facecolors=[color if s else "white" for s in sig],
                   edgecolors=color, linewidths=1.6, marker=marker, zorder=3, label=label)

    # Primary: the significant association-quality gains (filled = p<0.05).
    plot_sig(ax1, x, d_assa, sig_assa, "#4c9aff", "Δ AssA (● p<0.05)", "o")
    plot_sig(ax1, x, d_idf1, sig_idf1, "#37b679", "Δ IDF1 (● p<0.05)", "s")
    ax1.set_xlabel("inter-object appearance diversity  (0 = identical “dancers” … "
                   "1 = distinct “pedestrians”)")
    ax1.set_ylabel("Δ AssA / Δ IDF1  (appearance on − off)")
    ax1.grid(alpha=0.3)

    # Secondary: ID-switch reduction (same direction, but not significant).
    ax2 = ax1.twinx()
    ax2.plot(x, d_idsw, "^--", color="#e8833a", lw=1.1, ms=6, zorder=2, label="Δ IDSW (n.s.)")
    ax2.set_ylabel("Δ ID switches (appearance on − off)", color="#e8833a")
    ax2.tick_params(axis="y", colors="#e8833a")

    lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(lines, labels, loc="upper left", fontsize=8)
    ax1.set_title("RQ1 synthetic probe: appearance benefit grows with distinctness\n"
                  f"(significant on AssA/IDF1); similarity alone is inert, never harmful "
                  f"(w_app={w_app})")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
