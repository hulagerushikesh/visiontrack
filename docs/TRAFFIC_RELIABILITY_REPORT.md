# Complete development-grid export

The [frozen traffic protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) now has a
development-only exporter connecting the verified runner, crossing scorer and
tracking/contact diagnostics. **An exporter is not a completed study.** This
page initially documents the implementation; measured development findings
will be recorded separately after the committed harness runs all 120 cases.
Held-out tracking remains unopened, and no tracker behavior changes here.

## What the report will tell us

For each of three toy paths, run all ten registered development noise seeds
under four conditions: control, perspective only, box error only and both.
That is 120 runs, not 120 independent camera sites or people. Each run retains
the runner's three-pass reset/fresh reproducibility check.

Keep all four absolute results, each condition minus its paired control, and
the interaction `combined - perspective_only - box_error_only + control`.
The interaction describes whether the combined outcome differs from the sum
of the isolated differences in these scenes; it is not proof of a generally
causal mechanism or a newly better tracker. Nothing ranks a winning method.

The fixed comparison includes 37 endpoints: all crossing summaries for both
anchors; matched/missed object-frames, completeness, ID switches, fragmentation
and FP; and sample counts/mean contact distances for observations and matched
tracks. All additional position statistics, region/pulse strata, per-frame
errors, failure records and output boxes remain in the full per-run records.

For each scenario, show every seed and descriptive seed mean/min/max. A mean
does not turn correlated frames or noise repetitions into independent evidence.
No p-values, confidence intervals or grand cross-scenario average are produced.
Undefined values propagate into differences/interactions. Aggregates state
defined and undefined seed counts; they do not replace missing errors by zero.
Unfavorable and zero differences are retained, not filtered away.

## Run only from a committed, clean checkout

Commit the tested exporter first. From the local repository root:

```sh
python -m experiments.traffic_report --output /absolute/new/external/development-bundle
```

Use `PYTHONPATH=src` if the checkout is not installed. The output's parent must
exist, but the output directory itself must **not** exist. It must be outside
this repository. Existing attempts are never overwritten or cleaned up.
There is no split, seed-selection, config override or held-out option.

The exporter checks tracked cleanliness, actual HEAD and every `traffic_*.py`
source against that commit. The runner still checks the pinned package baseline.
Before any tracking, it saves the full fixed input plan/digests. Across all runs,
input manifests, protocol/config/output/record hashes, experiment source,
baseline source and environment must agree with the plan and each other.
It rechecks the committed harness at the end. No network, footage or model
download is needed. Environment metadata is not a cross-machine bit-parity claim.

## Bundle contents and failure handling

- `plan.json`: actual harness revision/source hashes, full protocol recipe and
  120 ordered development input manifests, saved before tracker execution.
- `attempts.jsonl`: flushed start/success/failure ledger, without timestamps
  that would needlessly change reproducible bytes.
- `runs/<scenario>/<seed>/<condition>.json`: full evidence and provenance for
  each successful run, with no raw personal imagery or persistent identities.
- `summary.json`: all absolute endpoints, seed-paired differences, interactions
  and per-scenario descriptive aggregates with explicit missingness counts.
- `summary.md`: human-readable primary counting/tracking tables, including
  paired differences and interaction, plus interpretation limits.
- `manifest.json`: status, attempted/successful/unattempted counts, first error,
  file SHA-256s and a separate self-excluding manifest digest.

On an error, stop and keep the evidence; do not silently skip a seed, repair a
box or rerun selectively. A failed/incomplete grid does not get a complete
comparison summary. An interrupted process may leave a plan and partial ledger
without a final manifest; that is not a completed bundle. Hashes establish
integrity, not research validity or real-world accuracy.

Tests use explicitly fake outcomes for arithmetic and file-handling oracles,
not performance evidence. They cover complete-grid enforcement, positive/zero/
negative/null contrasts, exact hand-calculated interaction, environment/source
drift, failed-attempt preservation, every file digest, byte-identical repeated
fixture bundles, no overwrite, and held-out/config override rejection.

## Remaining gates

Run and inspect the complete development grid, retain its manifest and honest
findings, then separately freeze the **complete** harness and input digests
before one-pass held-out tracking. A development export is not that final
held-out freeze. No new intervention, tuning, real-data transfer, upstream
contribution or C++ port is authorized by a development result alone.
