# Continuity warning v1 — a limited, testable diagnostic

Design checkpoint: **2026-10-26**. The observer, grid, replay and audit code are
implemented with hand-authored tests; **actual study tracking has not run at this
method-freeze checkpoint**. The recipe's `stage` records its original design-only
freeze and is intentionally unchanged.
The [machine recipe](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/continuity_warning_v1.json)
and this protocol precede candidate implementation and actual study tracking.
This is an internal prospective development design, not external preregistration,
an untouched validation set, a calibrated identity predictor or an accepted fix.
Recipe SHA-256:
`a6faf550f080834edf324698c59c7426ecad6824bf7f7f083e24dde0aadaa67f`.

## What we are trying to give a user

Imagine two tracking boxes in the previous frame. In the next frame, both overlap
one detector box, but there is no second distinct box to support both tracks.
The proposed message is: **“Recent tracks have insufficient distinct box support;
inspect this interval before trusting continuity.”** It does not say which person
is which, that an ID has switched, or that the detector merged two real people.

The [completed observation study](OBSERVATION_AVAILABILITY_FINDINGS.md) showed why
this matters: an ID can return unchanged and still switch later. It did not show
that this warning will work. We will first test whether the warning can identify
a narrowly observable situation without flagging every ordinary shape or motion
change. No tracker, memory setting, confirmation rule or website behavior changes.

## One frozen candidate, no hidden truth at runtime

For frame `f`, the observer receives **copied public observations from `f-1`**
and **copied detections for `f`**, before `ByteTracker.update` for `f`:

- Previous observations: frame, positive unique track ID, xyxy, score, class ID.
- Current detections: xyxy, score, class ID and original frame-local row index.
  Keep rows with score **>=0.1**. No appearance features or image bytes.
- All boxes must have finite float64 coordinates and positive width/height;
  scores finite in [0,1], integer classes/frames/IDs without bool/coercion.
  Require consecutive frames and the declared zero-based start. Invalid or
  skipped input is an explicit study failure, not an empty/all-clear result.
- No current public outputs, future frames, GT, evaluator matches, private track
  objects, Kalman predictions/covariance or actual association-stage decisions.
  It cannot silently peek at the surviving tracks after the current update.

Build a bipartite graph: previous public tracks on the left, eligible current
detection rows on the right. An edge requires equal class and **IoU >=0.3**.
IoU is scalar intersection/union with **no denominator epsilon** for these
positive-area boxes. This threshold is a diagnostic design choice, not the
tracker's complete matching rule; its gates and stage ordering are not modeled.

For each connected component with **at least two track nodes**, compute the
maximum one-to-one matching cardinality `k`. Emit one component warning if
`k < number_of_track_nodes`. A detection cannot support two assignments.
Isolated unsupported tracks are recorded separately, **not** collision warnings.
Preserve original row indices and sort track IDs/rows in records; duplicate rows
are still distinct observations. Do not deduplicate by coordinates or count edges
instead of assignment capacity. Retain a deterministic matching witness.

Report one record for **every frame**, including startup and no-warning frames:
input fingerprints; previous/eligible counts; all edges and IoUs; unsupported
IDs; every component's IDs/row indices/capacity/deficit; warning components.
Record whether two previous tracks have any support in that frame. At startup,
no previous output means **no opportunity to assess**, not verified continuity.
No warning means “no support shortfall observed,” never “identity is safe.”
For example, two tracks connected to two distinct rows can have capacity two
even if all four edges exist; their overlap alone must not trigger a warning.

After tracking, replace the snapshot with that frame's copied public outputs.
Memory is **one frame only**, reset at sequence reset; absent public IDs are not
carried forward or extrapolated. Warnings are frame-local, no sticky alert,
cooldown, gap join or invented persistent identity. Consecutive warnings with the
same sorted component IDs may be grouped *for reporting only*. One warning at
onset does not imply that the observer covers the rest of a long occlusion.

