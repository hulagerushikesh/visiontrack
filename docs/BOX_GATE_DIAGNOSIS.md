# Development diagnosis: stable IDs are not enough

**2026-10-23. Post-study exploration, not a new validation experiment.**
The [completed experiment](BOX_GATE_FINDINGS.md) remains a registered **failure**.
This follow-up reads only its original **120 development pairs / 240 saved
variant outputs**. It runs no tracker, generator or scorer, opens no held-out
files, and changes neither defaults nor C++.

## What we learned in plain language

There are different ways for a tracker to be wrong:

1. It may show no box when an object should be present.
2. It may keep showing the same ID, but put its box in the wrong place or give
   it the wrong shape.
3. Its displayed box may cross a counting line early, late, repeatedly or not
   at all. A stable ID does not make the resulting count correct.

The rejected gate-off change trades some of the first symptom for the second.
We can demonstrate that trade-off from retained outputs. We **cannot** identify
every internal association rejection from those outputs: costs, gate distances,
pre-update predictions and covariances were not saved.

## Reproducible symptom categories

The new stdlib-only `experiments/box_gate_diagnosis.py` first verifies the original
development index against its reviewed Git snapshot, all 365 bundle files and
their coverage/hashes. It re-runs the **unchanged development arithmetic auditor**
and compares its result with the hash-pinned original audit. It rechecks its
read set after diagnosis and never rewrites the original records.

For each reference object-frame already labeled a miss by the saved evaluator:

| Category | What the public output establishes | What it does not establish |
| --- | --- | --- |
| No public output | The entire frame has no public tracker row | Whether confirmation, association rejection, deletion or another internal step caused it |
| All public boxes below IoU 0.5 | No displayed box overlaps this reference box enough | That the closest box belongs to this object, or that the detector invented an object |
| Eligible box unmatched | At least one public box reaches IoU 0.5 but the saved correspondence leaves this reference unmatched | A new identity match; the box may already be assigned to another reference |

IoU is the shared area divided by the union of two boxes. The threshold is the
original evaluator's **0.5**, not the tracker's association IoU threshold of 0.3.
No threshold is tuned and no new matching is performed. Exact-threshold overlap
is eligible; undefined overlap when there is no output stays `null`, not zero.

Counts are partitioned into the original half-open frame windows `[135,165)`
(bottom pulse), `[210,240)` (top pulse) and everything else. These are fixed time
ranges even in unperturbed control conditions. The report retains all conditions,
per-object miss intervals, evaluated ID-switch frames, crossing records and
common-frame localization means. It uses **one retained output** per variant;
fresh/reset/independent-fresh checks are not counted three times.

## Development findings

Across **all 60 box-error-only and combined pairs**, each variant has 30,000
reference object-frames. The saved miss categories total:

| Symptom | Baseline | Gate off |
| --- | --- | --- |
| Misses on frames with no public output | 600 | 200 |
| Misses with all public boxes below IoU 0.5 | 112 | 757 |
| Eligible-but-unmatched misses | 0 | 0 |
| Total misses | 712 | 957 |

The candidate's 200 no-output misses are startup object-frames. These categories
describe public geometry, not internal rejection reasons. In multi-object scenes,
a displayed box below overlap threshold may belong to a different object.

For **box-error-only** cases, these are totals over ten repeated noise seeds
per scenario, combining both pulse windows. They are descriptive object-frame
counts, not independent trials or estimates for real cameras:

| Scenario | Baseline: misses with no output / boxes below IoU | Gate off: misses with no output / boxes below IoU |
| --- | --- | --- |
| Solo | 40 / 0 | 0 / 78 |
| Separated opposing | 80 / 18 | 0 / 150 |
| Close opposing | 80 / 18 | 0 / 150 |

There are no eligible-but-unmatched misses in these particular pulse-window
groups. Startup and post-pulse misses remain in the complete report; this table
does not replace the full safety totals. For example, all ten solo runs retain
20 startup misses at frames 0–1 under both variants, outside the pulse windows.

### A concrete example: solo, seed 2001, box-error-only

This is the first registered seed, not a newly selected validation case:

- **Baseline:** six missed object-frames: 0–1, 135–136 and 210–211. No public
  box exists on those frames. Evaluated ID switches occur at 137, 165, 212 and
  240; the reference is matched to IDs 1, 2 and 3 over the run.
