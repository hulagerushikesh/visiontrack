# Offline localization-signal audit: design v1

**Design checkpoint, 2026-11-04; not an executed accuracy study.** The
[research decision](LOCALIZATION_RESEARCH_DECISION.md) selected detector
proposals as an additional observable. The [cost/coverage probe](YOLOX_CAPTURE_COST.md)
now shows why the 4,096-row prefix cannot be assumed sufficient. Next we build
offline arithmetic and its disconfirming controls, before selecting outcome data.

Question: **does proposal spread help rank localization error beyond detection
score, class and box size?** This is a known information source, not a novelty
claim, a calibrated covariance, a cause classifier or a proposed tracker change.

## Inference-side feature and explicit abstention

For each ordinary returned winner, use only its direct greedy-suppression group.
Require the winner and **all** group members to be present, including members
of other classes. Within that complete group, retain same-class members and
require at least **three**, counting the winner. For valid finite positive-size
boxes, define bottom-center anchor `a = ((x1+x2)/2, y2)` and one fixed feature:

```text
spread = median(||a(member) - a(winner)||2) / height(winner)
```

No scores, reference labels or tracker matches select group members. Do not
replace missing/one-member groups with zero spread, fill an incomplete group,
or reinterpret different-object proposals as independent repeated measurements.
Mixed-class fraction and member count are diagnostics, not additional tuned
features in v1. Non-finite/invalid boxes cause an explicit unsupported reason.

For an offline pilot, choose a full-frame row cap from the pinned model shape
and refuse the frame's feature extraction if capture is truncated. Hash raw
output/model/frame inputs and record decoder settings. Compute one frame at a
time, retain compact features/reasons and release the capture. Preserve enough
permitted input/provenance to recompute it; do not claim a new sealed Lab format.
The existing API/default and all ordinary `Detection` objects remain unchanged.

## Target and fixed matching policy for the later data pilot

Use independently checked reference boxes and visibility/ignore status. Map
classes explicitly before any outcomes. Per frame, match returned detections
to eligible same-class references using maximum total IoU, with pairs below
**0.5** forbidden and one-to-one assignment; use deterministic original-index
tie handling. Fix ignore-region handling in the dataset manifest before running.
This is independent of tracker association and does not reuse accepted matches.

Primary error is Euclidean bottom-anchor error divided by reference box height;
report pixel error and `1 - IoU` as secondary descriptions. The predictor may
use **predicted** dimensions only. Reference dimensions normalize the target;
they are never inference features. Retain unmatched predictions, missed
references, excluded annotations and unsupported groups as separate totals.
This conditional localization audit cannot establish object recovery, count
accuracy, physical ground-plane error or session identity continuity.

## Same-population comparisons

All fitted quantities use development scenes only. Freeze the scene-separated
manifest, model bytes, preprocessing, class mapping and implementation before
test outcomes. A short single-scene run is tooling/exploration, never a held-out
domain result. Do not repurpose the already inspected MOT17 material as untouched.

- **B0:** constant development mean of the target (no ranking information).
- **B1:** ridge regression using class indicators and log predicted width/height.
- **B2:** B1 plus ordinary detection score.
- **B3:** B2 plus the single spread feature above.

Fit `log1p(error)` by ridge regression with fixed penalty **1.0**, unpenalized
intercept and training-only standardized numeric columns. Constant columns
become zero; unseen classes abstain. Convert predictions with non-negative
`expm1`; no hyperparameter/candidate search after seeing test errors. Compare
B2/B3 on the exact same supported population, and disclose how much of **all**
returned detections it covers. Report B0/B1/B2 on their broader supported
population separately; do not present cohort selection as a quality gain.

Primary measure: area under mean normalized error versus retained coverage,
ranking lowest predicted error first, over every attainable retained count.
Also show 10/25/50/75/100% coverage and per-scene paired B3-minus-B2 differences.
Break prediction ties by a fixed input key, never by reference error. Stratify
by class, predicted-height development quartile, visibility and group size.
Frames from one camera session are correlated: intervals resample independent
scene/session units, not individual boxes (10,000 paired bootstrap resamples,
seed 20261104). Fewer than eight independent test units or fewer than 50
supported matches in a declared stratum yields a descriptive pilot/insufficient
evidence for that conclusion, not an acceptance. These operational floors are
not a power calculation or proof of representativeness.

## Required controls and stop rules

Authored checks must include: a tightly grouped but coherently biased box set;
one/missing/truncated group; mixed classes; adjacent objects in one suppression
group; invalid geometry; and a large genuine displacement with low spread.
Their role is arithmetic/refusal and counterexample testing, not simulated
proof that the feature generalizes. The data pilot must disclose blur/occlusion,
small boxes, real extent change and perspective/label ambiguity when available.

If capture changes detections, stop on engineering failure. If coverage is low,
do not compensate by dropping hard scenes or increasing confidence thresholds.
If the paired scene-level interval for B3-minus-B2 area does not lie below zero,
or reported supported strata show unresolved regressions, the outcome is no-go
or inconclusive for association work. Reaching a gate is not a novelty claim;
practical effect size and an application-specific no-harm margin need a later,
separately frozen association/count experiment. Calibration is a separate task
if we ever define an actual predictive distribution.

No dataset, split manifest, outcome table or accepted method exists for this
audit yet. The next deliverable is the small offline feature/control implementation.
Then an admitted-input manifest and independent label check precede outcome
execution. RoundaboutHD remains conditional on Bath; C++ stays in maintenance.