## Fresh, completely specified development inputs

Every cell has **96 frames**, zero-based `f=0..95`; episode `[36,36+d)` for
`d` in **3,9,33**. Recovery is `[36+d,96)`, not an equal-duration sample.
There is no randomness, noise, model, image, seed search or appearance vector.
All detections have score 0.9, class 0, feature None. Box from center `(x,y)` and
size `(w,h)` is `[x-w/2,y-h/2,x+w/2,y+h/2]` in pixels, without clipping/rounding.

Default reference A has center `(120+1.5*f,180)`, reference B
`(270-1.5*f,180)`; both size **28 x 56**, reference IDs 1 and 2 throughout.
They cross at frame 50, including exact co-location; reference annotations do
not make their visual identities observable. Write A then B in detector order.
Truth is evaluator-only and stored separately from observer/tracker payloads.

| Family | Complete recipe | Purpose |
| --- | --- | --- |
| crossing_distinct | Supply exact A and B every frame | Crossing with two distinct rows, even when they overlap |
| unchanged_control | Exact byte copy of crossing_distinct inputs and truth | Unchanged-input/output/warning control |
| scale_pulse_pair | Both centers x=`120+1.5*f`, y=96/320; multiply both reference sizes by 1.5 during episode, otherwise 1; supply both exact boxes | Genuine abrupt size change, not shared support |
| motion_turn_pair | Both centers x=`120+1.5*(f-2*min(max(f-36,0),d))`, y=96/320; sizes unchanged; supply both exact boxes | Genuine reversal then resumption, spatially separated |
| shared_union | A/B truth unchanged; replace their two detections with the enclosing union during episode, otherwise exact A/B | Target: one row competing for recent tracks |
| missing_second | A/B truth unchanged; omit B during episode, otherwise exact A/B | Limitation: a missed object need not create a shared component |
| exit_new_entrant | **Same detector bytes** as missing_second; truth A=1 throughout, B=2 only before episode, absent during it, B=3 after | Identical observations cannot tell a gap from exit/new entrant |
| coincident_two | Both references follow A's exact box; supply two identical rows outside episode, one during | Target at the observability boundary |
| duplicate_single | **Same detector bytes** as coincident_two; truth is only reference 1 following A throughout | Duplicate detections of one object can mimic merged support of two |

There are **27 registered cells**, but only **16 unique complete detector
payloads**: unchanged controls, repeated distinct paths and the two semantic
pairs intentionally reuse inputs. They are not 27 independent scenes. The
coincident/duplicate cases are deliberate synthetic boundary constructions, not
claims about physically distinguishable people or realistic detector behavior.
Count unique inputs from ordered frame/xyxy/score/class payloads only, excluding
family/duration tags and truth. At co-location, evaluator tie choices and GT
IDs cannot establish physical identity; retain deterministic canonical matches
and their overlaps without presenting the resulting IDSW as independent truth.

Do not score exit_new_entrant or duplicate_single as ordinary benign controls:
the identical observable records force the same warning as their paired family.
Retain that semantic nuisance burden openly; excluding these from the clean
control gate does **not** make them real-world false-alarm successes.

## Measurements and decision fixed before implementation

Use the exact unchanged package at
`7308dfbe8f79da61b56beed05784e56b512c156a`, with all 20 default settings
recorded explicitly in the recipe. No preset, candidate tracker or C++ run.

Each cell needs monitored fresh, monitored reset, monitored second-fresh, then
unmonitored fresh: **108 tracker passes / 10,368 frame updates**. Require exact
public-output JSON bytes in all four, and exact warning records in the three
monitored passes. Compare each unchanged control to crossing_distinct of the
same duration. Also require identical public outputs/warnings within each
same-observations/different-truth pair; truth must never affect these outputs.
Repeatability, reset and observer non-interference are correctness checks, not
independent validation. No outcomes from this future execution exist yet.

