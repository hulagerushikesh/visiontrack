"""RQ2: train the from-scratch motion residual and measure whether it beats the
constant-velocity prediction — more on maneuver-heavy DanceTrack than on MOT17.

Extracts GT centroid trajectories from the cached sequences, builds
(history → CV-residual) samples, splits **by track** into train/held-out (no
leakage), trains :class:`MLPResidual`, and reports the held-out next-centre
prediction error of CV vs CV+residual per dataset. This is the isolated RQ2
result (before any tracking): does a learned residual recover the lag the
constant-velocity model shows at turns and accelerations?

    python -m experiments.train_residual --out models/motion_residual.npz
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.datasets.cache import CachedSequence  # noqa: E402
from visiontrack.detection.mot_loader import PEDESTRIAN_CLASS  # noqa: E402
from visiontrack.tracking.motion.residual import (  # noqa: E402
    WINDOW,
    MLPResidual,
    residual_features,
)

DATASETS = {
    "MOT17": ("data/cache/mot17", "*-FRCNN.npz"),
    "DanceTrack": ("data/cache/dancetrack", "dancetrack*.npz"),
}


def _runs_from_reader(reader) -> list[np.ndarray]:
    """GT centroid+size runs (contiguous frames) for one sequence, scoring GT only."""
    seq: dict[int, list] = defaultdict(list)
    for fd in reader:
        keep = (fd.gt_classes == PEDESTRIAN_CLASS) & (fd.gt_conf >= 1.0)
        for i in np.where(keep)[0]:
            x1, y1, x2, y2 = fd.gt_xyxy[i]
            size = float(np.sqrt(max((x2 - x1) * (y2 - y1), 1.0)))
            seq[int(fd.gt_ids[i])].append((fd.frame, (x1 + x2) / 2, (y1 + y2) / 2, size))
    runs = []
    for rows in seq.values():
        rows.sort()
        run, prev = [], None
        for f, cx, cy, s in rows:
            if prev is not None and f != prev + 1:
                if len(run) >= WINDOW + 2:
                    runs.append(np.array(run))
                run = []
            run.append((cx, cy, s))
            prev = f
        if len(run) >= WINDOW + 2:
            runs.append(np.array(run))
    return runs


def _samples(run: np.ndarray):
    """Yield (features, target_norm, cv_err, scale) over a run (cx,cy,size)."""
    C, S = run[:, :2], run[:, 2]
    for t in range(WINDOW, len(run) - 1):
        s = S[t]
        cv = C[t] + (C[t] - C[t - 1])
        target = C[t + 1] - cv
        yield residual_features(C[: t + 1], s), target / s, float(np.linalg.norm(target)), s


def _collect(glob_dir, pattern):
    runs = []
    for npz in sorted(Path(glob_dir).glob(pattern)):
        if npz.name.endswith(".emb.npz"):
            continue
        runs += _runs_from_reader(CachedSequence(npz))
    return runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RQ2 learned motion residual")
    parser.add_argument("--out", default="models/motion_residual.npz")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    train_X, train_Y, held = [], [], {}
    print("Extracting GT trajectories:")
    for name, (d, pat) in DATASETS.items():
        runs = _collect(d, pat)
        if not runs:
            print(f"  {name:<11} no caches at {d}/{pat} — skipping")
            continue
        rng.shuffle(runs)
        cut = int(0.8 * len(runs))
        tr_runs, ho_runs = runs[:cut], runs[cut:]
        for r in tr_runs:
            for feats, y, _cv, _s in _samples(r):
                train_X.append(feats)
                train_Y.append(y)
        held[name] = ho_runs
        n_tr = sum(max(0, len(r) - WINDOW - 1) for r in tr_runs)
        print(f"  {name:<11} {len(runs):>4} runs  ({n_tr} train samples, "
              f"{len(ho_runs)} held-out runs)")

    if not train_X:
        print("No trajectory data. Build the caches first (precompute*.py).")
        return 1

    X = np.array(train_X)
    Y = np.array(train_Y)
    print(f"\nTraining MLPResidual on {X.shape[0]} samples (in={X.shape[1]}) ...")
    model = MLPResidual(seed=args.seed)
    losses = model.fit(X, Y, epochs=args.epochs, seed=args.seed, verbose=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out)
    print(f"saved -> {args.out}  (final train MSE {losses[-1]:.5f})\n")

    # Held-out next-centre error: CV vs CV+residual, per dataset.
    print(f"{'dataset':<11} | {'CV err':>8} | {'+resid err':>10} | {'Δ (lower=better)':>16}")
    print("-" * 56)
    for name, ho_runs in held.items():
        cv_errs, res_errs = [], []
        for r in ho_runs:
            C, S = r[:, :2], r[:, 2]
            for t in range(WINDOW, len(r) - 1):
                s = S[t]
                cv = C[t] + (C[t] - C[t - 1])
                feats = residual_features(C[: t + 1], s)
                corr = model.predict(feats)[0] * s
                cv_errs.append(np.linalg.norm(C[t + 1] - cv))
                res_errs.append(np.linalg.norm(C[t + 1] - (cv + corr)))
        cv_m, res_m = float(np.mean(cv_errs)), float(np.mean(res_errs))
        pct = 100.0 * (cv_m - res_m) / cv_m if cv_m else 0.0
        print(f"{name:<11} | {cv_m:>8.3f} | {res_m:>10.3f} | "
              f"{res_m - cv_m:>+9.3f} ({pct:+.1f}%)")

    print("\nRQ2 prediction: the residual should help MORE on DanceTrack (non-linear "
          "dance motion) than on MOT17 (near-linear pedestrians).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
