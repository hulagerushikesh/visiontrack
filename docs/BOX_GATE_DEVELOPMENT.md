# Box-gate ablation — development results and saved-record audit

**2026-10-23. Milestone 6 is complete.** All 120 development pairs ran from
clean committed harness `817e6f7c9d802f4a762c6ca00ba26035a9eab6ca`:
240 variant runs, 720 fresh/reset/fresh passes, 300 updates per pass.
There were no failed, skipped, replaced or selectively repeated cases.
At this development snapshot the new held-out grid was **unopened**. It has now
completed separately; see the [held-out execution record](BOX_GATE_HELDOUT_RESULTS.md)
and [final combined findings](BOX_GATE_FINDINGS.md). The final registered
classification is failure; this historical development-only audit stays unchanged.
No tracker defaults, website behavior, Python package source, parity fixtures
or C++ behavior changed.

## What we learned in plain language

Turning off the rectangle-sensitive rejection check kept IDs stable in these
synthetic cases. **It was not an overall improvement.** More output boxes failed
to match the expected object rectangles, and some crossing counts got worse.

Imagine a tracker continuing to say “ID 1” while its rectangle no longer follows
the expected object closely enough. The ID-switch score can look perfect while
the trajectory is still unsuitable for a counting application. This is why we
registered several non-regression checks rather than selecting a winner using
only ID switches.

Here, an FP row means a **public tracker output unmatched by the reference
IoU-0.5 evaluator**. It does not mean the input detector invented another person:
these inputs have one synthetic detection per reference object on every frame.
The audit does not identify the internal cause of each failure.

## Fixed comparison and coverage

The [registered protocol](BOX_GATE_ABLATION_PROTOCOL.md) is unchanged. Baseline
uses the pinned package at `16c287a6b18c5c142a28e4bce70b3232946459db`; candidate
changes only `use_mahalanobis_gating` from `true` to `false`. Both variants
consume the same detections with all other 19 configuration fields unchanged.
All three replay passes agree for every variant, including after reset.

The complete 3-scenario × 10-seed × 4-condition grid was retained. Seeds repeat
noise, not independent people, camera sites or traffic domains. No tuning,
case removal, changed margin or new intervention was introduced after outcomes.

## ID benefit does not satisfy the safety requirement

The registered primary averages ID switches per reference object over each
scenario's 20 box-error cases (ten seeds × two error conditions).

| Scenario | Baseline switches/object | Gate off | Relative reduction | Both improvement margins |
| --- | --- | --- | --- | --- |
| Solo | 4.00 | 0.00 | 100% | Met |
| Separated opposing | 3.75 | 0.00 | 100% | Met |
| Close opposing | 3.75 | 0.00 | 100% | Met |

All three development scenarios meet the baseline-challenge and ID-benefit
margins. Nevertheless, **all 60 box-error pairs violate at least one registered
non-regression requirement**. The other 60 pairs—control and perspective-only—
have identical baseline/candidate values for all 37 endpoints.

| Non-increase requirement | Pairs worse | Pairs better | Pairs equal |
| --- | --- | --- | --- |
| ID switches | 0 | 60 | 60 |
| Missed object-frames | 54 | 4 | 62 |
| Unmatched public output rows (FP) | 60 | 0 | 60 |
| Bottom-centre missed + extra crossing events | 30 | 20 | 70 |
| Bottom-centre absolute window-count error | 30 | 20 | 70 |

These are **174 endpoint violations in 60 distinct pairs**, not 174 independent
failed experiments. A pair can violate more than one measure. Safety checks
compare exact integers per pair; improvements elsewhere cannot cancel them.

## Some absolute results, not just a headline percentage

Each entry below is the ten-seed mean, **baseline → gate off**. Switches in this
table are counts per run; the primary table above normalizes by reference objects.
The full saved summary retains every seed, all 37 endpoints, ranges and null counts.

| Scenario / condition | ID switches | Missed object-frames | FP rows | Crossing event error |
| --- | --- | --- | --- | --- |
| Solo / box error | 4 → 0 | 6 → 9.8 | 0 → 7.8 | 1 → 0 |
| Solo / combined | 4 → 0 | 6 → 9.9 | 0 → 7.9 | 1 → 0 |
| Separated / box error | 7.5 → 0 | 14.8 → 19 | 1.8 → 15 | 0.9 → 1.3 |
| Separated / combined | 7.5 → 0 | 14.8 → 19 | 1.8 → 15 | 0.4 → 1 |
| Close / box error | 7.5 → 0 | 14.8 → 19 | 1.8 → 15 | 1.2 → 3 |
| Close / combined | 7.5 → 0 | 14.8 → 19 | 1.8 → 15 | 0.9 → 2.7 |

