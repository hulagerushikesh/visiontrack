# VisionTrack and VisionTrack C++ — progress overview

Snapshot: **2026-10-23**. This is a summary of the canonical
[VisionTrack checklist](NEXT_STEPS.md), [status](STATUS.md) and
[C++ checklist](https://github.com/hulagerushikesh/visiontrack-cpp/blob/main/NEXT_STEPS.md).
Completed implementation is not the same as validated research or product demand.
This document does not claim the latest local work is already pushed or deployed.

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

## Current focus: one-switch box-gate experiment

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

The present box-gate experiment uses a setting already in the Python tracker;
it introduces no new algorithm requiring an immediate C++ port. Re-entry gallery,
scoring, abstention, expiry/eviction and decision-stream parity remain conditional
future work. Approximate indexing must remain explicitly separate from exact mode;
no GPU path or weakened parity is justified by the current plan.

## Immediate next action

The experiment is closed with a negative result, not an accepted tracker change.
Next, inspect saved **development** failures to separate match rejection, box
localization and crossing-window timing before choosing a narrower intervention.
Any new comparative study needs a new registration and genuinely fresh held-out
cases; neither opened set may be relabeled as untouched validation. This diagnosis
needs no new footage or owner assistance. Real recording, usability walkthrough
and discovery remain separate pending work. C++ stays in maintenance until a
useful behavior earns an explicitly accepted parity handoff.
