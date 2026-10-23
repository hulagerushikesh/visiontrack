# Verified development trace replay wrapper

**2026-10-23. Implementation and safeguards, not new tracking findings.**
The [internal observer](BOX_GATE_TRACE.md) now has a development-only wrapper,
`experiments/box_gate_trace_replay.py`. The exploratory trace is now
[complete and independently audited](BOX_GATE_TRACE_FINDINGS.md): all 240 variant
outputs match their saved development outputs exactly. The safeguards below
describe the committed execution; do not rerun it merely to read the findings.
The closed box-gate experiment remains a failure; defaults and C++ are unchanged.

## What the wrapper does

Before constructing a tracker, it requires a clean committed checkout, verifies
the original development index against its reviewed Git snapshot, checks all
365 original bundle files, and reruns the unchanged arithmetic auditor against
its hash-pinned saved output. The protocol locks, baseline package source and
original Python/NumPy/platform environment must match. Current experiment code,
relevant tests, package source, settings and lock files are hash-watched too.

It regenerates **all 120 development inputs** and requires exact saved-manifest
equality. Both saved variant configurations and complete expected output seals
are checked. Trace windows are fixed from startup, both pulse boundaries and
the union of all saved predicted bottom-centre crossings, including extra events.
No new trace outcome is used to select a case/window.

Only then may a new replay run, in the original development grid order:

1. Write a plan to a **new external output directory**.
2. Record each attempt before constructing its fresh tracker.
3. Supply only copied detection boxes, score, class and no feature—not reference
   identities, world coordinates, calibration or evaluator labels.
4. Verify the actual payload fingerprint collected before **every** update,
   complete output bytes/hash, settings, all 300 frames and the fixed selection.
5. Preserve each trace with interpretation still disabled; recheck code/runtime.
6. Stop at the first error. Preserve failed parity diagnostics or an interruption
   receipt where available. Never silently skip, continue, resume or retry.
7. Only after all **240 variant traces** pass, recheck the full input read set
   and exact written-file coverage/hashes. Seal a complete manifest permitting
   **exploratory inspection only**.

This is one new traced pass per variant, not three new reset-check passes or a
replacement for the original recorded executions. No scoring or endpoint ranking
is performed. Existing evidence is never overwritten, and the consumed held-out
opening is neither read nor modified. The public interface has no split,
scenario, seed, variant, resume or retry selector.

## Records and failure handling

The new directory contains `plan.json`, ordered `attempts/001.json` through
`240.json`, successful `traces/NNN.json`, and a sealed `manifest.json`. Successful
records individually remain unapproved; interpretation requires the verified
**complete manifest**, not a filename, a passing subset or an observer flag.

On ordinary failure the manifest is `failed` with interpretation disabled.
`failed_trace.json` preserves a parity mismatch when available. An interruption
gets a best-effort `interrupted.json`, no complete manifest, and propagates the
interrupt. Disk/power failures can prevent receipts; absence of a complete
manifest never grants approval. The per-file limit is 64 MiB; budget failure is
an error, not permission to truncate. Output files use exclusive creation and
must remain disjoint from the repository and the original development directory.

Local hashes/guards are not a malicious-runtime sandbox, global execution registry
or independently witnessed experiment. A new invocation elsewhere cannot turn
already consumed data into untouched validation. Profiling overhead is not a
runtime benchmark. Synthetic trace evidence is not real-world accuracy, a
production fix or C++ adoption authority.

## Running it later

Do **not** run the command merely to inspect the script: it executes the complete
development diagnostic after preflight. Commit/review the implementation first.

```bash
PYTHONPATH=src:. python -m experiments.box_gate_trace_replay \
  --development /absolute/path/to/original/development/bundle \
  --output /absolute/path/to/a/new/external/trace-directory
```

The original raw files, Git history and exact recorded runtime are required.
An implementation-only read-only check may call `_prepare(bundle, ROOT)`; this
authenticates/regenerates inputs but constructs no tracker and writes no output.
It is not an execution receipt or a new tracking result.

Tests use explicit evidence, scene and execution doubles, not actual study
replays. They exercise complete order/coverage, lineage and payload/output
forgeries, source/runtime drift, first-error preservation, interruptions,
exclusive writes, tampered-output refusal and unsupported CLI options. Separate
authored observer tests continue to check actual output/state preservation.

The complete run from `dd653aa` is retained separately from the original study.
Next choose and separately register a narrower intervention with fresh validation,
using the scoped trace findings without treating development exploration as
validation. No owner assistance was needed for the diagnostic.