Absolute window-count error has the same values as event error in these rows;
this observed equality does not make the measures generally interchangeable.
Controls have zero ID switches, FP rows and crossing errors in both variants;
the initial confirmation delay yields two missed object-frames per object.

The solo crossing improves, but its candidate crossing-time error is still about
15.20 frames (box error) or 15.12 (combined), within the registered 30-frame
matching tolerance. Baseline has no matched solo crossing in those conditions,
so its conditional time error is **undefined**, not zero or a directly paired
timing improvement. Stable IDs are not proof of precise contact localization.

## Verdict and limits

**Development non-regression requirement: failed. Candidate not accepted.**
The stored development-only numerical classification remains **inconclusive**:
both splits are required by the unchanged decision policy, and this historical
summary does not include held-out rows. Both bundles now exist, and the combined
audit/reporting is complete separately. The historical inconclusive wording must
not conceal the already observed violations.
Completing held-out work cannot erase these development violations or justify
acceptance of this unchanged candidate under the registered requirements.

This is a useful negative result for the proposed trade-off, not a wasted run.
It supports keeping the existing default and rejects “zero switches means a
better tracker” for these fixtures. It does not establish a universal detector/
tracker ranking, real pedestrian identity recovery, traffic accuracy, privacy
robustness, statistical significance or a new algorithm. The close sprites
overlap but are not real mutually occluded detector observations.

## Evidence and independent arithmetic checks

The raw bundle is outside Git, about 179 MiB locally:

```text
/Users/rushikeshhulage/Documents/Quant/visiontrack-walkthrough/box-gate-development-xuQjms/bundle
```

Its self-excluding manifest SHA-256 is
`307fe7ad651b0e81befa4715f7b7d7b465007f2f4fb03a28e6af6e24d090570a`.
The committed compact index is
[`experiments/box_gate_development_v1_evidence.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_development_v1_evidence.json).
It records raw file hashes, source/runtime, primary means and every regression
category. Full per-case violations remain in `summary.json` and the neighboring
`audit.json`; neither is replaced by this short index.

The read-only auditor, `experiments/box_gate_audit.py`, was written **after** the
development run. It did not belong to, or alter, the recorded `817e6f7` execution
harness. It imports no tracker, generator, scorer or NumPy, and checks:

- all 364 indexed file hashes plus the manifest seal and exact file coverage;
- 480 ordered ledger entries, 120 paired records, 240 retained variant records,
  exact single-switch configs and all six detector receipts per pair;
- 34 committed harness files, four protocol artifact hashes and 57 pinned
  baseline files, with recorded source/environment consistent across records;
- 8,880 endpoint values reconstructed from saved samples/events; crossing
  matching independently enumerated from retained events under the fixed rule;
- 4,440 paired differences and 1,332 descriptive endpoint groups, including
  defined/undefined seed counts;
- primary per-object denominators and exact rational improvement margins,
  every per-case safety violation, and absence of held-out evidence.

This is independent **saved-record arithmetic**, not independent proof of
execution or an alternative CLEAR-MOT implementation. It trusts retained
canonical correspondence and input manifests; it does not regenerate detector
arrays, ground truth, geometry or contact errors. The exporter separately
regenerated inputs and re-scored public rows using the original scorer.
Diagnostic summation comparisons allow `1e-12` arithmetic tolerance; safety
integers and rational decision margins use no tolerance. The auditor's 27
hand-worked tests cover mistakes, conditional nulls and malformed records;
they do not replay this experiment.

Developer-only repeat of the **read-only audit**, not another tracker run:

```bash
python -m experiments.box_gate_audit /absolute/path/to/bundle --root /absolute/path/to/visiontrack
```

## Next, without changing this candidate

Milestone 7 has now completed the separate exact freeze and once-only held-out
run from committed `c99c4e7`; all 120 pairs finished without errors or selective
retries. See the [held-out results](BOX_GATE_HELDOUT_RESULTS.md), which also
retain safety regressions. Milestone 8 independently audits and reports both
splits together, without changing the pinned development auditor. The purpose
is faithful reporting, not finding a way to turn the candidate into a pass.

No owner recording is needed for these steps. Real-data transfer, a future
separately registered intervention, production-default decisions and any C++
handoff remain separate. See the [two-project progress overview](PROGRESS_OVERVIEW.md).
