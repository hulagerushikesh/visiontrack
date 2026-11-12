# Offline localization-signal audit: feature v1

**Offline feature and authored controls, 2026-11-04; not an accuracy study.** The
[research decision](LOCALIZATION_RESEARCH_DECISION.md) selected detector
proposals as an additional observable. The [cost/coverage probe](YOLOX_CAPTURE_COST.md)
shows why the 4,096-row prefix cannot be assumed sufficient. The
[`audit_capture` implementation](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/localization_signal.py) now
calculates the fixed spread and returns explicit refusal reasons. The
[authored controls](https://github.com/hulagerushikesh/visiontrack/blob/main/tests/test_localization_signal.py) check arithmetic,
capture completeness, invalid boxes and counterexamples using generated inputs.
This does not select outcome data or establish a real-world signal.
The extractor now indexes complete suppression groups once per frame rather
than scanning all proposals for every returned box. Exact output agrees with
the previous implementation across four generated capture shapes and four
retention limits. On the generated 8,400-proposal/256-detection case, local
median audit time fell from 34.3 ms to 0.9 ms over 20 runs each; this excludes
model inference and is not a deployment-latency claim. The separate
[Singapore LTA preflight](LTA_LOCALIZATION_PREFLIGHT.md) checks all 63 retained
real images and shows that detector coverage, not spread computation, is the
immediate obstacle for that fixed model/source pairing.
The subsequent [development-only detector comparison](LTA_LOCALIZATION_PREFLIGHT.md#predeclared-development-only-overlap-screen)
shows substantially more supplied-box overlap with the existing X/640 model,
but weights and input resolution change together, and the eight-camera source
cannot meet the eight-test-scene floor with an internal separate development
set. These already-inspected validation frames are not untouched test data. This
does not advance the frozen outcome comparison or change the C++ handoff.

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
The compact returned row contains the ordinary detection output index, winner
proposal index, status, spread when supported, group size, same-class count and
mixed-class fraction. It contains no boxes, images or raw proposal records.

The code refuses an entire truncated frame, even if one visible group looks
complete. For complete frames it refuses missing winners, inconsistent direct
groups, singleton groups, groups with fewer than three same-class members, and
invalid geometry. The controlled three-row example has anchor distances
`0, 2, 4` pixels and winner height `10` pixels, giving spread `0.2`. Translating
all three boxes 100 pixels preserves `0.2` even when the reference or previous
position remains at the original location. Likewise, adjacent objects can
appear within one suppression group. These are explicit limits on interpretation,
not a demonstrated localization predictor.

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
**0.5** forbidden and one-to-one assignment. Preserve original input order and
pin the solver version for reproducibility. If forbidding a selected pair still
permits the same optimum total IoU (within `1e-12`), count that pair and frame
as assignment-ambiguous; the selected target remains in the analysis, so report
these counts alongside every outcome. Fix ignore-region handling in the dataset
manifest before running.
As a sensitivity check, refit B2 and B3 using only unambiguous supported
development matches and compare them on the same unambiguous supported test
matches. Report excluded ambiguous rows, any classes absent after the exclusion,
the remaining scene count and the paired area/scene interval. If either split
has no such rows, report the sensitivity as unavailable. This check probes
dependence on the fixed reference assignment; it does not make the remaining
labels independent or resolve ambiguous object identity.

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

For the fixed subgroup display, predicted-height quartile boundaries come only
from supported development matches (25th, 50th and 75th percentiles; ties go to
the lower bin). Complete suppression-group sizes are binned as 3, 4–7 and 8+;
missing sizes remain `undeclared`. A source adapter must supply a declared
visibility mapping. The default `unknown` is displayed honestly and cannot
stand in for a reviewed visibility stratum. Each populated subgroup reports its
own B2/B3 pooled area, equal-scene mean difference and interval status. No
subgroup interval is emitted below the eight-scene/50-match floors.

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

The dataset-agnostic [offline comparison runner](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/localization_outcome.py)
now implements eligible same-class IoU-0.5 box matching, bottom-anchor targets,
unmatched/missed/excluded and equal-optimum assignment-ambiguity counts, B0–B3
ridge fits with an unpenalized intercept,
training-only numeric standardization, matched-population B2/B3 comparison,
risk-versus-coverage area, fixed-key ranking ties, paired scene-level bootstrap,
an unambiguous-match sensitivity refit, and the declared subgroup display.
The report now retains every declared test scene in a separate coverage table,
including cameras with zero detections, no matches or no supported paired
matches, and lists omitted scenes explicitly. Paired scene intervals still
describe only scenes with paired matches and must be read with that coverage
table; an interval cannot validate a camera that contributed no pair.
It rejects a scene shared by development and test. Generated-input tests check
the arithmetic, leakage, refusal paths and scene-unit resampling. The interval
is the bootstrap of the **mean of per-scene paired areas**; the pooled paired
areas are also shown and must not be confused with that equal-scene estimate.
The runner cannot certify label independence, scene provenance, media rights,
class/ignore mapping, visibility semantics or image quality. A source-specific
adapter and independently checked labels are still required before an outcome
study. Missing group-size and visibility metadata remain visible as undeclared
or unknown; they are not silently filled.

For an admitted source, the adapter must calculate `image_sha256` from each
exact input image and call `compare(..., require_image_hashes=True)`. The runner
then refuses missing/malformed hashes and identical image bytes appearing in
both development and test under different scene names. The report states
whether this supplied-hash split check ran. It does not independently reopen
images, authenticate supplied hashes, detect visually identical re-encodings,
or establish that differently named scenes are different cameras; source
provenance still needs separate review.

No admitted scene-separated dataset, split manifest, real outcome table or
accepted method exists for this audit yet. A [one-image UVH-26 preflight](UVH26_LOCALIZATION_PREFLIGHT.md)
checks real-image capture feasibility and exposes missing camera IDs and an
edge-box area-field inconsistency; it is not an outcome run. The next deliverable
is an admitted-input manifest and independent label check before any outcome
execution. RoundaboutHD remains conditional on Bath; C++ stays in maintenance.

The [UVH-26 MV/ST consensus audit](UVH26_CONSENSUS_AUDIT.md) additionally found
that the ST validation file is a strict subset by image filename and the two
consensus labels disagree on some shared boxes/classes. Since both derive from
the same model-assisted crowdsourced annotations, agreement cannot substitute
for independent reference inspection. This keeps the outcome gate open.
