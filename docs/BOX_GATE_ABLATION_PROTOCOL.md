# Box-gate ablation v1 — the next bounded research question

Locally registered **2026-10-23, before new comparative outcomes**. This is a
prospective repository protocol, not an external preregistration or a completed
experiment. The implementation harness and new held-out opening are **not yet
frozen**. No tracker, website or C++ behavior changes with this document.

## The question in plain language

A walker can move smoothly while their detection rectangle suddenly shrinks.
The tracker checks both rectangle overlap and whether the new rectangle is
plausible under its predicted state. That second check includes centre,
width-to-height ratio and height (`xyah`), not just position. Could it reject a
useful detection because the **rectangle changed**, and consequently break an ID?

We will compare the same unchanged tracker with that second check **on versus
off**, using one existing setting. Turning it off can also allow wrong matches,
especially between nearby objects. We are testing that trade-off, not assuming
that disabling a safety check is an improvement or a novel tracking algorithm.

The [completed traffic characterization](TRAFFIC_RELIABILITY_FINDINGS.md)
motivates this hypothesis; it does **not establish this cause**. In particular,
its missing crossings may result from anchor displacement as well as association
failures. Restoring an ID does not automatically restore the correct crossing.

## Exactly one intervention

- Baseline: the full explicit configuration and package source from the
  [original protocol](TRAFFIC_RELIABILITY_PROTOCOL.md), revision
  `16c287a6b18c5c142a28e4bce70b3232946459db`.
- Candidate: only `use_mahalanobis_gating=false` instead of `true`.
- Keep the same Kalman filter, IoU threshold, class constraint, assignment,
  confirmation, track lifetime, raw detections, scores and public-row semantics.
  Appearance, residuals, soft uncertainty, momentum, ORU and GMC remain off.
- In the current source this switch affects the high-score confirmed and
  tentative matching stages. Low-score recovery already uses no Mahalanobis
  gate, and all planned scores are 0.9, so this is **not a low-score recovery
  experiment**. The gate being ablated is the four-dimensional `xyah` gate,
  not a newly implemented position-only gate.
- No truth-assisted association, gap filling, ID merging, lifetime increase,
  anchor change, detector change or calibrated geometry intervention.

Source inspection motivating the switch: `ByteTracker._match` computes the gate
from `xyxy_to_xyah`, while `_observations` returns only confirmed tracks updated
on that frame. These statements describe our code, not another system's internals.

## New paired inputs, not another opening of the old test set

