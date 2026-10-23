# Development-only internal tracing: preparation

**2026-10-23. Tool and test milestone, not a diagnostic study replay.**
The completed box-gate experiment remains a **failure**, and its defaults,
protocols, held-out opening and C++ implementation are unchanged. The preceding
[saved-output diagnosis](BOX_GATE_DIAGNOSIS.md) establishes symptoms, not their
internal causes. This tool prepares the next question: what did the tracker
actually predict, reject, match, update and publish?

## What this adds

`experiments/box_gate_trace.py` is an opt-in, in-memory observer outside the
installed package. It temporarily uses Python's current-thread profiling hook
to copy locals from the **actual calls** made by an otherwise unchanged
`ByteTracker.update`. It does not replace association, recompute a distance,
update the filter twice, inject detections or change any configuration.

| Recorded item | Meaning |
| --- | --- |
| Input detection ordinal, box, score and class | Position in this frame's supplied list, never a ground-truth/person identity |
| Three association stages | Confirmed/high, remaining-confirmed/low recovery, tentative/leftover-high |
| Actual IoU, class mismatch, squared 4D xyah Mahalanobis distance and active threshold | Matrices already computed by the tracker; absent calculations stay `null` |
| Actual forbidden mask, weighted cost, maximum cost | Captured directly from the existing cost builder, not a reconstructed veto |
| Hungarian proposals and accepted/unmatched indices | Distinguishes a proposed assignment from a returned accepted match; unassigned does not imply every pair failed a gate |
| Predicted and pre/post-match state | Mean, full covariance, box, class, score, hits, age, freshness and lifecycle |
| Spawn, missed/deleted transitions and final public rows | Connects internal decisions to published boxes; confirmed-but-not-updated tracks are not public outputs |

Array rows/columns follow the recorded track list/detection ordinal mapping for
that stage. Exact-distance equality is allowed by the existing hard gate;
only distances **greater** than the active threshold are forbidden. The recovery
stage does not request the hard Mahalanobis gate. With gate-off and zero
uncertainty weight, no Mahalanobis distance is calculated: `null` does **not**
mean zero or an independently measured passing distance.

Snapshots are detached JSON-compatible copies. There are no image bytes,
appearance embeddings, network requests, file writes, CLI or held-out entry.
Boxes/states are still research data, not a reason to expose private footage.

## Bounded selection fixed before replay

For a future complete 300-frame development sequence, retain:

- Startup frames `[0,4)`.
- First pulse and recovery boundary `[133,168)`.
- Second pulse and recovery boundary `[208,243)`.
- The union of **all saved predicted bottom-centre crossing times from both
  variants**, including extra crossings. For each time `t`, include frames
  `floor(t)-1` through `floor(t)+2`, clipped to the frame grid.

The same selection applies to both variants and controls. This covers the
previously observed pre-pulse extra crossing near frame 127, not just the box
pulses. No selection is based on newly observed trace outcomes. Refuse more than
128 selected frames, 32 detections/tracks, 300 input frames or 4,096 events;
never silently truncate. Continue all updates, including unselected frames,
and compare **the complete public output**, not only traced windows.

## Parity is required, but provenance is a separate gate

`observe_sequence` requires a fresh exact `ByteTracker`, explicit bounded
feature-free detections, selected frames and expected public rows. Only the
baseline/default settings or its single gate-off switch are supported. Canonical
JSON output bytes must equal expected bytes exactly: no tolerances, sorting,
rounding, rematching or accepted numeric-type drift. A mismatch raises
`ParityMismatch` carrying the failed diagnostic with both output hashes.

The observer itself **does not authenticate the expected rows or source data**.
Every returned record therefore keeps `provenance_verified`,
`interpretation_allowed` and `validation_evidence` **false**, even when exact
output parity passes. A future development-only runner must separately verify
the original index, saved bundle hashes, selector, baseline source/configuration,
input payload and all expected rows before authorizing exploratory inspection.
Parity with a caller-created list alone is not saved-study parity or validation.

The observer refuses an existing profiler/debugger or a non-main-thread call.
The temporary hook is removed in `finally`, including tracker/callback failures;
do not share the observed tracker concurrently. After any failure, retain the
failure externally and discard the partially advanced tracker—no resume/retry
inside the old study. Profiling adds overhead and **cannot measure performance**.

## Verified now, and still pending

Implementation tests use short, explicitly authored sequences. They check exact
public outputs and final internal state against unobserved runs, detached
snapshots, all stages, startup/confirmation, recovery, class/IoU/4D vetoes,
deletion/expiry, raw solver proposals, no extra Kalman/gating calls, strict parity,
budgets, selection, existing hooks and cleanup on errors. These fixtures are not
the registered grid, held-out observations or an explanation of the saved failures.

- [x] Specify bounded tracing and test the opt-in observer outside production.
- [ ] Build a clean-revision development-only replay wrapper that authenticates
  saved evidence and inputs first, preserves a new trace/failure receipt, and
  checks complete exact output parity before permitting interpretation.
- [ ] Commit that wrapper and its tests **before** the new diagnostic replay.
- [ ] Run the disclosed exploratory development replay, retaining failures;
  inspect actual decisions without reopening held-out tracking.
- [ ] Choose a narrower hypothesis from that evidence. Any new intervention
  needs a separate registration and genuinely fresh validation cases.

No owner recording, cloud setup, new outreach or C++ port is required for this
preparation step. The separate recording/usability/practitioner gates remain open.
