# Box-gate held-out safeguards — freeze and once-only run completed

## What this step finishes

Milestones **7a and 7b** implement and test the code/input/evidence freeze,
read-only verifier, separate reference-scoring/replay adapter and exclusive
full-grid execution gate. **Milestone 7 is now complete:** the real freeze was
issued and verified from committed harness `c99c4e7`, then all 120 held-out pairs
ran once without errors or selective retries. See the
[held-out results and evidence inventory](BOX_GATE_HELDOUT_RESULTS.md).
The subsequent [saved-record arithmetic and combined audit](BOX_GATE_FINDINGS.md)
has now completed milestone 8 with a failure classification. This page describes
the preserved execution safeguards, not permission to reopen the experiment.

Think of a freeze as a sealed experiment checklist: it records exactly which
code, settings, runtime, earlier evidence and future input cases may be used.
The separate execution gate must still consume a single opening before it starts
the tracker. A freeze alone is not permission or proof of execution.

Implementation:
[`experiments/box_gate_holdout.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_holdout.py).
It exposes preparation and read-only verification only. Execution lives in
[`experiments/box_gate_execution.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_execution.py),
the explicit whole-grid opening entry point. It has no case, configuration,
resume or retry option. Do not run it before the complete harness is committed
and its exact freeze verified.

## What is bound and checked

- A completely committed, clean checkout, including untracked-file checks.
  All current `traffic_*.py` and `box_gate_*.py` experiment files, matching tests,
  package settings, initialization, both exact protocol/document locks and the
  reviewed development evidence index are bound to committed bytes.
- All 57 package source files remain identical to the original registered
  tracker baseline. Both full configurations are explicit; the candidate still
  differs only in `use_mahalanobis_gating=false`.
- Python/NumPy/platform/architecture/byte-order metadata and local import
  origins are checked. The runtime must match the reviewed development runtime;
  this is not a cross-platform bit-parity guarantee.
- All 365 development bundle files are checked using fixed registered relative
  names, bounded reads, exact coverage and hashes. Links and undeclared files
  are rejected. The adjacent original `audit.json` is pinned by the reviewed
  index, not discovered from arbitrary paths inside JSON.
- The saved-record auditor reconstructs the development arithmetic again.
  Its complete result must agree with the pinned original audit, including all
  **174 safety endpoint violations**, not just a favorable primary mean. Historic
  JSON spellings such as `4` versus `4.0` can represent the same numeric value;
  original bytes are retained, booleans do not alias numbers, and no numeric
  tolerance is used to excuse a changed audit value.
- All **120 new held-out input manifests** are generated in the registered
  order and hashed: three paths, seeds 4001..4010 and four conditions. This is
  numeric input geometry only, not tracking or performance measurements.
- A freeze binds its exact Git revision. Even a later documentation-only commit
  invalidates verification. This deliberately avoids a permissive descendant
  exception; do not silently re-freeze to bypass a refusal.

Preparation never overwrites an existing directory. Verification is read-only
and rejects an existing `opening.json`, including a dangling link. It never
creates an opening claim. The separate executor uses exclusive creation itself;
a read-only precheck is not sufficient to prevent a race between two executors.

## Separate execution gate (7b)

The public development scorer, replay wrapper and pair validator still reject
held-out inputs. Shared private arithmetic/replay cores avoid monkeypatching
those guards or relaxing the opened original traffic recipe. Private Python
helpers are not a security or permission boundary.

The new whole-grid entry point:

1. Re-verifies the original exact freeze, development audit and all planned inputs.
2. Exclusively creates and flushes `opening.json` **before any tracker call**.
   A losing concurrent caller cannot overwrite the winning claim or replay a case.
3. Writes the complete fixed plan, then processes all 120 pairs in registered
   order. Each variant uses isolated fresh/reset/independent-fresh passes.
   Actual detector handoff receipts, full configurations and all public rows remain
   bound to the input digest and unchanged tracker baseline.
4. Saves and flushes each completed variant before the next variant is attempted.
   The pair is retained before full reference re-scoring/lineage validation.
   Every attempt is logged; the first error stops further cases.
5. Checks the freeze, opening claim, source and runtime around each pair, then
   re-audits development evidence and seals exact output-file coverage/hashes.
   All 37 endpoints, null counts, per-seed differences and safety regressions
   remain visible. A held-out-only summary is not a combined study verdict.

An exception or interruption leaves the opening consumed. Even a failed plan
write cannot justify deleting the claim and retrying. An abrupt interruption
can leave unsealed partial files rather than a final manifest. A failed replay
that returns no variant records execution as unknown, not falsely unexecuted.
Flush/fsync improve local retention but do not guarantee recovery from every
power/storage failure. Do not copy or reissue a freeze to disguise a rerun.

## Validation and scope

Tests use explicit provenance/audit doubles and hand-specified mutations, while
the input-only check generates all 120 new manifests. Actual tracker constructors,
the scorer and the old traffic scene generator are forbidden in these tests.
Checks cover resealed forgeries, changed revisions/settings/runtime/inputs,
incomplete or modified development files, symlinks, duplicate/nonfinite JSON,
size bounds, existing outputs and consumed openings.

The execution-gate tests separately use hand-fed ideal/empty rows, explicit
empty-output replay doubles and provenance/audit doubles, never the real tracker.
They cover all held-out paths/conditions analytically, the full ordered exporter,
exclusive-claim races, wrong-order variants, resealed record forgeries, source/input
drift, interrupted/failed runs, storage failures and final artifact tampering.
Those temporary test exports are not research outcomes.

After extracting shared cores, all 24 saved development variant records for seed
2001 (three scenarios, four conditions, two variants) were re-scored with exact
canonical record equality. This is saved-row consistency, not a new tracker run
or an independent scientific validation.

Separately, the new development-evidence verification was run read-only against
the actual retained development bundle and original audit. All 365 bundle files
verified; all 174 violations remained present. This did not rerun any tracker.

The saved auditor still trusts recorded canonical correspondence and input
manifests as primitives. It does not independently prove the raw geometry,
scientific validity, real-world accuracy or tracker execution. Local checks are
workflow safeguards, not a malicious-runtime sandbox or a global registry that
can prevent someone copying a freeze or deliberately disguising a rerun.

## Actual opening and next step

The complete execution harness was committed before preparation. The exact
freeze binds revision `c99c4e72bf0fd6a740ec0b22135448b931eac448`, all 120 inputs,
the reviewed negative development evidence and the same runtime. It was verified
before the exclusive opening. All 120 pairs / 240 variants / 720 passes completed.
The retained evidence inventory checked all 365 files and 480 ledger entries;
the [compact index](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_heldout_v1_evidence.json)
records exact paths and hashes. No tracker was rerun for the inventory.

The original opening is **consumed**. Do not retry, tune or selectively replace
a case, and do not call these inputs untouched evidence for a later candidate.
The subsequent saved-record and combined-study audit is complete; see the final
findings above. There is no further opening. The pinned development auditor
remains unchanged.

Every later commit invalidates an unused freeze, even a documentation change.
Bind the actual run to the reviewed committed harness, not a pre-commit snapshot.
No production setting, C++ behavior, website, release or outreach changes here.

The candidate is still **not accepted**. Held-out saved results also show safety
violations, and cannot erase the earlier development violations. The completed
combined audit retains both sets of failures, not a more favorable subset.
