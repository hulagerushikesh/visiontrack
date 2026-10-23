# Crossing-band v1 — isolate counting from tracking

Locally registered **2026-10-23**, before this study's random observations or
tracker outcomes. This is a prospective repository registration, not an external
preregistration, completed study or accepted product change. The complete replay
and held-out harness is **not frozen yet**.

## Why this is the next action

The [completed internal traces](BOX_GATE_TRACE_FINDINGS.md) establish two
different mechanisms in specific development examples: a shape-sensitive gate
can reject a detection, and a noisy updated box anchor can recross a counting
line **without changing ID**. The gate-off study failed its safety criteria.
Combining a new association rule and a new counter now would obscure which
change caused a benefit or regression.

We will first isolate **counting only**. Keep the full original tracker,
including its enabled 4D gate, confirmation and public-output rules. Feed the
**same immutable public rows** to two counters. Any claimed change to identity,
boxes, detections or localization is an invalid experiment, not an improvement.
Association/shape robustness remains a separate later question.

## One candidate, no parameter sweep

Baseline is the unchanged first line arrival per local ID and direction from
`experiments/traffic_crossing.py`. Candidate requires reaching the other side
of a fixed **0.25 toy-world-unit half-band** around Y=10. This number is a
prospective screening choice, not an optimized setting or a real-camera metre
calibration. No dwell-time threshold, smoothing, gap filling or identity joining.

For example, a box anchor can move from Y=9.7 to 10.05 and back to 9.8. The
baseline records its positive arrival at the line; the candidate does not
confirm a passage unless it reaches Y=10.25. That can reject jitter, **but a real
person could genuinely cross only slightly and turn back**. Such a passage must
remain in the ground truth and count as a miss if the candidate suppresses it.
We will not redefine “crossing” after seeing results to make the candidate pass.

### Exact state and boundary rules

1. Sort unique integer-frame/local-ID anchor samples. The origin side is known
   only after Y <= 9.75 or Y >= 10.25. Starting inside the band is unknown, not
   an inferred negative/positive origin.
2. With a known origin, remember the latest adjacent-sample line arrival toward
   the opposite side, using the frozen strict/inclusive line rule and linear
   time/X interpolation. A strict return to the origin half-plane cancels it,
   including a return immediately after landing exactly on the line.
3. First arrival at the opposite stable side confirms the pending event. Retain
   its original line-arrival time and X, and separately retain the **integer
   confirmation frame**. Transition the stable side even when the pending event
   is outside the X segment or its ID/direction has already emitted.
4. Only -6 <= crossing X < 6 qualifies. Confirmation X does not substitute for
   crossing X. Keep the first confirmed in-segment event per ID and direction.
5. A gap other than one frame cancels pending state and reinitializes the side
   from the new sample. Never interpolate a gap, connect different IDs or reset
   the run-wide first-event ledger on a gap. No terminal flush: pending events
   at the final frame are unconfirmed, not manufactured counts.

Both counters therefore depend on the same available public boxes. A counter
cannot recover a deleted ID, an unpublished box or a physically displaced anchor.
Repeated visits beyond the first event per ID/direction are outside this v1
event policy; this is not a general traffic-flow counter.

## Fresh paths and fixed evidence