For each cell retain all inputs, public outputs, warning records, evaluator-only
truth/matches/failures, unrounded canonical CLEAR v2 metrics at IoU 0.5, and:

1. Warning-frame count and fraction over all 96 frames and each interval:
   startup `[0,2)`, settled warmup `[2,36)`, episode, recovery. Do not delete
   startup FN or rescore each interval with a reset matching history.
2. First episode-warning frame and delay from 36; null if none (not zero).
   Record warning frames outside the episode separately, without changing onset.
3. For frames **[3,96)**, fraction with at least two previous public tracks
   each having an edge, as a coverage/opportunity measure. Keep zero-edge IDs
   and frames with fewer than two previous tracks; do not silently drop them.
4. All warning/non-warning frames alongside canonical FN/FP/IDSW/fragmentation
   events. For each IDSW at `s`, descriptively record whether a warning occurred
   in `[max(0,s-2),s]`. Zero switches means coverage is null, not 100%; this is
   not a registered identity-prediction or causal-success endpoint.
5. Separate results for every semantic counterexample, including warnings when
   no reference ID switch occurs. No pooled best score or statistical intervals
   from deterministic frames/repeated cells.

**Development screening gates** (engineering limits, not estimated real-world
error guarantees):

- All integrity, complete-coverage, deterministic/reset, control-equality,
  semantic-pair equality and monitor-on/off checks must pass first.
- Each of the six target cells (shared_union / coincident_two x three durations)
  needs at least **one episode warning**, first delay **<=2 frames**.
- Each of the twelve clean-control cells (four named control families x three
  durations) needs **zero warning frames over the entire sequence**, and at least
  **90%** opportunity coverage over [3,96); use the exact integer comparison
  `10 * opportunity_frames >= 9 * 93`, not rounded display percentages.
- Missing-second and semantic-counterexample outcomes are mandatory reports,
  not discarded failures or opportunities to redefine the candidate.

If any gate fails: **stop v1**, retain all completed/partial outcomes and explain
the failure. Do not tune the threshold, window, scope, selected frame or control
list to make v1 pass. A separately justified future design needs a new version
and new evidence. Passing only makes an offline diagnostic eligible for further
evaluation; it does not authorize a green identity badge, a user alert feature,
default change, real-world false-alarm claim or C++ port.

## Implementation handoff and evidence gates

- [x] Define one observable claim, candidate rule, fresh controls, semantic
      non-identifiability examples, usefulness/error limits and negative decision.
- [x] Implement the small offline observer and these exact inputs; author hand
      fixtures for IoU boundaries, class/score filters, empty/invalid/duplicate
      rows, component capacity (including a greedy-matching trap), reset,
      source-row permutations, coordinate scaling/translation and no mutation.
      Tests/doubles must not run the actual study tracker before the freeze.
- [x] Validate all 27 input/GT recipes and 16 unique detector payloads by separate
      scalar geometry; verify the two same-observation pairs, exact controls,
      truth exclusion and temporal ordering. No candidate performance yet.
- [x] Commit implementation, recipe, tests and protocol before actual execution;
      bind hashes/revision/runtime/config and baseline package to a pre-run
      method receipt. Refuse existing/symlink outputs or outputs inside either
      repo; retain partial failures, no success manifest on failure or drift.
- [ ] Execute all cells once with all passes, then audit saved records using
      scalar IoU and exhaustive small-component matching, independently of the
      observer's matching implementation. Retain every warning and non-warning.
- [ ] Write all-cell findings and explicit stop/pass decision. Known MOT17 and
      prior toy-study records may only be exploratory follow-up, not validation.
- [ ] Before real utility/transfer claims: representative permitted observations,
      independent physical/reference labels, a separate prospective evaluation
      and practitioner review of warning burden. These remain open.

**Next action:** one complete execution of the frozen development grid and
independent saved-record audit. No owner action is needed for that.
No new recording, outreach, release, public pixel distribution or C++ change.
