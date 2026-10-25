# VisionTrack and VisionTrack C++ — progress overview

Snapshot: **2026-10-25**. This is a summary of the canonical
[VisionTrack checklist](NEXT_STEPS.md), [status](STATUS.md) and
[C++ checklist](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/NEXT_STEPS.md).
Completed implementation is not the same as validated research or product demand.
This document does not claim the latest local work is already pushed or deployed.

Latest advance: the fixed MOT17 **36–57** source-image window is available for
local non-commercial research, with exact annotation correspondence, all 22
image receipts, preliminary AI-assisted inspection and a private staged review.
See [the findings and reviewer handoff](MOT17_VISUAL_REVIEW.md). Independent
human/reference review remains open; no tracker intervention or C++ port is
accepted, and no dataset images are published.

The [saved earlier context](MOT17_PRIOR_CONTEXT.md) is also checked without new
pixels/replay: public 19 overlaps reference 85 alone above IoU 0.5 throughout
frames 3–35. That strengthens the correspondence-change hypothesis, not a
physical-identity verdict, accepted fix or completed independent review.

## Direction: unchanged

VisionTrack is the readable NumPy reference and local-first **tracking Reliability
Lab**: reproduce failures, compare detector/tracker settings, inspect evidence
and make explicit human decisions. It is also our research and learning platform.
VisionTrack C++ is the faster implementation of accepted, frozen reference
behavior, not a second independent research project.

We are not building permanent worldwide person identification. Re-entry research
concerns bounded, anonymous, same-camera/session continuity, with expiry,
abstention and measured error limits. A useful product vertical is not yet chosen.

## What is already finished

| Area | Completed scope | Important limit |
| --- | --- | --- |
| Tracking foundations | Kalman filter, assignment, ByteTrack lifecycle, evaluation, controlled RQ1–RQ4 research | Not a claim of universal best accuracy |
| Usable Python package | Published `visiontrack-mot 0.3.0`, video/webcam workflows and release gates | Detector quality and domain still matter |
| Website and learning | React design, learning paths, research/results access and beginner explanations | No new UI redesign is needed for the current experiment |
| Reliability Lab alpha | Local reports, failures, optional verified images/playback, explicit decision drafting/import and shared contracts | Owner walkthrough is partial; practitioner usability remains unvalidated |
| Original traffic mechanism probe | All 120 development and 120 held-out cases retained; scoped findings and independent saved-record checks | Toy geometry/imposed box errors, not a real traffic benchmark |
| C++ runtime | Published `0.1.1`, NumPy `0.3.0` oracle compatibility, exact parity, reset, packaging/benchmark evidence | New research is not automatically authorized for porting |
| Re-entry groundwork | Protocol, synthetic stress results, dataset audits, privacy/capture/review tooling | Real-data accuracy is not established; the 1,000-candidate synthetic margin rule failed its risk gate |

The traffic characterization found severe failures under the imposed box errors;
perspective alone did not change the primary count/ID outcomes. These observations
motivated the next question. They did **not** prove its cause or a solution.

## Completed research: one-switch box-gate experiment

Question: can disabling only the tracker’s shape-sensitive rejection gate reduce
broken IDs **without worsening** the registered tracking/counting measures?
It could help, do nothing or harm nearby-object associations.

There are **eight milestone groups** in this experiment. All eight are complete.
That is a count of milestone groups, **not a percentage of total
effort, a probability of success or a whole-project completion percentage**.

- [x] 1. Register the question, single changed setting, fresh scenario/seed
  splits, numerical improvement margins and negative-result rules.
- [x] 2. Build/check paired immutable inputs: all 120 development input
  combinations, shared noise and detector-only fingerprints.
- [x] 3. Build/check the reference scorer: all 37 endpoints, canonical match
  history, missing-value handling and hand-worked mistakes.
- [x] 4. Implement/test the [paired replay adapter](BOX_GATE_REPLAY.md): isolated
  variants, detector-only handoff and fresh/reset/fresh checks, using test doubles.
  Actual development outcomes are now retained in milestone 6 below.