- **Gate off:** ID 1 remains the only evaluated matched ID, with no ID switches.
  There are nine misses: 0–1, 137–139 and 212–215. Apart from startup, boxes
  exist but fall below IoU 0.5. At frame 137 the ID-1 box has IoU
  **0.4892198878744103**; frames 138 and 139 reach about 0.4661 and 0.4799.
- **Counting:** the reference crosses at frame **149.5**. The candidate records
  a crossing at **134.31310297954988**, about **15.1869 frames early**. Both are
  in `[120,150)`, so event error and window-count error improve from 1 to 0
  here, even though timing is visibly imperfect. The baseline has no matched
  crossing; its timing error is undefined, not zero.

Thus “same ID” and “correct box/trajectory” must be evaluated separately.
The baseline gap alone does **not** prove the Mahalanobis gate rejected a
particular detection. The candidate's box alone does **not** prove a real-world
identity or a detector false positive.

For completeness, the report compares localization on **identical reference
frame/object keys matched by both variants**, rather than comparing means over
different matched subsets. In this example there are 287 common matched frames;
bottom-centre mean error is about 0.3831 world units for baseline and 0.3933 for
gate-off. These conditional means exclude the misses and cannot substitute for
coverage/counting safety. World units belong to the toy geometry, not calibrated
measurements from a real installation.

### A second symptom: an extra crossing before either box pulse

In separated-opposing, seed 2001, box-error-only, both variants retain the same
three predicted crossings for two reference crossings. An extra positive
crossing on ID 2 occurs at frame **127.29480328576642**, around X = **2.7992**.
The true positive-direction crossing belongs on the other path, X = −2.8;
the fixed matcher therefore cannot accept this as that reference event.
It occurs **before** the first imposed shape pulse at frame 135 and appears in
both variants, so not every count artifact can be attributed to an ID change at
the pulse boundary. Internal tracing should cover startup and saved crossing
brackets too, not just pulse transitions. This is a saved-output observation,
not proof of a particular filter or counting-rule defect.

## Evidence and reproduction

The compact `experiments/box_gate_diagnosis_v1_evidence.json` pins the new script,
tests, unchanged reader/auditor helpers and external full diagnosis artifact.
The new code is **post-study exploratory analysis**, not part of the earlier
frozen execution harness. Original protocol locks, indices, bundles, freeze and
consumed opening remain untouched.

```bash
python -m experiments.box_gate_diagnosis \
  --root /absolute/path/to/visiontrack \
  --development /absolute/path/to/original/development/bundle
```

Default output is JSON on standard output. Optional `--output` creates a **new**
external JSON file; it refuses overwrite and paths inside this repository or the
development bundle's parent directory. Existing raw evidence and Git history are
required. The compact index alone cannot reproduce the full report.

## Next question, before another algorithm change

The narrower question is: **which association decision and subsequent box-state
update produces each observed gap, overlap failure and crossing artifact?**

- [x] Specify a development-only diagnostic trace before running it: candidate
  IoU, full-state Mahalanobis distance/threshold, stage, assignment/rejection,
  track lifecycle and pre/post-update box state around the fixed pulse boundaries,
  startup and saved crossing brackets (including the shared pre-pulse artifact).
- [x] Build/test opt-in instrumentation outside the production behavior path:
  [observer contract and authored implementation tests](BOX_GATE_TRACE.md).
  Require exact public-output parity with the saved development records; stop
  if instrumentation changes the numerical behavior. A trace replay would be
  a newly disclosed diagnostic run, not the old once-only study or fresh validation.
- [x] Add and commit the [saved-evidence/provenance wrapper](BOX_GATE_TRACE_REPLAY.md)
  before the diagnostic replay. Observer fixture parity is not yet parity with
  authenticated saved study outputs; no actual study trace has been run.
- [x] Execute the [development-only diagnostic](BOX_GATE_TRACE_FINDINGS.md) and require complete
  exact saved-output parity before interpreting its internal trace evidence.
- [ ] Use that evidence to choose between narrower association, state-estimation
  or counting hypotheses. Position-only gating, a different state model,
  ground-plane motion and appearance are possibilities, **not accepted fixes**.
- [ ] Register any new intervention comparison with new held-out cases and
  explicit joint continuity/localization/counting safety before observing outcomes.

Neither consumed split becomes untouched again. Representative rights-reviewed
real data, usability and practitioner discovery remain separate pending gates.
No additional recording or owner assistance is needed for this diagnostic work.
