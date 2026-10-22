# Held-out harness and input freeze

## What this step means

We have development results for three toy paths. Before evaluating three
different paths, we lock the **whole evaluation setup**: code, configuration,
tests, dependency-version metadata and every planned input fingerprint. This
helps prevent accidental changes after seeing the next results. It does not
make the scenes representative of real traffic or prove a new tracker is better.

Preparation generates geometry only. It **does not run held-out tracking**.
The [original v1 recipe](TRAFFIC_RELIABILITY_PROTOCOL.md), primary bottom-centre
crossing measure, secondary centre diagnostic and 37 report endpoints are
unchanged. No intervention, tuning or practical acceptance margin is introduced.
The unchanged NumPy package remains pinned to `16c287a`.

## What is locked

The experiment-only `experiments.traffic_holdout` module separates three actions:

- `prepare`: independently check all 124 non-manifest development evidence
  files and its indexed manifest; verify committed code/tests and pinned package;
  generate all 120 held-out **input manifests** and save `freeze.json` externally.
- `verify`: regenerate input fingerprints and check the saved freeze against
  the committed harness, baseline and Python/NumPy/OS/architecture/byte-order
  metadata. No tracker construction or result files.
- `run`: explicitly open the complete registered held-out grid through that
  freeze, saving all records, a flushed attempt ledger and the same paired
  absolute/difference/interaction summaries. No scenario, seed, configuration,
  filtering, resume or retry option is provided.

The held-out paths are `offcentre`, `close_opposing` and `slanted`, with seeds
1001–1010 and all four frozen conditions: 120 cases, **not 120 independent
camera sites**. Public development commands continue to reject held-out inputs.
Only private shared adapters implement common scoring/replay mechanics; this
separation is an accidental-misuse guard, not a sandbox against editing Python.

The freeze binds all `traffic_*.py` implementation files, `test_traffic*.py`
tests, package settings, protocol/lock files, the development evidence index,
baseline source files and runtime metadata. Later descendant commits may add
documentation or a freeze evidence index, but cannot alter those bound files.
The execution records both the frozen harness revision and actual run revision.
Hashes detect drift; they do not authenticate an outside party or establish
scientific validity. Version metadata is not a complete native BLAS/runtime
lock or a cross-environment bit-parity guarantee; exact input regeneration must
also pass. No public uploads, model downloads, footage or volunteers are needed.

## Commands — preparation is separate from opening

Run from a clean, committed local checkout. Add `PYTHONPATH=src` if needed.
Use new external directories whose parents already exist; nothing is overwritten.

```sh
python -m experiments.traffic_holdout prepare \
  --development-bundle /absolute/retained/development-bundle \
  --output /absolute/new/heldout-freeze
python -m experiments.traffic_holdout verify \
  --freeze /absolute/new/heldout-freeze/freeze.json
```

These two commands do **not** open held-out tracker outcomes. The original
development bundle remains read-only; its indexed bytes must still match.
An actual freeze must be generated only **after** committing the tested harness;
having the preparation command implemented is not itself a completed freeze.

The following is a **later, explicit experiment**, not part of preparation:

```sh
python -m experiments.traffic_holdout run \
  --freeze /absolute/new/heldout-freeze/freeze.json \
  --output /absolute/new/heldout-results
```

Before the first tracker call, an exclusive `opening.json` is written beside
the original external freeze. A failed or interrupted attempt consumes that
opening too; the program will not retry it under another output name. The
result plan/manifest bind the freeze digest. Reset/fresh replay remains three
passes per case as specified: it checks reproducibility and is not selective
rerunning. The first error stops the grid, retains prior results and records
unattempted cases; there is no complete summary for an incomplete grid.
A crash can leave only a plan/claim/partial ledger: that is not a completed run.
Once dispatch is attempted, conservatively treat the held-out set as opened.

The local claim is **not** a global tamper-proof registry: copying a freeze,
deleting the claim, re-preparing or manually calling a private adapter could
circumvent it. Those actions do not restore untouched evidence and must never
be used to disguise an earlier opening. If a genuine specification defect is
found, preserve the failed evidence, stop and document a versioned amendment;
do not silently refresh v1 hashes or tune against this set. A proposed fix
requires a separate registration, practical margins and new untouched scenarios.

## Verification and next milestone

Prepared and read-only verified on 2026-10-22 from committed harness
`fe88a169a5c86b7f80400fa8f6f605f4d1802d02`. All 120 held-out input
manifests are frozen, binding 19 harness/test/settings files and 57 baseline
files. Freeze content SHA-256:
`2c6a56b0ecb91d95820f52c67a921d58572fe2c7f8159a287c47e875485ac1a5`.
The machine-readable record is
[`experiments/traffic_heldout_v1_freeze_evidence.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_heldout_v1_freeze_evidence.json).
The full freeze stays in the local external research folder, outside Git.
No opening claim or held-out tracking output exists at this milestone.

Verification: 1,086 tests passed (one slow test deselected), Ruff lint/changed-file
format and strict docs build passed. A separate 12-case development regression
check (seed 101, three paths × four conditions) matched the retained input,
output, crossing and diagnostic canonical bytes and all 37 endpoints exactly.
The whole production package and parity fixtures remain unchanged.

Tests of held-out export use deliberately **fake outcomes**, not an actual
held-out tracker run. They check all-case enforcement, missing-value propagation,
checksum verification, clean/committed-source and environment gates, recorded
failures, no overwrite and consumed-opening rejection. Existing development
replay/scorer tests continue to exercise the real unchanged baseline.

With the committed freeze now recorded and verified, the next step is one
complete held-out run, followed by a combined development/held-out interpretation
that retains negative and mixed findings. Completing a synthetic grid is not
real-data validation, an automatic product feature, an upstream contribution
or a reason to port new behavior to C++. RQ5/volunteer recording is separate.
