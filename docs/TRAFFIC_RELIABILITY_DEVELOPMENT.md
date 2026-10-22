# Traffic mechanism — complete development findings

Executed 2026-10-22 with committed harness
`19a7c821ea4b8d1f54d0ffc0450beb9391b38e1e` and the unchanged baseline at
`16c287a6b18c5c142a28e4bce70b3232946459db`. **120/120 development runs
completed; no failed or skipped case. Held-out tracking was unopened at this
development milestone.** The subsequent one-pass held-out results are now in
the [combined scoped findings](TRAFFIC_RELIABILITY_FINDINGS.md).
The [frozen v1 protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) is unchanged. These
are synthetic development findings, not proof of a better tracker, traffic
performance, novelty, an upstream partnership or a completed research study.

## What we learned in plain language

1. **The imposed box errors expose a real failure of this baseline in these
   simulated scenes.** They increase ID switches, misses and counting errors.
   Correct motion underneath the detection box does not ensure stable tracking.
2. **Perspective alone did not worsen the primary crossing/count/ID measures
   in this development grid.** That negative finding stays visible. Position
   errors did change; zero count differences do not mean every output is equal
   or that perspective is harmless for other cameras or trajectories.
3. **The combination is not uniformly worse on every metric.** In the two
   two-object paths, it adds some misses/FP on average but slightly reduces ID
   switches relative to box error alone. We do not hide that mixed result or
   invent a general winner from it.

## Absolute outcomes, including unfavorable ones

Numbers are **means over ten noise seeds**, with ID-switch ranges shown in
brackets. These are repeated observations of three fixed paths, not independent
scenes or camera sites. Counts are per run, not a confidence interval.
All other endpoint ranges, individual seeds, paired differences and interaction
are retained in the exported `summary.json` and primary tables in `summary.md`.

| Path | Condition | Primary crossing misses + extras | ID switches, mean [range] | Missed object-frames, mean | False-positive rows, mean | Completeness, mean |
| --- | --- | --- | --- | --- | --- | --- |
| solo | control | 0 | 0 [0, 0] | 2 | 0 | 0.993333 |
| solo | perspective_only | 0 | 0 [0, 0] | 2 | 0 | 0.993333 |
| solo | box_error_only | 1 | 3.4 [2, 4] | 9.3 | 2.1 | 0.969000 |
| solo | combined | 1 | 3.4 [2, 4] | 9.3 | 2.1 | 0.969000 |
| opposing | control | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| opposing | perspective_only | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| opposing | box_error_only | 2 | 7.3 [6, 8] | 16.3 | 2.9 | 0.972833 |
| opposing | combined | 2 | 7.1 [6, 8] | 17.4 | 3.6 | 0.971000 |
| converging | control | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| converging | perspective_only | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| converging | box_error_only | 2 | 7.3 [6, 8] | 16.3 | 2.9 | 0.972833 |
| converging | combined | 2 | 7.1 [6, 8] | 17.4 | 3.6 | 0.971000 |

The primary bottom-centre crossing recall is zero for both box-error conditions
on every development path/seed, versus one in the controls. The scorer reports
those missing crossings rather than turning unmatched timing/position error
into zero. This is a deliberately severe imposed perturbation: it is **not a
claim that actual traffic detectors miss all crossings**.

Completeness can still be around 97% while a critical crossing is missed. That
is why an operational event measure and trajectory diagnostics are both needed.
Initial confirmation accounts for the control's first two misses per object.
The opposing and converging paths give identical values for these selected
tracking/count endpoints; they are not independent confirmations of generality.

The count-error interaction is zero for all paths/seeds. For each two-object
path, mean interaction is -0.2 ID switches, +1.1 missed object-frames, +0.7 FP
rows and -0.00183333 completeness. The solo primary interaction is zero.
These descriptive contrasts do not establish statistical significance.

## Position error is a different question

For `solo`, mean matched bottom-contact error is approximately 0.000199 toy
units in control, 0.001000 with perspective alone, 0.402506 with box errors,
and 0.328313 with both. Observation-only error is approximately 0.460856 for
box errors and 0.373505 for both. These are **not surveyed metres**; apparent
improvement in one error measure is not a selected intervention or net gain.
Matched-track means exclude unmatched object-frames and must be read with their
sample counts/completeness. Box-centre remains a secondary diagnostic and is
not a true contact point in this toy observation model.

## Evidence, provenance and reproduction

The [exporter guide](TRAFFIC_RELIABILITY_REPORT.md) describes the 37 fixed
comparison endpoints, full records and fail-closed attempt handling. The
machine-readable index is
[`experiments/traffic_development_v1_evidence.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_development_v1_evidence.json).

The locally retained external bundle contains 120 full records, a pre-run
input plan, attempt ledger, JSON/Markdown summaries and a manifest. All **124
non-manifest file SHA-256s** and the manifest's separate content digest were
independently checked after export. It contains generated geometry/results,
not recordings, images, consent records or personal identity data. Raw generated
outputs stay outside Git; the index records the source and key artifact hashes.

Runtime: Python 3.12.9, NumPy 2.3.1, Darwin arm64, little endian. This records
the tested environment, not a claim of bit-identical results under every native
numerical library. Each run passed reset and fresh-instance replay checks.
Use the recorded harness revision to reproduce; a later reporting change can
legitimately change output hashes and must not be silently labelled identical.

## What this permits next — and what it does not

The [complete harness/input freeze](TRAFFIC_RELIABILITY_HOLDOUT.md) was prepared
before the subsequent single held-out export. Its [scoped findings](TRAFFIC_RELIABILITY_FINDINGS.md)
are now recorded, without tuning on held-out outcomes.
A proposed fix needs its own registered question, practical margins
and new untouched evidence; this study does not automatically select that fix.
Rights-reviewed real data, RQ5 re-entry, volunteer consent and practitioner
validation remain separate gates. There is no C++ change or website behavior
change from these development results, and no owner action is needed yet.
