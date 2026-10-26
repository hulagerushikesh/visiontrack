# Observation availability — prospective development study v1

## Why this is next

The [MOT17 inventory](MOT17_ASSOCIATION_INVENTORY.md) distinguishes a missing
neighbour, two references supported by one box, and a pair not offered to an
already matched track. It does **not** establish a physical cause or a fix.
This small study asks what the **unchanged** tracker reports when known toy
trajectories receive different supplied observations. No detector is trained.

For a beginner: two people can continue moving while the detector supplies only
one box. An internal track can survive without appearing in public outputs.
When boxes return, the old tracking number may resume or a new one may appear.
We will measure these separately rather than calling every gap “forgotten.”

## Freeze before any actual study replay

The committed [machine recipe](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/observation_availability_v1.json)
and implementation/test commit precede actual execution. The receipt records
that commit, exact recipe/source hashes and runtime. Author-written geometry
and scoring fixtures are permitted before execution; no actual tracker study
outcomes are used to revise the recipe. This is a prospective **development**
characterization informed by an already inspected real episode, not a blind
held-out test or a claim of external preregistration.

### Fixed scene and all 12 cells

Two 20 × 40 rectangles move right by 2 pixels/frame, at y=100, starting x=100
and x=108. They remain eight pixels apart; this is not a crossing/re-entry or
realistic pedestrian rendering. Each reference exists throughout the sequence.
The full truth is identical across conditions of equal duration. Stable source
row order is first then second; no appearance features, jitter or randomness.

Frames are **zero-based**: 12 warmup frames, a 4-, 12- or 36-frame observation
episode starting at 12, then exactly 20 recovery frames. These durations bracket
the unchanged max-age of 30; they are not tuned after outcomes. Each input box
has score 0.9 and class 0, including the shared box.

| Condition | During the episode | Outside the episode |
| --- | --- | --- |
| distinct | Both exact reference rectangles | Both exact rectangles |
| unchanged_control | Byte-identical copy of distinct | Byte-identical copy of distinct |
| missing_second | Only the first reference rectangle | Both exact rectangles |
| shared_union | One enclosing union rectangle for both references | Both exact rectangles |

At diagnostic IoU ≥0.5 the distinct boxes support only their own reference
(cross-IoU 3/7), missing_second supports only the first, and shared_union supports
both (IoU 5/7 each), but can be assigned only once. Distinct observations can
overlap spatially; “distinct” does not mean disjoint boxes or known identity.
The two degraded conditions both supply one box but change its location/shape
as well as its support pattern. Their contrast is **not** a geometry-free causal
effect of ambiguity. Capacity is descriptive, not achievable tracker recall.

### Tracker and measurement contract

- Exact package source at `7308dfbe8f79da61b56beed05784e56b512c156a`, all 20
  default settings explicitly recorded in the recipe. No candidate setting.
- Each cell runs fresh, reset, then a second fresh instance; require exact
  public-output JSON bytes for all three. Keep failed attempts, do not tune/retry
  selectively. Require unchanged_control input and complete result equality
  with distinct for each duration. Repeatability is not independent validation.
- Only copied detection xyxy, score and class reach the tracker. Reference IDs
  and truth reach the evaluator only. No camera, images, model, GT-assisted
  tracker assignment, MOT17 data or C++ execution.
- Every frame, detection, public observation, canonical CLEAR v2 failure and
  matched reference→track correspondence is retained. Matching uses the existing
  canonical accumulator at IoU 0.5; reading its last-match map after excluding
  missed references is diagnostic only and never affects the tracker.
- Report unrounded CLEAR totals **and** startup [0,2), settled warmup [2,12),
  episode [12,12+d), recovery [12+d,32+d) event counts. Startup confirmation
  misses are retained, not deducted from headline FN. Stratum IDSW/fragmentation
  preserves whole-sequence matching history; strata are not rescored in isolation.
- For **both** references, retain the match at 11, first matched frame in the
  recovery interval, its delay from 12+d, and whether that match has the same
  ID. If no recovery match, frame/delay/ID/same-ID are null, not zero/false.
  First recovery match is not proof of stable later identity; full history stays
  available. A surviving internal track alone is not a public match.
- Report each cell's FN/FP/IDSW/fragmentation deltas from its own equal-duration
  distinct control. No averaging across lengths or choosing a winner.

## Decision and stop rules fixed in advance

This is characterization, so **no accuracy acceptance/pass margin or adoption**
is defined. Null effects, switches, poor recovery, startup effects and harms are
all reportable outcomes. Fail on source/config/recipe drift, incomplete coverage,
input mutation, nonfinite output or fresh/reset/control mismatch. Retain the
method and partial cell artifacts plus a failure receipt; no success manifest
on failure. Existing output directories, symlinks and outputs inside either repo
are refused. A new success manifest requires all 12 cells and all checks.

Publish recipe, code, tests and a small all-cell numerical findings table, not
private MOT17 pixels or participant records. The local execution bundle remains
outside Git. One fixed two-object geometry cannot establish prevalence,
real-detector behavior, general accuracy, novelty, re-entry recognition, the
physical cause of the street episode or transfer to OpenTrafficCam.

## After this study

1. Audit retained records and all-cell comparisons without another tracking run.
2. Write the understandable finding and its limits, including any null/harm.
3. Decide whether a specific observation/association question warrants a new
   prospective comparison with fresh evidence. Do not turn this study into
   tuning on the known MOT17 episode or resurrect rejected gate-off changes.
4. Keep representative permitted real-data validation and independent physical
   label review open. C++ changes require separately accepted useful behavior;
   this diagnostic alone does not create a porting milestone.
