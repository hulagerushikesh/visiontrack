# Box-gate ablation — final bounded findings

**2026-10-23. All eight milestone groups of this experiment are complete.**
The unchanged registered candidate receives **`failure`**, not `pass`, under
the original numerical rules. This is a useful negative research result, not a
failure of VisionTrack as a project. Package defaults and C++ remain unchanged.

## The answer in plain language

We tested one proposed fix: turn off the tracker check that can reject a match
when a detection's position or box shape changes unexpectedly. Only
`use_mahalanobis_gating` changed; this was not a new algorithm.

The change eliminated evaluated ID switches on these toy paths. However, it also
worsened other required measures, including unmatched output boxes and missed
object-frames. Keeping an ID stable does not mean its box follows the object
accurately, or that its crossing gets counted in the correct time window.

**We should not adopt gate-off as the fix.** We learned that this intervention
does not meet our joint ID-stability and counting requirements. We have not
proved which internal mechanism causes every error or that any replacement
algorithm would work better in real traffic.

## Complete comparison, not selected favorable cases

Both splits completed without errors, skipped cases or selective retries:

| Evidence | Development | Held out | Total |
| --- | --- | --- | --- |
| Paired cases | 120 | 120 | 240 |
| Baseline/candidate variant runs | 240 | 240 | 480 |
| Recorded fresh/reset/independent-fresh passes | 720 | 720 | 1,440 |
| Safety-endpoint violations | 174 | 206 | 380 |
| Distinct pairs with at least one violation | 60 | 60 | 120 |
| Control/perspective-only pairs identical on all 37 endpoints | 60 | 60 | 120 |

Each pass has 300 updates. Multiple violations can occur in one pair;
380 violations are **not 380 independent experiments**. All 120 box-error pairs
violate at least one safety endpoint. Repeated noise seeds are not independent
camera sites, populations or confidence intervals.

Primary means are ID switches per reference object over each scenario's 20
error-condition cases:

| Split / scenario | Baseline | Gate off |
| --- | --- | --- |
| Development / solo | 4.00 | 0.00 |
| Development / separated opposing | 3.75 | 0.00 |
| Development / close opposing | 3.75 | 0.00 |
| Held out / solo | 4.00 | 0.00 |
| Held out / slanted opposing | 3.70 | 0.00 |
| Held out / close opposing | 3.70 | 0.00 |

All three scenarios in each split meet the fixed challenge and improvement
margins. This does **not** override the requirement that no paired case worsen
any of the five safety endpoints:

| Safety measure | Development: worse / better / equal | Held out: worse / better / equal |
| --- | --- | --- |
| ID switches | 0 / 60 / 60 | 0 / 60 / 60 |
| Missed object-frames | 54 / 4 / 62 | 50 / 8 / 62 |
| Unmatched public output rows (FP) | 60 / 0 / 60 | 60 / 0 / 60 |
| Bottom-centre missed + extra crossings | 30 / 20 / 70 | 38 / 20 / 62 |
| Bottom-centre absolute window-count error | 30 / 20 / 70 | 58 / 0 / 62 |

FP here means a tracker output unmatched by the IoU-0.5 reference evaluator,
not a hallucinated detector input or an additional identified person. Inputs
still provide one synthetic detection per reference object on every frame.
See the full [development](BOX_GATE_DEVELOPMENT.md) and
[held-out](BOX_GATE_HELDOUT_RESULTS.md) tables for scenario-specific means.

## Why the verdict is failure, not inconclusive

The final audit checks complete, valid saved evidence for **both** splits and
adequate challenge. It then applies the registered priority: a single per-case
safety regression is enough for `failure`. There are 174 + 206 such violations.
The ID-switch benefit cannot average them away.

The original split-only summaries remain `inconclusive` because each intentionally
omits the other split. Those historical files are not rewritten. They do not
say that evidence is still missing from this combined report.

