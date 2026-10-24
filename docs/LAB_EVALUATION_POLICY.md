# Lab evaluation policies: old evidence stays old

Checkpoint: **2026-10-24**. New Lab results now explicitly adopt the independently
checked [MOT17 preprocessing v2](MOT17_PREPROCESSING.md). This is measurement
consistency, not a new tracker, an accuracy improvement or a package release.

## Why this matters

Before measuring a tracker, we decide which reference objects count and which
outputs to exclude. Those **input-filtering rules** are different from the
**metric formulas** that score the remaining boxes. Changing either can change
a result without changing a single tracker output.

The Lab now carries both definitions from the metric artifact through failure
events, comparison summaries and the browser/offline report. It refuses to
compare different policies instead of presenting an unexplained improvement.

## Supported contracts

| Metric artifact schema | Metric evaluator | Stored `preprocessing` | Executed filtering |
| --- | --- | --- | --- |
| 1, historical | Implicit `visiontrack.metrics/v1` | `visiontrack.eval.mot17.preprocess_frame` | `visiontrack.mot17-preprocessing/v1` |
| 2, historical | Explicit `visiontrack.metrics/v2` | `visiontrack.eval.mot17.preprocess_frame` | `visiontrack.mot17-preprocessing/v1` |
| **3, new** | Explicit `visiontrack.metrics/v2` | **`visiontrack.mot17-preprocessing/v2`** | **v2** |

Only the metric artifact becomes schema 3. Experiment, source, run, failure,
comparison and report schemas remain 1; reports carry an optional preprocessing
identifier for the new contract. Missing identifiers in historical reports
mean the historical Lab policy, not the current default. No evaluator-v3 tag
is invented: metric formulas remain v2. The supported CLEAR/identity IoU
threshold is still **0.5**, while HOTA retains its own threshold sweep.

Unknown policies, incompatible schema/policy pairs, unsupported thresholds and
mismatched failure context are rejected even if someone recomputes the hashes.
Comparisons and failure extraction reject mixed evaluation definitions.

## Old evidence is not upgraded

- Existing schema-1/2 metrics select legacy filtering explicitly. Their old
  failure IDs, report IDs and serialized bytes stay unchanged.
- New calculation writes schema 3. It cannot overwrite an old metric file.
  Use a new bundle/output root for new evaluation; keep the historical bundle.
- Before publishing metrics or failures, every variant is checked for known
  conflicts. A conflicting later variant does not publish the earlier variants.
  This is preflight protection, not a multi-file transactional filesystem.
- Frozen study source guards and receipt hashes are not relaxed. Historical
  research is not silently rerun under the new rules.
- Track/detection payloads, tracker configuration and runtime behavior do not
  change. Nothing is sent to a server by importing a report.

## What the user sees

The Lab comparison explanation identifies both the metric evaluator and input
filtering policy. It explains that different rules are not directly comparable.
The metric table uses the matching evaluator's wording: v2 fragmentation marks
a **resumed match after an interruption**, and v2 mostly-tracked means **more
than 80%**, not at least 80%. Historical descriptions are retained for old reports.
The offline report includes the policy in its limitations and fingerprint.

To rehearse with the current checkout, generate a new synthetic bundle in a
new output folder; do not reuse the earlier showcase folder:

```bash
# From the VisionTrack repository, with its lab dependencies installed:
PYTHONPATH=src python -m visiontrack.cli lab-demo ./lab-policy-rehearsal
# Preview first; only then create the new bundle:
PYTHONPATH=src python -m visiontrack.cli lab-demo ./lab-policy-rehearsal --write
```

Import the exact report path printed by the second command into `/lab`. This
is still a synthetic workflow exercise, not a real-world performance result.
The published `visiontrack-mot 0.3.0` package is not changed by this source update.

## Verification

- Exact historical v1 **and v2** report JSON/HTML and failure-stream golden
  hashes were captured by executing unmodified revision `87575c9` before this
  migration. Current legacy reconstruction must match those bytes.
- A hand-defined case includes an ignored pedestrian and a car with matching
  outputs. Legacy filtering removes both outputs; v2 retains them, giving two
  false positives. Metrics and extracted events must agree; this is a policy
  example, not evidence that these labels describe real imagery.
- That new report is a shared Python/browser fixture. Tests check the complete
  generated model, import acceptance, exact exported canonical report/event
  fingerprints and rejection of missing, unknown or conflicting policy identifiers.
  The byte check preserves Python's numeric serialization; it does not treat
  JavaScript reserialization as a universal numeric-report hasher. Browser import
  validates structure/lineage; source revalidation remains the local Python path.
- Tests exercise immutable reruns, later-variant conflicts, mixed policies,
  threshold rejection and unchanged source/track bytes.
- Existing decision/import and image/playback round trips run with freshly
  generated schema-3 metrics. No human acceptance decision is made by these tests.

Local verification: **985 tests pass, one slow test deselected**, including the
bootstrap that executes **1,099 historical tests at their original revision**.
All eight browser contract/workflow scripts, TypeScript, production app build,
Ruff and strict documentation build pass. Remote CI/deployment are separate checks.
The actual earlier showcase report still has its original ID
`b8b8760c1c6616856577082bcb2e3e96cf3d3ee961ab3dc3c00f3b4dfb109f96`
and JSON SHA-256
`184445099c301764a2f87fcd7793973beb975898e3e88d632105836be6c35837`.

A separate CLI preview/write rehearsal created new schema-3 metrics outside
the repository, without modifying that old showcase. Its report ID is
`d37d847100489f7cee7f3f083e9085f7bd2a4c0dbbf140d46f51409c62b2f3fc`,
JSON SHA-256
`197efc039a63276934f4a2e5d059a26754743f621d0a7c2bea972eb21fadd01e`.
Both synthetic configurations still tie: FN 23, FP 0, IDSW 0, Frag 9, 64 total
failure events across both variants. A new policy tag is not a new research win.

The [corrected MOT17 coverage and 36–57 trace](MOT17_COVERAGE_V2.md) remain
separate sealed evidence. This migration does not add pixels, verify reference
labels, establish a cause or justify a gate/lifetime/memory intervention. Next:
resolve lawful independent visual/reference review of the same fixed event,
then justify one prospectively fixed comparison or a reasoned stop. C++ remains
on its accepted runtime contract; scorer-only work does not require a port.
