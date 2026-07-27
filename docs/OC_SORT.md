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

## Honest finding (synthetic scope)

Across the synthetic regimes, OC-SORT's mechanics **do not help**:

- **Clean, near-linear motion + occlusion gaps:** exactly neutral (Δ=0, IDSW=0).
  The Kalman filter already nails linear motion, so there is nothing for ORU to
  re-anchor and OCM's directional prior is redundant.
- **High observation noise (8px jitter):** mildly *harmful* (MOTA −0.010, p<0.01;
  driven mostly by OCM). When observation noise swamps the motion signal, the
  observed-velocity direction is unreliable, so the momentum prior misleads and
  the virtual trajectory is built from noisy endpoints.

This is consistent with the project's recurring result: **a trick helps only in
its intended regime.** OC-SORT is designed for *genuinely non-linear* motion with
*clean* detections (sports/dance). The synthetic generator's linear motion can't
create that regime, so the fair test is **DanceTrack** (real non-linear dance
motion) — queued alongside the project's other DanceTrack-scale runs.

## Status
Implemented, tested (11 tests, `tests/test_oc_sort.py`), in the zoo as the
`oc_sort` preset. Fair non-linear real-data test (DanceTrack) deferred.
