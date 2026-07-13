# VisionTrack

[![CI](https://github.com/hulagerushikesh/visiontrack/actions/workflows/ci.yml/badge.svg)](https://github.com/hulagerushikesh/visiontrack/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**A from-scratch multi-object tracker, used as a controlled study of *when* the field's standard tricks actually help.**

The tracker — an 8-state **Kalman filter**, an O(n³) **Hungarian** solver, and **ByteTrack** two-stage association — is implemented from first principles on NumPy, with no ML framework in the core. On top of it sits a reproducible experiment harness that measures, on **real MOT17** with seed variance and paired significance tests, whether **appearance** and **uncertainty-aware association** actually improve tracking. Several of the answers are honest negatives — which is the point.

---

## Abstract

Most tracking repositories are a thin wrapper over a detector plus a vendored tracker; every reported number is a single run on one configuration. VisionTrack inverts that: the estimation and association math *is* the deliverable (independently tested against SciPy and `trackeval`), and it is used to run a **falsifiable study**. We reproduce a from-scratch ByteTrack baseline on MOT17 public detections (HOTA/IDF1 verified against `trackeval` to within `1.4e-3`), then ablate two common enhancements under seed variance and Wilcoxon significance:

- **Appearance (RQ1)** — a per-track re-ID cost helps *association* on MOT17 (ID switches 188 → 170) but the effect is small and not significant with a cheap descriptor.
- **Uncertainty (RQ3)** — folding calibrated Kalman uncertainty into the cost is **null**, and *calibrating* the filter to real motion is **actively harmful** under detector noise (ID switches 40 → 400+). The filter's apparent under-confidence turns out to be a robustness feature, not a bug.

![tracked trajectories](assets/trajectories.png)

*Synthetic sanity check: seven objects over 120 frames — tracks **#3** and **#7** cross in the centre and keep their identities.*

---

## Research questions

| | Question | Answer on MOT17 |
|---|---|---|
| **RQ1** | Does an appearance (re-ID) association cost improve tracking? | Small, consistent ↓ in ID switches; negligible HOTA change (weak descriptor) |
| **RQ3** | Does folding *calibrated* Kalman uncertainty into the cost reduce switches under noise? | **No** — null as a soft cost; calibrating the filter *hurts* badly under detector noise |
| RQ2 | Does a learned motion residual help? | Deferred — needs a maneuver-heavy dataset; MOT17 motion is near-linear (see §Limitations) |

The value is the same whichever way each result falls: a controlled study that shows a trick *doesn't* help is a contribution, not a failure.

---

## Method

**The from-scratch core** (`core/`, NumPy only):

- **Kalman filter** — 8-state constant-velocity model in DeepSORT's `xyah` parametrization, height-scaled noise for scale-invariance, Joseph-form covariance update, Mahalanobis gating. Convergence-tested.
- **Hungarian assignment** — rectangular O(n³) Kuhn–Munkres with dual potentials; validated against `scipy.optimize.linear_sum_assignment` on 150 random matrices.
- **ByteTrack two-stage association** + a `Tentative → Confirmed → Deleted` lifecycle FSM.

**The ablation surface** (`tracking/cost.py`): the association cost is factored so each hypothesis is one weighted term with a hard gate deciding feasibility and the terms only *ranking* feasible pairs (DeepSORT-style fusion):

```
cost = w_iou·motion  ⊕  w_app·appearance  ⊕  w_unc·uncertainty      (gate: IoU + class + Mahalanobis)
```

At `w_app = w_unc = 0` this is **bit-identical** to the plain `1 − IoU` baseline, so every ablation toggles exactly one variable.

**Rigor** (`eval/`, `experiments/`):

- **Metrics**: from-scratch **CLEAR-MOT + IDF1 + HOTA**, cross-checked against `trackeval` end-to-end on real MOT17 (MOTA/IDF1 exact, HOTA within `1.4e-3`).
- **Seed variance + paired significance**: every configuration is run over seeds; variants are compared paired (same sequences/seeds) with a **paired bootstrap + Wilcoxon** test and Cohen's d.
- **Compute once**: detections and appearance embeddings are cached to disk (5.2 MB + 6.3 MB for all of MOT17-train), so the raw ~5 GB of frames can be deleted and every experiment runs CPU-only in seconds.

---

## Results

### Baseline — from-scratch ByteTrack on real MOT17 (val-half, public detections)

| detector | MOTA | IDF1 | HOTA | DetA | AssA |
|----------|-----:|-----:|-----:|-----:|-----:|
| **SDP**   | 0.624 | 0.673 | 0.565 | 0.542 | 0.589 |
| **FRCNN** | 0.469 | 0.570 | 0.497 | 0.423 | 0.587 |
| **DPM**   | 0.115 | 0.182 | 0.193 | 0.093 | 0.404 |

Squarely in the public-detection neighbourhood (the famous ~76 MOTA ByteTrack uses a private YOLOX detector), with the expected detector ordering. `scripts/xcheck_mot17_trackeval.py` confirms our whole pipeline (preprocessing + metrics) matches `trackeval` on a real sequence.

### RQ1 — appearance (MOT17 FRCNN, from-scratch colour-histogram embedder)

| w_app | HOTA | IDF1 | AssA | IDSW |
|------:|------|------|------|-----:|
| 0.0 (motion only) | 0.497 | 0.570 | 0.587 | 188 |
| 0.6 | +0.001 | +0.002 | +0.003 | **170 (−18)** |

![appearance](assets/appearance_mot17_frcnn.png)

Appearance's clearest effect is on **ID switches** (−10%); HOTA barely moves. Directionally consistent but not significant with a cheap descriptor — a deep re-ID model (`appearance/reid_onnx.py`, drop-in) is the lever to widen it. [Details →](docs/PHASE3.md)

### RQ3 — calibrated uncertainty (the interesting negative)

Stepping the Kalman filter along real MOT17 GT, the innovation χ² is **0.15** where a calibrated filter would give **4.0** — it is ~25× *under-confident*, so its 95% gate captures **100%** of innovations and never rejects.

![calibration](assets/kalman_calibration.png)

Consequences, measured:

- Folding uncertainty into the cost (`w_unc`) is **null** (the gate is inert, the signal near-constant).
- *Calibrating* the filter (`kf_noise_scale=0.19`) is **catastrophic under detector noise**: HOTA −0.205, **ID switches 40 → 400+** (both p<0.05). A tight gate tuned to clean motion rejects noisy-but-correct detections and tracks fragment.

**The loose gate is a robustness feature, not a bug.** This unifies with the ablation finding that disabling the gate barely changes clean-data results. [Details →](docs/PHASE5.md)

### Throughput

Real-time on CPU (single-threaded): **2334 FPS** at 4 objects down to **214 FPS** at 64 — comfortably ≥30 FPS across the range (`benchmarks/bench_tracker.py`).

---

## Reproduce

```bash
make install                 # editable install with all extras
make test                    # 253 tests
make reproduce-synth         # synthetic harness + RQ3 probe — NO dataset needed
```

Full real-data reproduction (after a one-time cache build — see [docs/PHASE0.md](docs/PHASE0.md)):

```bash
python data/cache/precompute.py            --data-root ~/MOT17 --detector FRCNN --out data/cache/mot17
python data/cache/precompute_embeddings.py --data-root ~/MOT17 --detector FRCNN --cache-dir data/cache/mot17
make reproduce               # regenerates every table and figure above
```

Every run is pinned by a config hash; bootstrap resampling and synthetic scenes are seeded. Each phase has a runbook in [`docs/`](docs/) (`PHASE0.md` … `PHASE5.md`).

---

## Engineering

- **Zero ML-framework dependency in the core** — just NumPy. Heavy/optional deps (`scipy`, `pandas`, `matplotlib`, `pillow`, `onnxruntime`, `torch`) are isolated in extras (`[experiments]`, `[appearance]`, `[onnx]`) and lazily imported; nothing in `core/` imports them.
- **253 tests**: unit, property (Hungarian vs SciPy), convergence (Kalman), metric cross-checks (HOTA/IDF1 vs `trackeval`), and end-to-end integration with a MOTA floor.
- **CI** on Python 3.10/3.11/3.12 + ruff.

```
src/visiontrack/
  core/        geometry · kalman · assignment          ← from-scratch math
  detection/   base · synthetic · onnx_yolo · mot_loader · noise
  appearance/  embedder (colour-hist) · reid_onnx · gallery   (RQ1)
  tracking/    tracker · track (FSM) · cost (ablation surface) · config
  eval/        mot (CLEAR-MOT) · hota (HOTA/IDF1) · stats · calibration (RQ3)
  datasets/    splits (frozen) · cache (detections + embeddings)
experiments/   run_matrix · analyze · appearance_study · uncertainty_study · configs/
data/cache/    precompute · precompute_embeddings
scripts/       xcheck_mot17_trackeval.py
```

---

## Limitations & honest negatives

- **Public-detection, train/val split** — reproducible and self-contained, not test-server leaderboard numbers (deliberate).
- **RQ1 uses a weak descriptor** — an HSV colour histogram; the deep re-ID hook is built but unused for the headline numbers.
- **RQ2 (learned motion residual) is deferred** — it needs a maneuver-heavy dataset (SportsMOT/DanceTrack); MOT17 pedestrian motion is near-linear (the calibration study measured how smooth), so a residual is a predicted null on the available data.
- **The cross-dataset RQ1 crossover** (appearance helping on MOT17 but hurting on near-identical DanceTrack) awaits those datasets — a storage constraint, not a code one; the loaders reuse the MOT-format parser.
- **Interactive demo** — a deployed toggle-the-branches demo is future work (needs a hosting decision).

## License

MIT
