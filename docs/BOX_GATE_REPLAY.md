# Box-gate ablation — development replay adapter

Implementation milestone, 2026-10-23. The adapter now connects the
[registered paired inputs](BOX_GATE_INPUTS.md), the existing tracker API and
the [reference scorer](BOX_GATE_SCORING.md). **This milestone uses test doubles;
no new actual-tracker ablation results or held-out outcomes have been generated.**

## What this step does

The input generator supplies the same imperfect rectangles to two versions:

- Baseline: the full registered configuration.
- Candidate: that configuration with only `use_mahalanobis_gating=false`.

`experiments/box_gate_runner.py` provides one development-pair function,
`run_development(scenario=..., seed=..., condition=...)`. It has no arbitrary
configuration, variant or split override, no CLI and no file writes. The
[development exporter](BOX_GATE_REPORT.md) enforces a committed clean harness
before comparisons. A private development-only sink emits immutable bytes for
each finished variant, so the exporter can preserve a baseline before attempting
the candidate; it does not expose mutable tracker/scorer state.

For each version the adapter performs three passes in registered order:

1. A fresh tracker instance.
2. The same instance after its public `reset()`.
3. An independent fresh tracker and configuration.

It rejects shared instances/configurations, wrong starting frame, skipped frame
advancement, changed configuration, invalid output rows and reset/fresh output
differences. Each frame passes only `Detection(xyxy, score, class_id, feature=None)`:
reference identities, contacts, projection matrices and scoring state never go
into the tracker. Writable box copies prevent one pass from changing another's
immutable input.

The actual detection payload is fingerprinted **before** each update, including
the boxes as constructed by `Detection`. All six pass receipts must reproduce
the same input manifest. A changed constructor payload cannot quietly acquire
the fingerprint of the intended inputs.

Each variant retains its exact configuration, output rows/digest, three-pass
receipts and full scorer record. The pair includes all 37 candidate-minus-baseline
differences, with null propagated rather than filled with zero, plus protocol,
input, baseline-source, local revision, harness hashes and runtime metadata.
Source/input/protocol drift is checked at completion. A pair record does not
choose a winner or satisfy the complete study's acceptance rules.

The source snapshot records dirty local state instead of implying that this
adapter is already a frozen experiment harness. It is workflow provenance,
not protection against a malicious or monkeypatched runtime. The later freeze
must bind the full reviewed harness, tests and environment.

## What was verified

**49 adapter tests** forbid constructing the real tracker. Explicit test doubles
echo supplied rectangles under local IDs; that is deliberate test behavior,
not a tracking algorithm or a research result.

Tests exercise all three development paths and all four conditions, checking
all 300 frame payloads in every pass, exact configuration isolation and the
scorer/output lineage. Fault injection covers broken resets, differing fresh
outputs, reused instances/configurations, malformed observations, detection
box/metadata changes, input forgery, source/import/protocol drift and invalid
selectors. Mutation tests confirm that writable detection copies cannot alter
the next pass's input. The real factory's explicit configuration construction
is checked with its final tracker constructor replaced by an inspection double.

Run from the repository root:

```bash
python -m pytest tests/test_box_gate_runner.py
```

Actual baseline/candidate numerical behavior, real reset/fresh parity on these
new cases, usefulness and performance remain to be measured by the committed
complete experiment. No production tracker, website behavior, old traffic-study
artifact, registered acceptance margin or C++ behavior changes here.

## Next

The [paired-grid exporter and numerical rules](BOX_GATE_REPORT.md) are now
implemented/tested with hand-worked tables and explicit doubles. Next, run and
independently audit the 120 development pairs from the committed harness
(240 variant runs, 720 passes). After retaining
development results without tuning, freeze a separate new held-out gate and open
it once. Preserve failure and no-effect outcomes as faithfully as benefits.

See the [two-project progress overview](PROGRESS_OVERVIEW.md) for the wider plan.