The machine-readable definition is
[`experiments/box_gate_protocol_v1.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_protocol_v1.json).
Its lock binds this document and the JSON; the parent recipe's two exact hashes
are also checked. Only the following fields are replaced: protocol identity,
purpose, scenarios, split seeds and execution/evaluation policy. All named
`inherit_unchanged` fields retain their parent equations and values.

Read-only integrity check from the repository root:

```bash
PYTHONPATH=src python -m experiments.box_gate_protocol
```

This verifies reviewed bytes only. It does not generate random detections,
execute tracking, freeze an implementation or produce research results.

In particular: 300 frames at 30 fps, the two exact projections, ideal sprite
boxes, paired PCG64 edge noise, 35% bottom/top pulses at frames [135,165) and
[210,240), four conditions, public-row anchors, crossing tolerances, 30-frame
count windows, IoU-0.5 reference matching and all 37 endpoints remain fixed.
Linearly interpolate each new path over frames 0..299 as in the parent recipe.
Ten seeds repeat noise, **not independent camera sites**. Each variant consumes
identical immutable detections and has separate fresh/reset/fresh passes.

| Split | Path | Object start → end in toy world coordinates | True crossing frame |
| --- | --- | --- | --- |
| Development | solo | (-2.4,3) → (-2.4,17) | 149.5, within bottom pulse |
| Development | separated | (-2.8,4) → (-2.8,18); (2.8,16) → (2.8,2) | 128.142857, before pulse |
| Development | close opposing | (-0.15,2) → (-0.15,16); (0.15,18) → (0.15,4) | 170.857143, after pulse |
| Held-out | solo | (2.6,17) → (2.6,3) | 149.5, within pulse |
| Held-out | slanted opposing | (-3.6,2) → (-1.4,16); (3.6,18) → (1.4,4) | 170.857143, after pulse |
| Held-out | close opposing | (-0.12,4) → (-0.12,18); (0.12,16) → (0.12,2) | 128.142857, before pulse |

The displayed frame decimals are explanatory; scoring uses unrounded float64
coordinates/times. New seeds are 2001..2010 for development and 4001..4010 for
held-out, disjoint from both old sets. New paths are not identical to an old
path. Inspecting deterministic geometry for validity is allowed; executing
tracking on the new held-out set before its gate is not.

The close paths deliberately have overlapping ideal sprites near their meeting
point to challenge association. Detections remain independent boxes: this does
not simulate an actual detector's mutual occlusion or prove that identity is
visually recoverable. The other paths provide less ambiguous comparisons.
Crossing timing now includes before/during/after-pulse cases, rather than always
coinciding with the bottom truncation. This small six-path design still has
limited domain coverage; a new seed is not a new domain.

Per split: **120 paired input cases × 2 variants = 240 variant runs**. Each has
three deterministic passes, making 720 replays per split, 1,440 over both splits.
Keep every case and variant, not just favorable examples. The registered order
is scenario, seed, condition, variant, using their JSON list order.

## Decision rules fixed before implementation

Define `primary(s,variant)` as the mean of `ID_switch_count / reference_object_count`
over the **20** cases comprising ten seeds × `box_error_only` and `combined`,
separately for each scenario. Object count is fixed by the input recipe, not
the number of detections or returned IDs. Do not pool different scenarios.

1. **Adequate challenge:** at least two of the three scenarios in **each** split
   must have baseline primary ≥ 0.5 switches per reference object. Otherwise
   classify the study as inconclusive, not successful because nothing broke.
2. **Practical benefit:** in at least two scenarios in each split, reduce primary
   by both **≥25% relative** and **≥0.5 switches per reference object absolute**.
   A qualifying scenario must itself meet the adequate-challenge threshold.
   The absolute margin requires at least ten fewer switches across the 20
   one-object runs, or twenty fewer across the 20 two-object runs; it avoids
   presenting one isolated switch as the whole practical improvement.
3. **Conservative non-regression:** in **every paired case**, all four conditions
   included, candidate ID switches, missed object-frames, FP rows, primary
   bottom-centre misses+extras and absolute window-count error must each be
   ≤ baseline. One violation blocks acceptance; no averaging away a harmful
   close-object or clean-control case. More matched frames cannot excuse a
   new false crossing or identity switch.
4. **Retain everything:** report all 37 endpoints for each variant, candidate
   minus baseline differences, defined/missing counts, per-seed values and
   per-scenario mean/range. Contact/timing errors remain conditional diagnostics,
   not substitute primary endpoints. Null is not zero. The secondary box centre
   cannot replace bottom centre after results are seen.

These are deliberately conservative **engineering screening margins**, not
industry standards, a statistical power calculation or a proven safety bound.
Passing would support only a synthetic association benefit without the listed
regressions. It would not establish improved contact localization, improved
counting (which may be unchanged), real traffic accuracy or a production default.

Decision order: incomplete/invalid evidence or inadequate challenge →
**inconclusive**; otherwise any non-regression violation → **failure**;
otherwise no paired difference in any registered endpoint → **no effect**;
otherwise missed benefit margins → **failure**; otherwise → **pass**.
No effect is a negative result, not acceptance. All outcomes must be retained.

## Execution gates and what remains

- [x] Choose one switch, fixed comparator and explicit unchanged settings.
- [x] Register fresh paths/seeds, numerical margins and negative-result rules.
- [x] Bind exact protocol bytes and validate geometry/configuration without
  generating new random inputs or executing new tracker outcomes.
- [ ] Build a separate input/replay/report harness; keep old v1 files immutable.
  Test hand-worked cases, candidate isolation, metric definitions, full case
  coverage, null handling, no-effect/failure decisions and all one-pass guards.
- [ ] Commit the harness before the full development grid. Record actual
  source/config/environment/input/output digests and three-pass equality.
  Development outcomes may diagnose defects, not tune this v1 candidate,
  margins, input selection or acceptance criteria.
- [ ] Freeze the entire reviewed harness, environment and new held-out input
  hashes after development, then open the **new** held-out grid once with an
  exclusive claim. Stop on first error, keep partial evidence, no silent retry.
- [ ] Independently reconstruct results from retained artifacts and publish
  failures/no-effect as faithfully as gains. A defect needs an explicit new
  version/amendment; an opened test set cannot become untouched again.
- [ ] Only after the fixed gates pass, consider representative licensed/consented
  detector data, then separate production-default and Python/C++ handoff reviews.

The original v1 development and held-out sets are already opened and may only
inform hypothesis generation, not untouched acceptance. This protocol does not
modify their source locks, raw records or consumed opening claim. The remaining
owner recording rehearsal, RQ5 re-entry work and practitioner validation stay
separate. No new meeting, data request or upstream contribution is authorized.
