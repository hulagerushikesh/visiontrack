# Box-gate held-out safeguards — preparation, not execution

## What this step finishes

Milestone **7a** implements and tests the code/input/evidence freeze and its
read-only verifier. Milestone 7 as a whole is **not finished**. No real ablation
freeze or opening has been issued, and no new held-out tracker has run.

Think of a freeze as a sealed experiment checklist: it records exactly which
code, settings, runtime, earlier evidence and future input cases may be used.
The later execution gate must still consume a single opening before it starts
the tracker. A freeze alone is not permission or proof of execution.

Implementation:
[`experiments/box_gate_holdout.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/box_gate_holdout.py).
It exposes preparation and read-only verification only; there is deliberately
**no `run` command or held-out replay/export entry point yet**.

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
creates an opening claim. A future executor must use exclusive creation itself;
a read-only precheck is not sufficient to prevent a race between two executors.

## Validation and scope

Tests use explicit provenance/audit doubles and hand-specified mutations, while
the input-only check generates all 120 new manifests. Actual tracker constructors,
the scorer and the old traffic scene generator are forbidden in these tests.
Checks cover resealed forgeries, changed revisions/settings/runtime/inputs,
incomplete or modified development files, symlinks, duplicate/nonfinite JSON,
size bounds, existing outputs and consumed openings.

Separately, the new development-evidence verification was run read-only against
the actual retained development bundle and original audit. All 365 bundle files
verified; all 174 violations remained present. This did not rerun any tracker.

The saved auditor still trusts recorded canonical correspondence and input
manifests as primitives. It does not independently prove the raw geometry,
scientific validity, real-world accuracy or tracker execution. Local checks are
workflow safeguards, not a malicious-runtime sandbox or a global registry that
can prevent someone copying a freeze or deliberately disguising a rerun.

## Next: finish the execution gate before issuing the real freeze

1. Implement/test a properly isolated held-out scorer/replay adapter and complete
   ordered exporter. Keep the public development APIs rejecting held-out inputs;
   do not monkeypatch their guards or relax the opened original traffic recipe.
2. Require an exclusive opening claim **before the first tracker construction**.
   Retain each completed variant and all attempts, stop at the first error, and
   leave partial evidence intact. No automatic retry or selective replacement.
3. Review and commit that entire harness and its tests. Only then issue the real
   code/runtime/evidence/input freeze and verify it before one ordered run:
   120 pairs, 240 variants, 720 fresh/reset/fresh passes.
4. Audit combined evidence and apply the unchanged registered decision rules.

Do not invoke preparation now simply to create a premature official freeze:
the forthcoming execution code would change its revision and invalidate it.
No production setting, C++ behavior, website, release or outreach changes here.

The development candidate is still **not accepted**. Completing held-out evidence
cannot erase its development safety violations. This next run completes a
prospective negative study; it is not a search for a more favorable result.
