# Box-gate ablation — reporting and numerical-rule harness

Implementation milestone, **2026-10-23**. The development exporter, complete-grid
summary and registered numerical rules are implemented and tested. **No actual
new baseline/candidate experiment or new held-out tracking was run in this step.**
The test data are hand-worked endpoint tables and explicit replay/export doubles.

## In plain language

We have built the experiment's checked results folder, not discovered whether
turning the gate off works. It must keep every attempt and ask three questions:

1. Did we really compare the same inputs with only the intended setting changed?
2. Did enough broken cases improve by the margins chosen before the experiment?
3. Did even one case get worse on the registered ID, miss, false-positive or
   counting measures? A better average cannot hide that case.

Development results alone cannot answer the complete study question. The new
held-out set remains unopened; its separate freeze/opening gate is later work.

## Development export boundary

`experiments/box_gate_report.py` exposes only `export_development(output)` and
a development-only CLI. There is no arbitrary split, variant or configuration
override. Before tracking, it requires a clean Git worktree and verifies the
complete current `traffic_*.py` / `box_gate_*.py` experiment and matching test
sources, package initializer, project settings, protocol documents and locks
against committed HEAD. The pinned production package and runtime metadata are
recorded separately. The whole development harness must be committed before
the full grid is run.

The output must be a **new, nonexistent directory outside the repository**.
The fixed order is scenario → seed → condition, with baseline then gate-off
inside each pair. All 120 pairs, 240 variant runs and 720 passes are required.
No skipped case, replacement seed, filtered result or automatic retry is allowed.

Each completed variant is saved through the replay adapter's private byte-only
sink before the next variant starts. If candidate construction/replay fails,
the finished baseline remains available. A variant that itself fails before
completion has no complete variant record; the attempt ledger records the error.
Partial variant files are explicitly not yet validated paired evidence.

Completed pair validation checks:

- exact planned input, one-switch configuration, source/runtime lineage and
  registered variant order;
- actual detector-stream receipts for all six passes, 300 updates per pass,
  reset/fresh equality flags and output hashes;
- full re-scoring of retained public rows against the unchanged reference
  scorer, rather than trusting a self-consistent advertised endpoint hash;
- all 37 candidate-minus-baseline differences, with null propagation;
- shared truth/random draws across the four conditions and shared ideal truth
  within each projection pair;
- unchanged harness/runtime before and after pairs and at grid completion,
  plus saved-file hashes before sealing a complete bundle.

Re-scoring is a consistency check using the same scorer, **not an independent
scientific implementation**. The later saved-record audit remains necessary.

## Retained files

```text
new-external-bundle/
  plan.json                         # exact selectors, inputs, source and runtime
  attempts.jsonl                    # starts, retained variants, success/failure
  pairs/<scenario>/<seed>/<condition>/
    baseline.json                   # finished variant; may survive failed pair
    gate_off.json
    pair.json                       # both variants, full rows and diagnostics
  summary.json                      # only after all pairs validate
  summary.md                        # short readable development overview
  manifest.json                     # complete/failed, counts, hashes, error
```

A normal complete export has 364 indexed files plus the manifest itself, and
480 ordered ledger entries. The manifest's own fingerprint excludes its own
digest field. An error stops further pairs and retains the partial folder.
Interruption or storage failure can leave an unsealed partial folder: absence of
a valid complete manifest is never evidence of completion. Checksums are workflow
integrity, not a malicious-runtime sandbox or a power-loss durability guarantee.

Developer command for the **later** committed development run (not executed in
this milestone; replace the placeholder with a new external path):

```bash
PYTHONPATH=src python -m experiments.box_gate_report /absolute/path/to/new-development-bundle
```

## Numerical rules are separate from provenance

`experiments/box_gate_decision.py` evaluates supplied tables with exactly the
37 registered endpoints and both fixed variants. It does not generate input
measurements, instantiate a tracker or establish that a tracker produced a table.
Every rule result explicitly states that provenance and execution are not
established by the rule evaluator.

The [registered policy](BOX_GATE_ABLATION_PROTOCOL.md) is unchanged:

1. Invalid/incomplete evidence, or inadequate baseline challenge in either split
   → **inconclusive**.
2. Otherwise, any registered per-case regression → **failure**.
3. Otherwise, all 37 endpoints identical in every pair → **no effect**.
4. Otherwise, missing either benefit margin in enough scenarios → **failure**.
5. Otherwise → **pass**, a bounded synthetic numerical screen only.

The primary denominator is the registered reference-object count, not returned
IDs. Each scenario's primary averages the 20 box-error cases. Thresholds use
exact rational comparisons; no fitted tolerance is introduced. Every control
case is included in non-regression checks. Undefined conditional values are
retained, not filled with zero. Summaries retain per-seed absolute endpoints,
differences, scenario/condition mean/range and defined/undefined seed counts.
They do not pool camera sites or calculate confidence intervals/p-values.

Even a hypothetical pass authorizes neither a production default change nor a
C++ port. The development summary's complete-study numerical classification is
necessarily inconclusive because held-out evidence is missing.

## Verification and next action

**78 new tests** cover the pure rules and report/export plumbing. They prohibit
actual tracker construction. Hand-worked tables cover both margin boundaries,
per-object normalization, split independence, all safety gates, negative/no-effect
outcomes, nulls and malformed/incomplete evidence. Replay doubles exercise the
real scorer and partial-variant sink. Export doubles cover the complete ordered
grid, exclusive paths, retained failures, source drift and altered saved files.
They are not experimental outcomes or proof of actual tracker reset parity.

This implementation milestone is now followed by the completed
[120-pair development run and saved-record audit](BOX_GATE_DEVELOPMENT.md).
The harness ran unchanged from `817e6f7`; candidate safety requirements failed
despite improved ID switches. Next: build/freeze the separate new held-out
execution gate and open that set once, without tuning. No new owner recording
or action is required. See the [progress overview](PROGRESS_OVERVIEW.md).
