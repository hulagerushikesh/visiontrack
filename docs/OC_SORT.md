# H1.2 — OC-SORT (observation-centric mechanics)

The first tracker in the zoo whose defining ideas are **new mechanics**, not a
config flag. OC-SORT's premise: a constant-velocity Kalman filter is
*estimation*-centric — during an occlusion gap it coasts on prediction and its
never-re-anchored velocity drifts, causing ID switches on reappearance. OC-SORT
trusts *observations* over the linear estimate in two places, both implemented
from scratch in [`tracking/motion/oc.py`](../src/visiontrack/tracking/motion/oc.py)
and gated off by default (so the baseline is bit-identical).

## The two mechanics

- **OCM — Observation-Centric Momentum** (`w_ocm`, a soft cost term). Rewards
  matches consistent with the track's *observed* direction of motion: the angle
  between the track's velocity direction (from two observations `ocm_delta_t`
  frames apart) and the direction from its last observation to a candidate
  detection. Folded into the association cost like appearance/uncertainty — it
  only *ranks* in-gate pairs, never vetoes (the Phase-5 contract). Inert for
  tracks without enough history or with ~zero observed velocity.

- **ORU — Observation-Centric Re-Update** (`use_oru`). On re-match after coasting
  `gap` frames, rebuild the state along a virtual straight-line trajectory
  between the last observation and the new one, re-running predict→update at each
  virtual step — re-anchoring the velocity to a smooth, observation-consistent
  path.

## A bug the ablation caught (and the fix)

The first ORU implementation re-ran the filter from `kf.initiate(last_obs)` — a
**fresh** initialisation. That resets the covariance to its large initial value;
after only a few virtual steps the gate stays wide open, so the next frame admits
spurious matches. The component ablation made it unmissable:

| variant (vs `sort`, hard synthetic) | MOTA Δ | IDSW Δ |
|---|---|---|
| OCM only | −0.003 | +2.9 |
| ORU only **(naive re-init)** | **−0.058\*** | **+4.8** |
| ORU only **(anchored to pre-gap state)** | **−0.009\*** | **+1.8** |

The fix: re-run ORU from the **state as of the last observation** (a `(mean,
cov)` snapshot frozen through the gap, `Track.last_obs_state`) instead of
re-initialising — keeping the covariance tight. That turned a catastrophic
regression into a mild one. *Running the ablation before believing the result is
the point.*

## Honest finding — an across-the-board negative (in this study's setting)

Across the synthetic regimes **and** the fair real-data test, OC-SORT's mechanics
do not help:

- **Synthetic, clean + near-linear motion:** exactly neutral (Δ=0, IDSW=0). The
  Kalman filter already nails linear motion, so there is nothing for ORU to
  re-anchor and OCM's directional prior is redundant.
- **Synthetic, high observation noise (8px):** mildly *harmful* (MOTA −0.010,
  p<0.01; OCM-driven). Noisy observations make the observed-velocity direction
  unreliable, so the momentum prior misleads.
- **DanceTrack val (12 seqs) — OC-SORT's *intended* non-linear regime:**
  significantly *harmful*. Paired vs the fair single-stage baseline `sort`:
  **IDSW +19.8 (p=0.01\*)**, MOTA −0.003 (p=0.01*), HOTA −0.006 (n.s.). More ID
  switches, not fewer.

**Why it backfires on DanceTrack — the key insight.** ORU rebuilds the state
along a **straight-line** virtual trajectory between the last and new
observation. Dancers move highly **non-linearly** (they curve and spin), so a
straight line is a *poor* model of the true path across the gap — ORU injects a
wrong velocity, which then causes switches. The linear virtual-trajectory
assumption fails precisely where motion is most non-linear — the regime it was
meant to help. OCM compounds it: with oracle-perturbed (noisy) detections, the
observed-velocity direction is itself unreliable.

**Scope — this is not a refutation of OC-SORT the paper.** This study uses
oracle-perturbed GT detections, a weighted-and-gated single-stage core, and 12
DanceTrack val sequences. OC-SORT's published gains use real detectors and its
own tuning. The honest, scoped claim is: *in this controlled setting, OC-SORT's
observation-centric mechanics do not improve association and increase ID
switches on non-linear motion.*

**Bonus — harness cross-validation.** The same DanceTrack zoo run independently
reproduced the project's marquee RQ1 result: the appearance presets (`deepsort`,
`bytetrack_reid`) significantly cut ID switches (−15.7 / −15.2 IDSW, p<0.01*),
i.e. appearance *helps* on DanceTrack — through a completely different code path
than the original RQ1 study. That the zoo recovers the known result is evidence
the comparison harness is sound.

## Status
Implemented, tested (11 tests, `tests/test_oc_sort.py`), in the zoo as the
`oc_sort` preset. Fair non-linear real-data test on DanceTrack **done** — an
honest negative, scoped as above. Reproduce with
`python -m experiments.tracker_zoo --dataset dancetrack`.