A concrete held-out solo example explains the counting trade-off: the reference
crosses at frame 149.5, in `[120, 150)`. The candidate crosses around 165.5654,
in `[150, 180)`. The fixed event matcher accepts it within 30 frames, improving
event error from 1 to 0, but window-count error worsens from 1 to 2. The baseline
has no matched crossing, so its timing error is **undefined, not zero**.

## What the final audit establishes — and what it does not

The new stdlib-only
[`box_gate_combined_audit.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_combined_audit.py)
reads saved records; it imports no tracker, generator, scorer, NumPy or production
decision module. It verifies:

- Both original indices against their reviewed `8df9cff` snapshot; all **730 raw
  files**, **960 ledger entries**, retained variants, exact settings and receipts.
- The development and held-out execution revisions (`817e6f7` and `c99c4e7`),
  their historical harness files, unchanged 57-file baseline and four protocol
  artifact hashes, plus the exact freeze/consumed-opening/development lineage.
- **17,760 endpoint values**, **8,880 paired differences** and **2,664 descriptive
  endpoint groups**, retaining undefined means and their counts.
- A separately implemented decision-priority and exact rational margin check,
  tested against hand-worked boundaries and the production numerical-rule code.

Endpoint arithmetic uses the **unchanged pinned development auditor's helpers**,
independently of the scorer; it is not a second implementation of those helpers.
It rechecks the original development audit without changing its bytes or its
DEV-only guards. Diagnostic arithmetic permits `1e-12` tolerance; integer safety
comparisons and rational margins have no tolerance.

Saved input manifests, canonical CLEAR-MOT correspondence, labels and execution
receipts remain trusted primitives. This does not independently witness runtime
execution, regenerate projection/ground truth, or regenerate crossing events
from public rows. All observations remain synthetic, not real detector/camera
performance, an explanation of every internal cause or population-level evidence.

The external companion audit retains all 380 individual regressions. The compact
committed [combined evidence index](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_combined_v1_evidence.json)
pins its path, bytes and audit implementation. It was produced after execution;
it is not part of the earlier frozen execution harness. Original raw bundles,
indices, protocol locks, freeze and consumed opening remain untouched.

To check saved evidence again, use this **audit**, not the once-only executor:

```bash
python -m experiments.box_gate_combined_audit \
  --root /absolute/path/to/visiontrack \
  --development /absolute/path/to/development/bundle \
  --heldout /absolute/path/to/heldout/bundle \
  --freeze /absolute/path/to/original/freeze.json
```

By default JSON goes to standard output. Optional `--output` creates a **new**
external companion file only; it refuses overwrite and paths inside the
repository, either input bundle or freeze directory. No new tracking runs occur.
Reproduction needs the original external bundles/freeze/opening, the unchanged
indices and auditor helper, and Git history containing the recorded revisions;
the compact indices alone cannot recreate the raw evidence.

## Next action and the wider project

1. Keep the existing tracker/defaults and C++ parity boundary. Do not release or
   port the rejected candidate as an improvement.
2. The [saved-development symptom diagnosis](BOX_GATE_DIAGNOSIS.md) now
   distinguishes missing public output, box overlap and count-window timing
   across all 120 pairs. Specify/test development-only internal tracing next,
   with exact saved-output parity before replay. This is diagnosis, not a claim
   that disabling only shape gating, using ground-plane motion or adding
   appearance is already the answer.
3. Before any new comparative experiment, register its comparator, metrics,
   safety requirements and genuinely new held-out cases. Both opened sets stay
   consumed; no tuning and relabeling them as untouched validation.
4. Continue the separate permitted recording/workflow rehearsal and obtain
   representative rights-reviewed domain evidence before real-world claims.

The eight-step experiment is closed, **not the whole research/product roadmap**.
Owner walkthrough, real-data validation, discovery and any later accepted C++
handoff remain in the [two-project progress overview](PROGRESS_OVERVIEW.md).
No additional email, data request, upstream PR or release is authorized here.
