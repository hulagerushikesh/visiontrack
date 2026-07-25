# Phase 4 — RQ2: a learned motion residual (from scratch)

Question (RQ2): *does a small learned residual on top of the constant-velocity
(CV) Kalman prediction reduce error during abrupt maneuvers — and does it help
more on non-linear motion (dancers) than near-linear motion (pedestrians)?*

## Method — from-scratch, no framework

Consistent with the project's ethos (the hard math on NumPy), the residual is
**not** a Torch import. It is a two-layer tanh MLP with **hand-written
back-propagation and Adam**, trained and run on NumPy, weights serialized to
`.npz` — a peer of the from-scratch Kalman filter and Hungarian solver.

- [`tracking/motion/residual.py`](../src/visiontrack/tracking/motion/residual.py):
  `residual_features` (last `WINDOW=5` velocities, scale-normalized by box size —
  translation- and scale-invariant), `MLPResidual` (forward/backward + Adam +
  save/load), `MotionResidual` (inference; a no-op when no model is set).
- **Target.** CV predicts `p_{t+1} ≈ p_t + v_t`; the residual learns the part CV
  misses, `r = p_{t+1} − (p_t + v_t)`, normalized by the box size. At inference,
  `p_{t+1} = (p_t + v_t) + s·model(features)`.
- [`experiments/train_residual.py`](../experiments/train_residual.py): extracts
  GT centroid trajectories from the MOT17 + DanceTrack caches, splits **by track**
  (no leakage), trains, and reports held-out next-centre error.
- Wired into the tracker via `TrackerConfig.motion_residual_path`: after each
  `track.predict()`, the predicted xyah centre is nudged by the residual. `None`
  ⇒ pure CV, behaviour unchanged (regression-tested).

Weights are trained on GT coordinates (derived numbers, not imagery) but kept
**gitignored** with the rest of `models/`; regenerate with `make` /
`train_residual.py`.

## Result 1 — isolated trajectory prediction (the clean RQ2 answer)

Held-out next-centre error (pixels), CV vs CV+residual, per dataset:

| dataset | CV error | CV + residual | Δ |
|---------|---------:|--------------:|---|
| **MOT17** (pedestrians) | 1.047 | 1.272 | **+21.5 % (worse)** |
| **DanceTrack** (dancers) | 6.889 | 6.028 | **−12.5 % (better)** |

The contrast is the RQ2 result, with a mechanistic explanation baked into the
numbers:

- **MOT17 pedestrian motion is near-linear** — CV's own error is ~**1 pixel**.
  There is almost nothing for a residual to fix, so the learned correction only
  adds noise and *hurts* (+21.5 %). A predicted, honest **null-to-negative**.
- **DanceTrack motion is non-linear** — CV error is **~7×** larger (6.9 px). The
  residual has real lag to recover and cuts it by **12.5 %**. This is exactly the
  maneuver regime RQ2 targets, and the one MOT17 could never exercise.

That the same model helps on one dataset and hurts on the other — cleanly split
by how linear the motion is — is the point: a motion residual is worth its
latency only when the motion model is actually wrong.

## Result 2 — tracking-level ablation (the residual that helps prediction hurts tracking)

Δ = residual − baseline, paired over sequences, `*` = p<0.05
(`experiments/residual_ablation.py`):

| dataset | HOTA | IDF1 | AssA | MOTA | IDSW |
|---------|------|------|------|------|------|
| **DanceTrack** (12) | −0.043\* | −0.058\* | −0.037\* | −0.026\* | +29 (p.05) |
| **MOT17-FRCNN val** (7) | −0.013\* | −0.017\* | −0.018 | −0.012\* | +12\* |

**The residual hurts tracking on *both* datasets** — including DanceTrack, where
it *improved* open-loop prediction. This is the honest RQ2 result, and the gap
between Result 1 and Result 2 is the lesson:

- **Train/inference distribution shift.** The residual was trained on **clean GT
  trajectories**; at tracking time it is fed the tracker's own **noisy, jittery
  centre history**. A correction learned for smooth GT motion mis-fires on
  estimated tracks — the classic open-loop-vs-closed-loop, train-on-oracle skew.
- **It perturbs the association gate.** The residual nudges the predicted centre
  that gates and ranks matches. Even a small wrong nudge can push a box out of the
  IoU/Mahalanobis gate or into a neighbour's, *creating* switches — which is
  exactly what IDSW shows (+29 / +12).
- So a residual that provably lowers next-centre error **open-loop** still
  degrades identity **closed-loop**. The DanceTrack prediction win (−12.5 %) does
  not survive contact with association.

Net RQ2 answer, stated honestly: *on this tracking-by-detection pipeline, a learned
motion residual is not worth it* — it helps prediction only where motion is
non-linear, and even there the gain is erased (and reversed) by distribution shift
and gate disruption once it is inside the tracker. Making it pay off would require
training on tracker-estimated (not GT) trajectories and feeding the filter's
covariance in — a larger method, out of scope for this controlled study. Another
honest negative, in the same spirit as RQ3.

## Tests

`tests/test_residual.py` (pure NumPy, no Torch/data — runs in CI): feature
shape/padding/scale, the MLP overfitting a learnable map, save/load round-trip,
the inference no-op guard, an **end-to-end maneuver test** (the residual learns
to cancel a constant-acceleration lag that CV misses), and a tracker-integration
smoke test. Behaviour is unchanged when `motion_residual_path=None`.

## Notes / limitations

- The isolated result is the clean RQ2 statement; the tracking ablation shows how
  much of that prediction gain survives association (where a good detector's boxes
  already pin most tracks).
- Trained on GT trajectories (oracle motion) — a deployment residual would train
  on tracker-estimated tracks. Scope is the controlled study, as elsewhere.
- The model is deliberately tiny (a 10→32→2 MLP); the point is the *contrast*, not
  a state-of-the-art motion model.
