# Box-gate ablation — held-out execution record

**2026-10-23. Milestone 7 is complete.** The fixed grid ran once from clean
committed harness `c99c4e72bf0fd6a740ec0b22135448b931eac448`, after preparation
and read-only verification of the exact code/runtime/evidence/input freeze.
All **120 pairs / 240 variants / 720 fresh/reset/fresh passes** completed,
300 updates per pass, without errors, skipped cases or selective retries.

This page records milestone 7's saved results and inventory. **Milestone 8 is
now complete:** see the [final combined audit and findings](BOX_GATE_FINDINGS.md)
for the registered **failure** classification. The original compact index retains
its historical pending flags; a separate combined index records the final audit.
Neither this execution record nor that verdict is a real-traffic accuracy claim.
The candidate remains **not accepted**; defaults,
package source, parity fixtures, website behavior and C++ remain unchanged.

## What this means in plain language

Disabling the shape-sensitive rejection check again kept IDs stable in these
toy paths. But the output rectangles and crossing/count measures still worsened.
**A stable ID is not enough to call a tracker better.**

The saved held-out endpoints contain **206 safety violations across all 60
box-error pairs**. A pair can violate several endpoints: this is not 206
independent experiments. The other 60 control/perspective-only pairs have
identical baseline/candidate values for all 37 endpoints.

The earlier development evidence remains binding: its 174 violations have not
been removed, reclassified or used to tune another candidate. Both sets of
raw evidence now exist; their combined interpretation is in the final findings.

## Fixed comparison and saved results

The [registration](BOX_GATE_ABLATION_PROTOCOL.md), four protocol artifact hashes,
57-file tracker baseline, all 20 settings and evaluation policy are unchanged.
Only `use_mahalanobis_gating` differs between the two variants. Held-out paths
are the registered solo, slanted-opposing and close-opposing paths, using seeds
4001..4010 across four conditions. Seeds repeat noise, not independent sites.

The saved primary means are ID switches per reference object across each
scenario's 20 error-condition cases:

| Held-out scenario | Baseline | Gate off | Both improvement margins |
| --- | --- | --- | --- |
| Solo | 4.00 | 0.00 | Met |
| Slanted opposing | 3.70 | 0.00 | Met |
| Close opposing | 3.70 | 0.00 | Met |

These favorable primary means do not override the per-case safety requirement:

| Non-increase requirement | Pairs worse | Pairs better | Pairs equal |
| --- | --- | --- | --- |
| ID switches | 0 | 60 | 60 |
| Missed object-frames | 50 | 8 | 62 |
| Unmatched public output rows (FP) | 60 | 0 | 60 |
| Bottom-centre missed + extra crossing events | 38 | 20 | 62 |
| Bottom-centre absolute window-count error | 58 | 0 | 62 |

Here FP means a tracker output unmatched by the IoU-0.5 reference evaluator,
not an invented input detection or an identified extra person. There is one
synthetic detection per reference object on every frame.

Ten-seed means below are **baseline → gate off**. ID switches here are per run,
unlike the per-object normalization in the primary table.

| Scenario / condition | ID switches | Missed object-frames | FP rows | Crossing event error | Window-count error |
| --- | --- | --- | --- | --- | --- |
| Solo / box error | 4 → 0 | 6 → 8.8 | 0 → 6.8 | 1 → 0 | 1 → 2 |
| Solo / combined | 4 → 0 | 6 → 8.7 | 0 → 6.7 | 1 → 0 | 1 → 2 |
| Slanted / box error | 7.4 → 0 | 15.2 → 19.2 | 2 → 15.2 | 0.7 → 3.2 | 0.7 → 2.8 |
| Slanted / combined | 7.4 → 0 | 15.2 → 19.2 | 2 → 15.2 | 0.6 → 3 | 0.6 → 3 |
| Close / box error | 7.4 → 0 | 16.6 → 19.2 | 3 → 15.2 | 0.6 → 1.5 | 0.6 → 1.5 |
| Close / combined | 7.4 → 0 | 16.6 → 19.2 | 3 → 15.2 | 0.3 → 1.2 | 0.3 → 1.2 |

All seeds, ranges, null counts, all 37 endpoints and individual regressions
remain in the saved summary; these means do not replace them.

## Why a recovered crossing can still hurt time-window counts

One concrete saved case is solo / seed 4001 / box error. The reference crossing
occurs at frame **149.5**, inside the half-open window `[120, 150)`. Baseline
misses it: crossing-event error 1 and absolute window-count error 1.

Gate off predicts a crossing at about **165.5654**, inside `[150, 180)`.
It is within the fixed 30-frame event matching tolerance, so event error becomes
0. But the earlier window is missing one event and the later window has one
extra: absolute window-count error becomes **2**, not 0.

This is an illustration from saved rows, not a newly selected threshold or
proof of the internal cause. The complete grid stays included. Baseline's
matched timing error is undefined because it has no matched crossing; it must
not be treated as zero or as a directly paired timing improvement.

## Retention and checks completed

The approximately 181 MiB raw bundle stays outside Git:

```text
/Users/rushikeshhulage/Documents/Quant/visiontrack-walkthrough/box-gate-heldout-results-dkipv21_/bundle
```

Its self-excluding manifest SHA-256 is
`840735d9a22434695f59a52bf5f8db37e90b697ecd2b04863b2f98248e274f20`.
The compact committed index is
[`experiments/box_gate_heldout_v1_evidence.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_heldout_v1_evidence.json).
It pins the external freeze, consumed opening, bundle, inventory script/output,
source/runtime and provisional result totals. The raw evidence is not uploaded.

The exact freeze was verified before opening. The exclusive claim was written
before any tracker invocation. The executor checked the unchanged state and
inputs around every pair, regenerated the registered inputs, re-scored public
rows, and re-audited development evidence before sealing the bundle.

A separate retained read-only inventory script checked all 365 files, 480
ordered ledger entries, all 120 pair seals and 240 retained variants, all six
detector receipts per pair, exact settings, original freeze/opening lineage,
41 committed harness files and 57 baseline files. It does **not** independently
reconstruct endpoint arithmetic, geometry or canonical correspondence; those
values remain trusted here. It establishes consistency, not independent proof
of execution or real-world validity. No tracker was rerun for this check.

The original freeze and opening remain outside Git. The opening is consumed:
do not delete it, retry the grid or reuse these cases as untouched evidence for
a tuned candidate. Later commits do not change the recorded `c99c4e7` run.

## Subsequent combined audit

**Milestone 8 is complete:** a separate saved-record auditor checked both splits
without modifying the pinned development auditor or running the tracker again.
The [final findings](BOX_GATE_FINDINGS.md) retain every regression and conditional
null and explain the unchanged registered failure decision.

The held-out-only summary still says `inconclusive` because it intentionally
does not include development rows. That is not a combined classification or a
claim that held-out data is still missing. The combined classification is now
audited/reported separately as failure. Neither split's safety failures were
discarded or averaged away.

No owner recording is needed for the audit. Real-data transfer, representative
detector/camera evaluation, any new registered hypothesis and a future accepted
C++ handoff remain separate. See the [progress overview](PROGRESS_OVERVIEW.md).
