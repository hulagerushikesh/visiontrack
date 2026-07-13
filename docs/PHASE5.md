# Phase 5 — RQ3: calibrated uncertainty-aware association

Question (RQ3): *does propagating calibrated Kalman uncertainty into the full
association cost (a soft cost, not just a hard gate) reduce ID switches under
detector noise, versus a fixed-threshold gate?*

**Answer (honest, and more interesting than a yes):** No — and the *why*
reveals that the filter's apparent "miscalibration" is actually a robustness
feature for tracking-by-detection.

## What shipped

| Piece | Where | Role |
|-------|-------|------|
| Calibration analysis | [`eval/calibration.py`](../src/visiontrack/eval/calibration.py) | innovation χ² along GT tracks, χ²(4) reliability curve, calibration factor |
| Noise injection | [`detection/noise.py`](../src/visiontrack/detection/noise.py) | `perturb_detections` (jitter/drop/false-positives) + `PerturbedSequence` |
| Calibration knob | [`tracking/config.py`](../src/visiontrack/tracking/config.py) | `kf_noise_scale` — scale the filter covariance (calibrate it) |
| Soft-uncertainty cost | `tracking/cost.py` (Phase 2 hook, `w_unc`) | normalized Mahalanobis folded into the cost |
| Study | [`experiments/uncertainty_study.py`](../experiments/uncertainty_study.py) | reliability figure + noised-MOT17 sweep |
| Synthetic sweep | [`experiments/configs/rq3_uncertainty_synth.yaml`](../experiments/configs) | controlled high-noise probe via the Phase 1 harness |

## A cost-surface fix discovered here

Building RQ3 exposed a flaw in the Phase 2 cost: the appearance/uncertainty
terms were *added* on top of a **fixed IoU-based `max_cost`**, so any positive
weight pushed feasible pairs past the acceptance threshold — the soft term acted
as a **veto that shrank the gate**, guaranteeing harm. Fixed: each term now also
raises `max_cost` by its maximum contribution, so the **gate alone decides
feasibility and the terms only rank** feasible pairs (DeepSORT-style fusion).
`w_iou`-only behaviour is still bit-identical to Phase 0/2; Phase 3's appearance
numbers were re-run under the corrected cost (see `docs/PHASE3.md`).

## Finding 1 — the filter is badly under-confident

Stepping the CV Kalman filter along **real MOT17 GT trajectories** and measuring
the innovation χ² (should be χ²(4), mean 4 if calibrated):

```
                mean χ²   calibration factor   fraction inside 95% gate
default         0.15      0.04                 1.000   (ideal ≈ 0.95)
scaled × 0.19   2.61      0.65                 0.939
```

![Kalman calibration](../assets/kalman_calibration.png)

The default filter is **~25× under-confident**: GT pedestrian motion is far
smoother than the noise model assumes, so **the 95% Mahalanobis gate never
rejects anything** (100% inside). This is *why* Phase 0's ablation found that
disabling the gate barely changed results — it was already inert.

## Finding 2 — the soft uncertainty term is null

On the synthetic high-noise probe (10 objects, heavy jitter + clutter, 4
sequences × 10 seeds), folding normalized Mahalanobis into the cost (`w_unc`)
changes nothing significant:

```
variant         HOTA Δ (p)        IDSW Δ (p)
soft_unc_0.3    -0.001 (p=0.17)   +0.47 (p=0.35)
soft_unc_0.6    -0.001 (p=0.06)   +0.53 (p=0.35)
```

Expected, given Finding 1: when the gate is inert and the uncertainty signal is
near-constant, adding it to the cost carries no information.

## Finding 3 — *calibrating* the filter hurts under detector noise

The tempting fix is to calibrate (shrink the covariance, `kf_noise_scale=0.19`).
On **noised MOT17 val** (jitter 8px, 15% drop, 1 FP/frame; 3 seeds × 7 seqs),
paired vs the fixed-gate baseline:

```
variant           HOTA Δ (p)         IDSW Δ (p)
fixed_gate        0.343  (baseline)  40.2  (baseline)
calibrated        -0.205 (p<0.05*)   +362  (p<0.05*)
calibrated+soft   -0.205 (p<0.05*)   +394  (p<0.05*)
```

Calibrating makes it **dramatically worse**: a tight gate tuned to clean GT
motion **rejects noisy-but-correct detections**, so tracks fragment and ID
switches explode (40 → 400+). The under-confident loose gate was *tolerating
detector jitter* — a feature, not a bug.

## Conclusion (RQ3)

The fixed, loose Mahalanobis gate is already doing the right job as a **robust
safety net**. Neither folding calibrated uncertainty into the cost (null) nor
recalibrating the filter to GT motion (actively harmful under noise) improves on
it. The intuitive "the filter is miscalibrated, so calibrate it" is **wrong for
tracking-by-detection**: robustness to detector noise matters more than
statistical calibration to clean trajectories. This is the kind of controlled
negative result the project is built to surface honestly.

## Acceptance

The plan's target was "IDSW reduction with significance + a calibration plot."
The calibration plot is delivered and is the headline artifact; the honest
outcome is a **significant null/negative** for the soft term and for
calibration, with a mechanistic explanation that unifies Phase 0's gate ablation
with the calibration measurement. Reporting this rather than engineering a
spurious positive is the point.

## Tests

`tests/test_uncertainty.py` (9): innovation-sample shape/monotonicity, the
scale↔confidence relationship, noise-injection determinism/drop/FP behaviour,
`PerturbedSequence` GT pass-through, and that `kf_noise_scale=1.0` is unchanged.
**253 tests pass**, ruff clean. Core untouched; `scipy` (calibration) stays a
lazy/dev dependency.