The exact definition is
[`experiments/crossing_band_protocol_v1.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/crossing_band_protocol_v1.json).
It pins both earlier protocol/doc pairs, inheriting the original 300-frame,
30-fps grid, projection equations, ideal sprite boxes, PCG64 observation recipe,
four conditions, default tracker settings, bottom-centre anchor and scorer.
It replaces paths, seeds, counter intervention and evaluation rules only.

Each split has **six one-object paths**, ten new seeds and all four original
conditions (control, perspective-only, box-error-only, combined): **240 inputs /
480 counter views per split**. Each input gets fresh/reset/independent-fresh
tracker passes, **720 passes per split**. Counters share each resulting vector;
this is not 480 independently executed tracker variants. All retained pass
outputs must agree exactly, including both counters' deterministic records.

| Path family | What it prevents us from overlooking |
| --- | --- |
| Through passage | Ordinary crossing and confirmation delay |
| Dwell near line, no true crossing | False counts from noisy anchors |
| Shallow genuine crossing and return | Misses hidden by suppressing small excursions |
| Full crossing and return | Legitimate opposite-direction events |
| Start inside band, then cross | Unknown-origin censoring |
| Cross late and end inside band | Unconfirmed final passages |

Development uses seeds **6001..6010**, held-out **8001..8010**, with different
piecewise-linear paths, directions and timings. Waypoints are exact frame/X/Y
triples in JSON; interpolate without rounding. At most two ideal truth events
fit the existing bounded scorer. Truth uses the **legacy line rule on ideal
paths**, never the candidate's band. Fresh seeds are not new camera sites.

The earlier opened traffic/box-gate evidence stays consumed and unchanged. New
protocol integrity checks may read their committed definitions, not their raw
held-out bundles. Do not reuse old validation or rerun the completed trace.

## What would count as useful, and what would block it

Primary is mean **missed + extra bottom-centre events**, separately per scenario,
over ten seeds and the two box-error conditions. Both splits must have at least
two scenarios with baseline mean >= 1.0. In at least two such scenarios per
split, require **>= 0.5 absolute and >= 25% relative reduction**. These are
conservative engineering screening choices, not powered statistical margins.

In **every input pair and every condition**, candidate misses, extras, their
sum, timestamp-based absolute window-count error and emission-time window-count
error must each be no greater than baseline. Retain all 37 inherited endpoints;
the tracking/localization entries must be identical by construction and checked
against the exact shared rows. No swapping in box-centre counts after results.

Backdating a confirmed event must not hide latency. For **every candidate event,
including extras**, confirmation frame minus stored line-arrival time must be
<= **15 frames**. Also score half-open 30-frame directional count windows using
the actual emission frame (baseline: arrival sample frame; candidate:
confirmation frame), against exact ideal crossing times. Keep both window tables
and every delay. No emitted events means null maximum delay, not “zero latency.”
Keep unconfirmed and canceled pending counts. Full records, all cases and nulls
are mandatory; per-seed repeats are not independent deployments.

Decision order is fixed:

1. Invalid/incomplete evidence -> **inconclusive**.
2. Any per-pair safety or delay failure -> **failure**, even with weak challenge.
3. Insufficient baseline challenge -> **inconclusive**.
4. Identical complete records/endpoints -> **no effect**.
5. Missing improvement margins -> **failure**; otherwise -> scoped **pass**.

The shallow/start/end paths deliberately expose likely costs of this rule. A
failure is useful evidence for rejecting or narrowing it, not a reason to drop
those cases, move the band or recast missed real events as successful abstention.
Even a pass would support only this synthetic screen, not a production default,
novelty, identity/localization improvement or transfer to OpenTrafficCam.

## Work checklist

- [x] Freeze this question, single intervention, fresh grid and decision rules.
- [x] Add a read-only byte-integrity preflight and structural/geometry tests.
- [ ] Implement the isolated counter and test hand-authored boundary, reversal,
  gap, start/end, segment and timing diagrams. These are unit tests, not results.
- [ ] Build and commit a separately versioned input/replay/report harness,
  preserving shared public rows, all cases, latency and failure evidence.
- [ ] Run the complete development grid once after source/runtime/input guards.
- [ ] Review without tuning v1, freeze the full harness/environment and genuinely
  fresh held-out inputs, then open once with an exclusive claim. Stop on first
  error, keep partial records, no overwrite/selective retry or hidden resumption.
- [ ] Independently audit retained outputs and publish positive/negative results.
- [ ] Only after separate representative rights-reviewed evaluation, consider an
  explicitly accepted deployment/handoff. C++ remains stable until that gate.

```bash
PYTHONPATH=src:. python -m experiments.crossing_band_protocol
```

This checks exact registered bytes and pinned parent definitions only. It does
not generate noisy observations, execute a tracker, inspect prior held-out data,
freeze the future harness or produce a research result. Byte locks are reviewed
Git integrity checks, not an external timestamp authority or tamper-proof seal.
No website, installed package, C++ behavior, release or outreach changes here.
