# Crossing-band v1 — isolated counter implementation

Checkpoint **2026-10-23**. The [registered definition](CROSSING_BAND_PROTOCOL.md)
and its byte locks are unchanged. Its original checklist describes the point of
registration; this page and the [current checklist](NEXT_STEPS.md) track later
implementation. This is **unit-level preparation, not a completed study**.

## What was built

`experiments/crossing_band.py` accepts typed world-coordinate anchor samples,
checks the registered definitions, and returns immutable records for either
`legacy` or `band`. It neither executes a tracker nor generates observations,
reads saved study outcomes or writes results. The future adapter must supply
the **same projected public rows** to both counters. No production package,
website, public-output rule, association setting or C++ code changes here.

- Legacy uses the frozen adjacent line-arrival arithmetic and first valid
  event per ID/direction. It separately records the actual arrival sample's
  integer frame, **not** `ceil(interpolated_time)`: floating-point rounding can
  put the interpolated time exactly on the preceding integer.
- Band waits for an observed stable origin, tracks a pending line arrival,
  cancels on a strict return to the origin half-plane, and confirms only at
  the opposite stable boundary. Exact-line dwell preserves the pending arrival.
- The crossing's interpolated X, not confirmation X, controls the half-open
  segment. Confirmations outside the segment or already counted still change
  the stable side; they cannot consume a later first valid event accidentally.
- Gaps cancel pending state and reinitialize the origin, but do not reset the
  run-wide first-event ledger. IDs are never joined. End-of-input pending events
  are retained as unfinished, never flushed into counts.
- Inputs are sorted by frame/ID without modifying supplied records. Duplicates,
  wrong record types, out-of-grid frames, capacity overflow and nonfinite
  interpolation arithmetic raise errors instead of dropping problematic rows.

There are no tuning, truth, smoothing, dwell or gap-filling arguments.

## Records and timing

`CountResult.emissions` retains each `CrossingEvent` and its integer
`emission_frame`. `delay_frames` is reporting frame minus original interpolated
arrival time. A delay above 15 frames is **retained**, not suppressed; evaluation
must flag it as unsafe. No events gives `maximum_delay_frames = None`, not zero.

Results are ordered by original arrival time/ID/direction. They are **not**
necessarily ordered by reporting time. The future evaluator must use each
emission frame when computing reporting-window errors, not its position in the
list or backdated crossing time. The window scorer is not implemented here.

Every band pending arrival has a `PendingRecord`: original event, adjacent
arrival sample frame, closing frame and disposition. Dispositions are
`emitted`, `outside_segment`, `already_emitted`, `return_to_origin`, `sample_gap`
and `end_unconfirmed`. The last has no closing frame: there was no observation
that confirmed or canceled it. The derived diagnostic counts retain all fates;
legacy has no pending state and therefore zero pending diagnostics.

## What the authored examples establish

| Supplied anchor Y values | Legacy | Band | Interpretation |
| --- | --- | --- | --- |
| 9 → 11 | One arrival at frame 0.5, reported at 1 | Same event/report | Ordinary adjacent through passage |
| 9.7 → 10.05 → 9.8 | Two directional arrivals | None | Could be noise **or genuine shallow movement**; observations alone cannot distinguish them |
| 9.9 → 11 | One arrival | None | Unknown-origin censoring can miss a real passage |
| 9 → 10.1, then input ends | One arrival | None, pending retained | No terminal confirmation |
| 9 → 10 → seventeen samples at 10.1 → 10.25 | Arrival at 1, reported at 1 | Same arrival, reported at 19 | Eighteen-frame delay exceeds the registered 15-frame limit |

When the shallow/start/end examples are interpreted as **ideal real paths**,
their legacy truth is unchanged and the suppressed events are misses. The
unit tests deliberately assert that unfavorable result. They do not relabel
real passages as noise or claim the counter can infer which explanation is true.
An additional boundary example has identical event timestamps but band reporting
in the next 30-frame window: backdating does not remove reporting error.

## Verification and next gate

**64 authored tests** cover both directions, exact/next-float stable and segment
boundaries, line dwell, latest arrival after cancellation, gap/ID isolation,
first-event persistence, ordering, interpolation/rounding, final frame, delayed
emissions, missed real passages, validation and immutability. Exhaustive small
diagrams check all **625 four-sample Y combinations** against the frozen legacy
extractor, and candidate uniqueness/stable-confirmation invariants. These are
hand-defined synthetic unit diagrams, not registered random cases or research
performance measurements. Spies also require definition-only read access and
reject tracker construction, random generation or file writes.

```bash
python -m pytest tests/test_crossing_band.py -o addopts='' -q
PYTHONPATH=src:. python -m experiments.crossing_band_protocol
```

Before investing in the complete study, review these **structural safety costs**
against the intended crossing task. This rule cannot universally improve the
unchanged line-arrival target. A unit feasibility rejection would be a valid
engineering stop, **not** an executed development/held-out verdict. Do not tune
the band, drop genuine short crossings, or rewrite the locked v1 protocol to
rescue it. Any changed research question needs a separate prospective version.

If the original screen is still useful to quantify its limits, the next work
is a separately committed input/replay/report harness: shared rows, all 37
parent endpoints, actual emission-window errors, every pending fate/delay,
fresh/reset/independent passes, full coverage and exclusive failure-preserving
execution. No registered noisy inputs or tracker outcomes have been generated
for this counter checkpoint; no held-out set has been opened. C++ adoption is
not authorized by implementing or testing an experiment.

## Feasibility decision — 2026-10-23

**Stop this candidate at the engineering feasibility gate; do not build its full
grid harness as the next task.** The authored ideal-path examples already show
structural misses of genuine shallow/start/end passages and an 18-frame reporting
delay against the intended unchanged crossing target and 15-frame bound. The
same observed recrossing can represent noise or genuine movement; this rule has
no additional information to distinguish them. This does not assert that every
registered noisy case fails, or that the registered grid was executed.

The fixed rule, original registration/locks and tests remain unchanged and
retained. There are no new noisy inputs, development/held-out results, acceptance
decision or production/C++ changes. Full-grid execution/audit is **not undertaken**,
not completed and not required for this engineering stop. Quantifying this
negative design could be a separate explicitly justified future task, but we will
not silently tune it, redefine truth or turn the same set into fresh validation.

Next prioritize an understandable existing-report demonstration and one permitted
real-clip diagnostic case study, as scoped in the [showcase milestone](SHOWCASE_MILESTONE.md).
The purpose is useful evidence and workflow feedback, not another unvalidated fix.
