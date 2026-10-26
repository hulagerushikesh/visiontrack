# Continuity warning v1 — complete development findings

Checkpoint: **2026-10-26**. This is a deterministic synthetic **development
screen**, not a real-world identity or false-alarm evaluation. The candidate
method was committed and pushed at `907891d19bc6034c396b4db7b35eda3050c99230`
before its first actual tracker execution. The [frozen protocol](CONTINUITY_WARNING_PROTOCOL.md)
and recipe SHA-256 `a6faf550f080834edf324698c59c7426ecad6824bf7f7f083e24dde0aadaa67f`
define the grid and decision gates. Tracker package bytes still match baseline
`7308dfbe8f79da61b56beed05784e56b512c156a`.

## Plain-language result

The offline warning detects a narrow, observable condition: two recent public
tracks have only one distinct current detector box available at IoU >=0.3. It
flagged the **first frame (36)** of every registered shared-box episode, with
no warning in the twelve clean controls. All registered development gates pass.
The warning is therefore eligible for *further diagnostic evaluation*.

It is **not ready as a user-facing identity warning**. In each target cell, it
appeared only once at episode onset, even for a 33-frame episode. It did not
occur within the predeclared previous-two-frame window of any recorded ID switch.
A genuine size-pulse control had tracker ID switches without any warning. The
same exact detector inputs also produced the same warning when the reference
described *one object with duplicate detections*, not two objects merging.
These are limits of what the warning observes, not reasons to move the v1 gates.

## Complete registered grid

Each row is one 96-frame cell. `Warn` is the number of warning frames (all six
targets and all three duplicate-single cases warn at frame 36 only). `Opp` is
the number of frames in `[3,96)` with at least two previous public tracks, each
having a current eligible IoU edge (denominator 93). FN, FP, IDSW and Frag are
unrounded counts from the canonical CLEAR v2 evaluator at IoU 0.5. These are
synthetic, related cells; do not pool them into a population estimate.

| Family | Episode frames | Warn | Opp / 93 | FN | FP | IDSW | Frag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| crossing_distinct | 3 | 0 | 93 | 4 | 0 | 0 | 0 |
| unchanged_control | 3 | 0 | 93 | 4 | 0 | 0 | 0 |
| scale_pulse_pair | 3 | 0 | 91 | 8 | 0 | 4 | 0 |
| motion_turn_pair | 3 | 0 | 93 | 4 | 0 | 0 | 0 |
| shared_union | 3 | 1 | 90 | 10 | 1 | 0 | 2 |
| missing_second | 3 | 0 | 89 | 7 | 0 | 0 | 1 |
| exit_new_entrant | 3 | 0 | 89 | 4 | 0 | 0 | 0 |
| coincident_two | 3 | 1 | 90 | 7 | 0 | 0 | 1 |
| duplicate_single | 3 | 1 | 90 | 2 | 91 | 0 | 0 |
| crossing_distinct | 9 | 0 | 93 | 4 | 0 | 0 | 0 |
| unchanged_control | 9 | 0 | 93 | 4 | 0 | 0 | 0 |
| scale_pulse_pair | 9 | 0 | 91 | 8 | 0 | 4 | 0 |
| motion_turn_pair | 9 | 0 | 93 | 4 | 0 | 0 | 0 |
| shared_union | 9 | 1 | 84 | 21 | 5 | 0 | 2 |
| missing_second | 9 | 0 | 83 | 13 | 0 | 0 | 1 |
| exit_new_entrant | 9 | 0 | 83 | 4 | 0 | 0 | 0 |
| coincident_two | 9 | 1 | 84 | 13 | 0 | 0 | 1 |
| duplicate_single | 9 | 1 | 84 | 2 | 85 | 0 | 0 |
| crossing_distinct | 33 | 0 | 93 | 4 | 0 | 0 | 0 |
| unchanged_control | 33 | 0 | 93 | 4 | 0 | 0 | 0 |
| scale_pulse_pair | 33 | 0 | 89 | 12 | 0 | 2 | 0 |
| motion_turn_pair | 33 | 0 | 93 | 4 | 0 | 0 | 0 |
| shared_union | 33 | 1 | 58 | 59 | 17 | 1 | 4 |
| missing_second | 33 | 0 | 57 | 39 | 0 | 1 | 1 |
| exit_new_entrant | 33 | 0 | 57 | 6 | 0 | 0 | 0 |
| coincident_two | 33 | 1 | 58 | 39 | 0 | 1 | 1 |
| duplicate_single | 33 | 1 | 58 | 2 | 59 | 0 | 0 |

## Integrity and interpretation

- All **27 cells**, **108 tracker passes** and **10,368 frame updates** completed
  under the committed method. All four public-output JSON records per cell were
  byte-identical; the three monitored warning records were byte-identical.
  Every unchanged control and both different-truth/same-detector pairs had the
  required identical public output and warning. This checks deterministic
  replay, reset and observer non-interference; the passes are not independent
  trials.
- All six target cells had an episode warning at frame 36 (delay 0 <=2). All
  twelve clean-control cells had zero warnings. The least opportunity coverage
  among clean controls was **89/93**, above the fixed `10*opp >= 9*93` gate.
  The stored screen has `passed: true`, `issues: []`.
- The missing-second family had zero warnings at all durations. This observer
  does not claim to find every missing detection or lost identity. For the
  long shared-union and coincident-two cells, an IDSW occurred later, but their
  single warning at 36 was not within `[s-2,s]`; **0 of 13** canonical switches
  across all cells was covered by that short descriptive window. Scale-pulse
  produced **4, 4, 2** switches
  across durations without warning. Zero warning therefore cannot certify
  continuity.
- `exit_new_entrant` has the same detector payload as `missing_second` but a
  different reference lifecycle. `duplicate_single` has the same detector
  payload as `coincident_two` but one reference object instead of two. The
  tracker and observer give the same outputs for each pair because neither sees
  reference truth. Duplicate-single warns despite **zero** reference switches
  and has large canonical false-positive counts from its extra detector row.
  This directly limits any physical-person or cause claim.
- At crossing co-location, canonical matching can choose a deterministic tie.
  These reference IDSW counts do not independently establish physical identity.
  All reported metrics are conditional on these synthetic labels and the
  evaluator, and all frame-level failures and matches remain in the private
  saved records.

The read-only saved-record audit verified **245 files** against the success
manifest, then independently recomputed scalar IoU, connected components and
exhaustive matching capacity for **2,592 frames and 4,169 components**. The
manifest SHA-256 is
`f538bfbdffffbe34581bfd728f6809ece4bbaf3850e394b2595bb778f9567134`.
The private result folder is the sibling workspace's
`visiontrack-walkthrough/continuity-warning-itg0Sm/study`; it contains no image
bytes and is not part of either Git repository. This audit checks saved arithmetic
and coverage, not independent physical labels or real-world utility.

## Decision and next evidence gate

**Pass the registered development screen; keep the diagnostic offline.** Do not
add an identity-safety badge, automatic tracker correction, default change or C++
port. Before considering a user-facing diagnostic, choose the target decision
(for example, an engineer inspecting count/flow continuity), collect permitted
representative detector outputs with independent reference review, and
prospectively measure warning burden, useful onset coverage and misses. A new
rule that persists across a gap or incorporates other observations requires a
separate v2 design and fresh evidence; v1 is not retuned here.
