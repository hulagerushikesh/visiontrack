"""RQ3: calibrated uncertainty-aware association on MOT17.

Two parts:

1. **Calibration** — step a CV Kalman filter along MOT17 GT trajectories and
   check whether its innovation χ² matches the χ²(4) reference. Saves a
   reliability (Q–Q) figure and reports the calibration factor at the default
   noise and at a calibrated scale.
2. **Noise-regime tracking** — inject detector noise and compare, over seeds ×
   sequences (paired): the fixed-gate baseline, a *calibrated* filter, and
   calibrated + soft uncertainty cost (``w_unc``). Reports Δ metrics with
   Wilcoxon p-values.

    python -m experiments.uncertainty_study --detector FRCNN --out-fig assets/kalman_calibration.png
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
from visiontrack.detection.noise import NoiseConfig, PerturbedSequence  # noqa: E402
from visiontrack.eval.calibration import innovation_chi2_samples, reliability_curve  # noqa: E402
from visiontrack.eval.mot17 import evaluate_sequences  # noqa: E402
from visiontrack.eval.stats import compare  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402

CALIBRATED_SCALE = 0.19  # ~ sqrt(0.15/4): brings mean innovation χ² to ~4 on MOT17


def _base_readers(cache_dir: Path, detector: str, split):
    out = []
    for vid in split.video_ids():
        npz = cache_dir / f"{vid}-{detector}.npz"
        if npz.exists():
            out.append(CachedSequence(npz))
    return out


def calibrate(readers, split, subset, out_fig=None):
    d1, dc = [], []
    for r in readers:
        first, last = split.range_for(r.name, subset)
        d1.append(innovation_chi2_samples(r, first, last, noise_scale=1.0))
        dc.append(innovation_chi2_samples(r, first, last, noise_scale=CALIBRATED_SCALE))
    d1, dc = np.concatenate(d1), np.concatenate(dc)
    r1, rc = reliability_curve(d1, dof=4), reliability_curve(dc, dof=4)
    print("Kalman calibration on MOT17 GT trajectories (dof=4, calibrated mean χ²≈4):")
    print(f"  default   (scale=1.00): mean χ²={d1.mean():.2f}  factor={r1.calibration_factor:.3f}"
          f"  in-95%-gate={(d1 < 9.4877).mean():.3f}")
    print(f"  calibrated(scale={CALIBRATED_SCALE:.2f}): mean χ²={dc.mean():.2f}  "
          f"factor={rc.calibration_factor:.3f}  in-95%-gate={(dc < 9.4877).mean():.3f}")

    if out_fig:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(5.5, 5.5), dpi=110)
        lim = float(max(r1.theoretical.max(), r1.empirical.max(), rc.empirical.max()) * 1.05)
        ax.plot([0, lim], [0, lim], "--", color="#888", label="calibrated (y=x)")
        ax.plot(r1.theoretical, r1.empirical, "o-", color="#e8833a",
                label=f"default (factor {r1.calibration_factor:.2f})")
        ax.plot(rc.theoretical, rc.empirical, "s-", color="#4c9aff",
                label=f"scaled ×{CALIBRATED_SCALE} (factor {rc.calibration_factor:.2f})")
        ax.set_xlabel("χ²(4) theoretical quantile")
        ax.set_ylabel("empirical innovation χ² quantile")
        ax.set_title("Kalman calibration on MOT17 GT")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_fig)
        plt.close(fig)
        print(f"  wrote calibration figure -> {out_fig}")


def noise_sweep(base_readers, split, subset, seeds, noise_cfg):
    variants = {
        "fixed_gate": TrackerConfig(),
        "calibrated": TrackerConfig(kf_noise_scale=CALIBRATED_SCALE),
        "calibrated+soft": TrackerConfig(kf_noise_scale=CALIBRATED_SCALE, w_unc=0.5),
    }
    metrics = ["HOTA", "AssA", "IDF1", "IDSW", "MOTA"]
    # cell metrics keyed by (variant, seq, seed)
    cell: dict[tuple[str, str, int], dict] = {}
    for seed in seeds:
        readers = [PerturbedSequence(b, noise_cfg, seed) for b in base_readers]
        for name, cfg in variants.items():
            _, reports = evaluate_sequences(readers, cfg, split, subset, per_sequence=True)
            for rep in reports:
                cell[(name, rep.name, seed)] = rep.metrics

    seqs = [b.name for b in base_readers]
    print(f"\nNoise-regime tracking (jitter={noise_cfg.jitter_std}px, drop={noise_cfg.drop_prob}, "
          f"fp/frame={noise_cfg.fp_rate}) | {len(seeds)} seeds × {len(seqs)} seqs\n")
    header = f"{'variant':<16} | " + " | ".join(f"{m:>14}" for m in metrics)
    print(header)
    print("-" * len(header))
    base = "fixed_gate"
    for name in variants:
        cells = []
        for m in metrics:
            vals = [cell[(name, s, sd)][m] for s in seqs for sd in seeds]
            mean = float(np.mean(vals))
            if name == base:
                cells.append(f"{mean:>14.3f}")
            else:
                a = vals
                b = [cell[(base, s, sd)][m] for s in seqs for sd in seeds]
                c = compare(a, b, seed=0)
                star = "*" if c.p_wilcoxon < 0.05 else ""
                cells.append(f"{mean:>6.3f} {c.delta:+.3f}{star:>1}")
        print(f"{name:<16} | " + " | ".join(cells))
    print("\nΔ and * (p<0.05, Wilcoxon over seq×seed) are vs fixed_gate. IDSW lower is better.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ3 calibrated uncertainty study")
    parser.add_argument("--detector", default="FRCNN", choices=["DPM", "FRCNN", "SDP"])
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--split", default="val", choices=["train", "val", "all"])
    parser.add_argument("--split-file", default="mot17_val_half")
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--out-fig", default=None, help="calibration reliability figure path")
    parser.add_argument("--no-sweep", action="store_true", help="calibration only, skip sweep")
    args = parser.parse_args(argv)

    split = load_split(args.split_file)
    readers = _base_readers(Path(args.cache_dir), args.detector, split)
    if not readers:
        print("No detection caches found; run data/cache/precompute.py first.")
        return 1

    calibrate(readers, split, args.split, out_fig=args.out_fig)
    if not args.no_sweep:
        seeds = [int(s) for s in args.seeds.split(",")]
        noise_sweep(readers, split, args.split, seeds, NoiseConfig())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