- [x] 5. Build/test [complete paired exports and decision rules](BOX_GATE_REPORT.md); require exact
  coverage, retain per-case regressions, reject invalid/incomplete evidence,
  preserve nulls and distinguish inconclusive/failure/no-effect/pass.
  The development harness is committed before the development grid. All rule
  and exporter tests use hand-worked tables/doubles, not new tracker outcomes.
- [x] 6. Execute and independently audit all **120 development pairs**:
  240 variant runs, each with three passes. Keep every result, configuration,
  input/output digest and failed attempt; do not tune the registered candidate.
  All pairs completed from `817e6f7`, with no errors or selective retries.
  [Development findings](BOX_GATE_DEVELOPMENT.md): gate-off removed ID switches
  but violated safety requirements in all 60 box-error pairs (174 endpoint
  violations). The candidate is not accepted. Its development-only numerical
  summary is inconclusive by design; it does not include the held-out rows.
- [x] 7. Freeze the complete reviewed harness, environment and new held-out
  input hashes; execute the **120 new held-out pairs once** through a separate
  exclusive gate. Stop on error, retain partial evidence, no selective retries.
  [Safeguard substeps 7a and 7b](BOX_GATE_HOLDOUT.md) are implemented/tested:
  exact revision/runtime/evidence checks, all 120 input manifests, separate
  scoring/replay/export and an exclusive no-retry opening gate. The real freeze
  and [once-only run](BOX_GATE_HELDOUT_RESULTS.md) completed from `c99c4e7`:
  120 pairs / 240 variants / 720 passes, no errors or selective retries.
  All 365 files and 480 ledger entries passed a separate artifact inventory.
  Saved endpoints show 206 safety violations in all 60 box-error pairs; no
  candidate tuning or acceptance. Endpoint arithmetic is now checked in step 8.
- [x] 8. Audit and explain the [combined results](BOX_GATE_FINDINGS.md), retaining
  all negative outcomes. All 730 raw files, 17,760 endpoint values, 8,880 contrasts
  and exact decision margins were checked from saved records without tracker
  replay. **Final registered classification: failure** — 380 safety violations
  across 120 affected pairs, despite the ID-switch benefit. This uses unchanged
  development arithmetic helpers independently of the scorer, not a second
  implementation of those helpers. Saved correspondence/inputs remain trusted.
  Defaults and C++ are unchanged; this is not real-world validation.

The original traffic-v1 held-out set is already opened. It will not be relabeled
as untouched or reused as the new experiment's held-out evidence.

## What remains beyond this experiment

The post-study [saved-development diagnosis](BOX_GATE_DIAGNOSIS.md) is complete
without tracker replay. The next [internal tracing preparation](BOX_GATE_TRACE.md)
now has a bounded opt-in observer and authored parity/state/cleanup tests.
The [development-only provenance/replay wrapper](BOX_GATE_TRACE_REPLAY.md) is now
implemented/tested, including pre-update payload receipts and failure preservation.
The [new exploratory trace and read-only audit](BOX_GATE_TRACE_FINDINGS.md) now
cover all 240 variants with exact saved-output parity and no errors/retries.
Recorded events explain concrete gate/confirmation gaps and same-ID anchor
recrossings; they do not accept a fix or validate transfer. A new
[counting-only study](CROSSING_BAND_PROTOCOL.md) is now registered to separate
association from count stability. No held-out reopening, default change or
C++ adoption.

### Current focus: counting-only confirmation band

- [x] Register one fixed counter rule on identical unchanged tracker outputs.
- [x] Define fresh development/held-out paths and seeds, with through passages,
  near-line dwell, genuine shallow/full returns and band-start/end crossings.
- [x] Lock definitions; test integrity, scope and ideal geometry without new
  noisy observations, tracker runs or comparative research outcomes.
- [x] Implement/test the [isolated state machine](CROSSING_BAND_COUNTER.md) and
  emission-time records: 64 authored tests, including genuine misses and delay.
- [x] Review structural safety costs: **stop at engineering feasibility** because
  authored ideal paths expose genuine misses and excessive reporting delay.
  This is not an executed development/held-out verdict.
