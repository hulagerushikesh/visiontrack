# RQ5 first experiment — selective anonymous re-entry

Status: **protocol and scoring contract, 2026-10-14**. No real-data result has
been run or claimed. This document freezes the first question before choosing
thresholds from any evaluation set.

## Decision under study

At the moment a new tracklet starts, the system receives a bounded set of
recently retired anonymous identity candidates in the same authorized session.
It must either restore one candidate or abstain and create a new anonymous
identity. The existing `track_id` still names only the new continuous tracklet.
This experiment does not infer a person's name, link across unrelated sites, or
maintain identity beyond the declared time and memory limits.

The unit of evaluation is **one re-entry opportunity**, recorded after the
ordinary tracker has already produced the new tracklet. Truth is either one
prior anonymous identity or `novel`. A true return can be absent from memory
because of expiry or eviction; that is recorded separately. An attempted
restore must name a candidate that was actually available at that moment.

## Hypothesis and falsification

**H1:** With a fixed appearance representation, a selective rule using a
minimum similarity and a best-versus-runner-up margin will reduce false
restorations compared with always choosing the nearest candidate, while
retaining useful recall on eligible returns. We will report the whole
coverage-risk curve, rather than select one flattering threshold afterward.

The useful negative result is also defined now: if a rule cannot keep the
one-sided 95% upper bound on false-restoration risk below the chosen budget
while restoring more eligible returns than the abstain-all baseline, it has
not earned a product or C++ port. A zero-error sample with too few attempts
does not pass this gate. An absent or evicted true identity is never counted as
an eligible success opportunity.

This is a **research operating point**, not a deployment safety guarantee:

| Point | Maximum false restorations among attempted restores | Purpose |
|---|---:|---|
| Strict | 0.1% | Expose the sample size required for a very low-risk claim |
| Primary | 1% | Main comparison of useful recall under a bounded risk |
| Exploratory | 5% | Show the coverage/risk tradeoff and failure modes |

If the use case later demands a different cost ratio, that becomes a new,
explicitly registered study. We will not re-label a chosen threshold as
pre-registered after seeing test outcomes.

## Variables, controls, and baselines

The first study is **same camera, same session**, with exact candidate search
and an embedding adapter outside the tracker core. Hold fixed the detector,
crop extraction, embedding model, frame stream, and tracklet boundaries within
each paired comparison. Do not compare different detector resolutions as if
only the identity rule changed.

1. **Abstain all:** creates a new identity every time; zero false restorations,
   zero restoration recall. This is the safety and utility floor.
2. **Nearest appearance:** always restores the highest cosine-similarity
   candidate when a gallery is nonempty. This is the forced-choice baseline.
3. **Threshold only:** restores the nearest candidate when its similarity
   reaches the calibrated threshold.
4. **Threshold plus margin:** additionally requires a sufficient gap from the
   second candidate. This is H1's intervention.

Each rule sees the same candidate list and must emit either one candidate ID or
an abstention. The default tracker output remains unchanged. Time/zone/context
gates, quality gating, multiple prototypes, approximate indexing, and learned
calibration belong to later ablations; they must not be silently mixed into H1.

## Data and split policy

- Begin with a deterministic, dataset-free synthetic stress probe to test the
  evaluator and reveal obvious failure regimes. Synthetic performance cannot
  establish real-world accuracy.
- A real-data claim requires a rights-reviewed, consented or appropriately
  licensed source with stable identity annotations, a documented detector and
  crop path, and enough known returns **and** genuinely novel arrivals.
- Split by identity and recording/camera session before calibrating thresholds.
  All tracklets of one identity stay in one partition. Report camera or scene
  overlap explicitly; use a fully held-out camera for a transfer result.
- Calibrate threshold and margin on development data only. Freeze both numbers,
  the gallery policy, exclusions, and the event list before evaluating test.
  No test-set threshold sweep may be used to select the reported operating
  point. The full test-set curve may still be shown descriptively.
- Report sample sizes and uncertainty by identity and recording group. Use a
  grouped bootstrap for real video because nearby opportunities are
  correlated. The Wilson bound in the scoring helper applies only to
  independent synthetic events or as a clearly labeled descriptive check.
  The evaluator now has `grouped_reentry_bootstrap`: participants sharing a
  recording, or recordings sharing a participant, are resampled as one
  dependency-connected group. Its percentile intervals are descriptive, **not**
  a certified bound for the 1% operating point. It withholds intervals with
  fewer than two independent groups, and withholds a risk interval after zero
  observed false restorations. A small pilot cannot pass the product risk gate.

## Required evaluation matrix

Report separately for known eligible returns, known returns made unavailable
by expiry/eviction, and genuinely novel arrivals. Stratify by absence duration,
gallery size (10, 100, 1,000, 10,000), crop quality, similar appearance,
camera motion, and viewpoint/lighting change **when the dataset supports the
stratum**. Record unsupported cells as missing, never as zero errors.

The primary measurements are:

- **Selective risk:** false restorations / all attempted restorations.
- **Restoration coverage:** attempted restorations / all opportunities.
- **Eligible return recall:** correct restorations / known returns whose true
  identity remained in the candidate gallery.
- **Novel false-match rate:** novel arrivals incorrectly linked / all novel
  arrivals.
- **Memory availability:** expired or evicted true returns / all true returns.

Also publish raw counts, time to restore, bytes per retained identity,
candidate-search latency (median and p95), and the error table for each rule.
Operational count or dwell error is a secondary metric only when the selected
use case has a legitimate definition for it. HOTA/IDF1 alone cannot substitute
for false-restoration counts.

The first scoring implementation is
[`src/visiontrack/eval/selective_identity.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/src/visiontrack/eval/selective_identity.py).
It accepts explicit candidate lists and decisions, rejects impossible restores,
keeps abstention distinct from expiry, and provides grouped descriptive
uncertainty for a future real-video study. No identity memory or inference code
is enabled by adding this evaluator.

## Stop, narrow, and handoff gates

- Stop a real-data experiment when rights or truth provenance cannot be
  established, or when train/test identity leakage is found. Keep the failed
  audit but make no performance claim.
- Narrow to same-camera/session if cross-camera shift prevents calibrated
  thresholds from transferring. Do not hide the transfer failure in a pooled
  score.
- Reject a rule if it misses the registered risk budget or if gains disappear
  under a held-out scene, plausible gallery size, or poor-crop stratum.
- Consider a product prototype only after practitioner evidence identifies a
  valuable bounded decision and the study supports its error budget.
- Consider a C++ port only after the Python rule, expiry, eviction, reset,
  and decision stream are frozen as a versioned parity fixture. C++ remains
  on the existing ByteTrack contract until then.

The deterministic synthetic event generator, four registered decision
policies, and first held-out results are documented in
[`IDENTITY_CONTINUITY_SYNTHETIC.md`](IDENTITY_CONTINUITY_SYNTHETIC.md).
The next gate is a rights-reviewed real-data plan.