- Not undertaken after that stop: full input/replay/report harness, development
  grid, held-out execution and result audit. These are not completed study steps
  or the active backlog; definitions, locks and negative examples are retained.

The candidate's 0.25-unit toy band may reject jitter but also miss real short
passages or delay counting. Per-case misses/extras and both event/emission-time
window errors must not worsen; every emitted event must confirm within 15
frames. No acceptance or real-world transfer is established by this design.
See the [recorded feasibility decision](CROSSING_BAND_COUNTER.md#feasibility-decision-2026-10-23).

### Research and real data

- [ ] Complete a small permitted recording rehearsal when the owner is ready.
  Obtain adult consent before recording people, keep footage private/outside Git,
  and establish independent review. A two-person pilot is a workflow rehearsal,
  not enough evidence to certify accuracy.
- [ ] Secure representative rights-reviewed evidence and freeze its labels,
  detector, session/identity splits, controls and evaluation before claims.
- [ ] For same-session MEVID use, establish original recording/time provenance
  and resolve the empty annotation row; otherwise stop this route. Crop-local
  frame numbers are not proof of chronological exits/returns.
- [ ] Evaluate bounded anonymous re-entry on admissible real data, retaining
  false restorations, missed returns, abstentions, expiry and memory costs.
- [ ] Test whether any useful synthetic traffic finding transfers to the target
  camera/detector domain. Do not call synthetic box perturbations real occlusion.

### Product and usability

- [ ] Finish the owner Lab walkthrough and fix observed blockers.
- [ ] Continue practitioner discovery toward 5–10 interviews and at least
  three prospective design partners; Jan's helpful written reply is domain input,
  not a validated partnership or market demand.
- [ ] Select one evidence-backed vertical and write its user/input/output/success
  measure before building a small application prototype.
- [ ] Separate tracker value from detector, data rights and deployment needs;
  validate the workflow before expanding frontend or cloud infrastructure.

No new outreach, access permission or data-sharing action is implied by this plan.
Expensive detector-comparison extensions remain separate compute-dependent work,
not a prerequisite for completing the current small experiment.

## C++: what is finished and when we synchronize

The current released synchronization boundary already exists: C++ `0.1.1` was
verified against NumPy `0.3.0`. Release evidence includes 7,545 exact real-sequence
observations and a 100,765-observation exact-mode benchmark. Prospective Eigen
3.4.0/5.0.1 source-build checks passed across Linux, macOS ARM64 and Windows;
that does not change the release's Eigen 3.4.0 pin.

C++ is therefore in **maintenance**, not an unfinished duplicate of this study.
Ongoing work is deliberate toolchain testing and protection of existing parity.

A new synchronization happens only after:

1. Python behavior demonstrates a useful, accepted result within the required
   evidence scope. A synthetic ablation pass alone is not a real-data approval.
2. Its public settings/API and exact decision/output fixtures are frozen, with
   explicit acceptance of the handoff.
3. C++ implements only that stable subset, verifies exact parity/reset behavior
   across the supported matrix, and measures latency/memory before release.

The completed box-gate experiment uses a setting already in the Python tracker;
the new counting-only registration does not alter tracking or authorize a C++
port. Re-entry gallery, scoring, abstention, expiry/eviction and decision-stream
parity remain conditional
future work. Approximate indexing must remain explicitly separate from exact mode;
no GPU path or weakened parity is justified by the current plan.

## Immediate next action

The counter's engineering feasibility review is complete: **stop the fixed band
candidate**, retain its examples/locks and do not invest in its full grid now.
This is not a development/held-out verdict. The box-gate study and diagnosis are
finished; neither opened set may become untouched validation again.

Follow the [bounded showcase plan](SHOWCASE_MILESTONE.md): the short
[existing-report demonstration](SHOWCASE_DEMO.md) is now prepared and verified
locally. Its two configurations tie; the research trade-off is explicitly from
a separate completed synthetic study. The owner has clarified that substantive
evidence, not a demonstration, takes priority. The
[existing MOT17-04-FRCNN intake](REAL_DATA_CASE_INTAKE.md) now passes source/cache
correspondence for annotation-only diagnosis. Its [unchanged baseline](REAL_DATA_BASELINE.md)
now reproduces all four run files exactly across two fresh runs: FN 21,825,
FP 49, IDSW 43, IDF1 61.32%, HOTA 52.55%. The first switch (reference 85,
track 19 → 31, source frame 54) has a bounded metadata inspection, not a visual
causal explanation. The [coverage diagnosis](REAL_DATA_COVERAGE.md) now reconciles
all 21,825 misses: 19,387 lack any raw detection IoU ≥0.5 neighbour; 2,019 have
an eligible retained neighbour but no scored match. The remaining 419 concern
low scores/ignore handling; unique assignment capacity prevents treating neighbour
counts as guaranteed recovery. The [actual unchanged trace](REAL_DATA_TRACE.md)
now passes all 1,050 replay frames: 19 remains updated; 31 is born at 52 and
confirmed at 54. Shared geometry with reference 89 prevents calling this a
proven forgotten-person or tracker-drift error. The intervention decision and
bounded independent-review brief are complete; no candidate is adopted.
Full visual review and a justified comparison
remain open; the owner walkthrough is not a
technical prerequisite. Follow the [daily/weekly checkpoints](WEEKLY_DELIVERY_PLAN.md)
toward one permitted
real-clip diagnostic case study. Its proposed first audience is fixed-camera CV engineers
and applied researchers, not a validated market. Technical case-study effort is
estimated at 4–5 focused working days **after usable permitted data/labels are
ready**, with external permission/review delays separate. The alpha can already
be shown with synthetic evidence labelled honestly; real-world improvement is
not yet proved. Real recording, usability and discovery remain pending. C++ stays
in maintenance until useful behavior earns an explicitly accepted parity handoff.

**New measurement gate (2026-10-24):** the [independent metric check](REAL_DATA_METRIC_CHECK.md)
does not pass. Saved-output TP/FN/FP and IDF1 agree; TrackEval reports IDSW 44
versus our historical 43, and HOTA 0.52372649 versus 0.52554966. Minimal examples
show algorithm/definition differences, not just rounding or solver ties.
Next align the evaluators and re-score unchanged outputs with explicit history/
report compatibility before a new tracker comparison. No owner footage is needed
for that technical correction. Historical results are retained, not silently revised.

**Resolved at metric level:** [evaluator v2](EVALUATOR_V2.md) now passes all 45
reference checks on unchanged saved outputs. Corrected IDSW 44, Frag 108, HOTA
52.37%, IDF1 61.32%; not a tracker improvement. Old Lab artifacts keep v1 semantics
and hashes; mixed evaluators are rejected. All 1,099 frozen-study tests run at
their original revision. The next preprocessing/coverage gates are now also
complete, as recorded below; independent pixel/reference review still precedes
an intervention.

**Current measurement milestone:** [MOT17 preprocessing](MOT17_PREPROCESSING.md)
matches all 1,050 saved frames; general policy discrepancies are corrected under
an explicit v2 policy with legacy reproduction. Existing Lab policy stays
explicitly historical rather than changing under old artifact IDs.
[V2 coverage and the extended actual trace](MOT17_COVERAGE_V2.md) now pass:
19,393 misses without raw overlap, 149 low-score-only, 270 ignore-removed, 2,013
with an eligible retained neighbour. Of the changed miss records, 29 replace
object/frame pairs and 25 change history only. The same first event's last
prior match is frame 37, so the actual trace now covers 36–57: 738 events/66
stages, all 1,050 outputs/failures reproduced exactly, track 19 updated/public
throughout. Next: independent lawful visual/reference review, then a justified
comparison or reasoned stop. No new tracker behavior or C++ port is justified yet.

**Lab policy migration complete:** [new schema-3 metric artifacts](LAB_EVALUATION_POLICY.md)
explicitly name preprocessing v2 as well as evaluator v2. Failure/report lineage
carries that policy, mixed definitions are rejected, and historical v1/v2 report
JSON, HTML and event-stream golden hashes remain exact. The browser names the
rules and uses evaluator-correct metric explanations. This is a measurement
compatibility milestone, not improved tracking or independent visual review.
