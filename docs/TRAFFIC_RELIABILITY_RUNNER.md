# Development baseline runner — replay milestone

Completed 2026-10-22. The [input generator](TRAFFIC_RELIABILITY_GENERATOR.md),
unchanged NumPy tracker and [crossing scorer](TRAFFIC_RELIABILITY_SCORER.md)
are now connected in an experiment-only **development** runner. This is not
the complete traffic study, a tracker improvement or real-world validation.
The [frozen v1 protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) has not changed.

## What this means in ordinary language

Previously we had a test scene and a way to mark counting mistakes, but had not
connected them to the tracker. Now we can feed the scene's detection boxes to
the existing tracker and compare its reported crossings with the known ones.

We also repeat the same input after resetting the tracker, and with a fresh
tracker. All three output streams must be byte-identical. This checks that a
previous run does not contaminate the next one; it does not establish accuracy.
Both reported anchors use the same first output stream, not independently
tuned trackers. The two extra passes are explicit reproducibility checks.

The simple `solo / 101 / control` smoke check returned 298 rows for 300 frames:
the baseline requires three observations to confirm a track, so frames 0 and 1
have no public rows. The adapter does not invent those missing observations.
Its bottom-centre crossing matched the one true crossing, with no missed or
extra event in that toy case. The box-centre crossing fell outside the frozen
time-matching tolerance, yielding one miss and one extra. This is consistent
with a centre above the simulated ground contact, not evidence that a new
tracker or a universal bottom-centre solution has been validated. Truncation
can move bottom-centre too. Full four-condition analysis remains pending.

## Read-only development use

From the repository root, with its package installed in your Python environment:

```sh
python -m experiments.traffic_runner --scenario solo --seed 101 --condition control
```

If the checkout is not installed, prefix the command with `PYTHONPATH=src`.
Git and the locally available pinned baseline commit are required. The command
prints a compact smoke summary and writes no report, media or result files.
It does not fetch from GitHub or access a camera/network service.
There is deliberately **no `--split heldout` option**. Held-out scenarios/seeds,
unregistered selectors and configuration overrides are not accepted.

`run_development(scenario=..., seed=..., condition=...)` returns an in-memory
JSON-safe record with all public output rows and full crossing scores. This is
experiment code, not a new supported package API or a Lab `report.json` import.
The CLI's compact output is not the complete returned provenance record.

## Guards before trusting an output

- Verify the exact frozen protocol/document hashes before constructing a tracker.
- Compare all package source files with their Git blob IDs at baseline commit
  `16c287a6b18c5c142a28e4bce70b3232946459db`, before and after replay. Reject
  changed, staged, missing or extra Python source, and source-file symlinks.
  Record accepted source bytes with SHA-256. Do not trust the current branch name.
- Reject an installed wheel or another checkout shadowing package imports.
- Require the complete frozen `TrackerConfig` field set and explicit values;
  never inherit future defaults. Appearance features and camera shifts are absent.
- Supply only observed boxes, score and class to `Detection`. Reference IDs and
  true ground contacts are reserved for later scoring, never tracker inputs.
- Update exactly once per frame. Keep public output rows without truth-based
  filtering, gap filling, ID merging or hidden lifecycle changes. The current
  baseline returns confirmed, just-updated tracks, not unmatched coasted rows.
  The adapter preserves this actual behavior rather than its broader comment.
- Reject invalid, nonfinite, out-of-image or duplicate-ID public outputs. Do not
  clip or repair them. Inverse-projected valid anchors outside the ground ROI
  remain outside; only the frozen crossing gate determines whether they count.
- Require equal first/reset/fresh output bytes. A mismatch invalidates the run.

These are reproducibility/drift checks in a trusted research checkout, **not a
security sandbox** against monkeypatched Python or malicious dependencies.
Git history must be present; the test CI checkout now includes it rather than
silently skipping source verification in a shallow clone.

## Provenance and tests

The returned record identifies the protocol, truth/input and detector-input
digests (frame-ordered boxes/scores/classes, with no appearance), complete config
and digest, pinned baseline/source SHA-256s, actual HEAD and tracked dirty state,
experiment-source digests, Python/NumPy versions, OS/architecture/byte order,
public output/digest, replay checks, both crossing scores and a whole-record
digest. The input subrecord describes generator inputs only; its
`tracker_executed: false` is not the state of the surrounding replay record.
The top-level record explicitly marks `complete_study_report: false` and
`heldout_tracking_executed: false`.

Environment versions are recorded, not locked into a full environment image.
Native numerical-library/compiler differences can change low-order output bits;
the equality guarantee is within the tested runtime, not across all machines.
The smoke check is not a published benchmark result or a completed harness freeze.

Tests cover real development cases, reset/fresh determinism, source drift even
after staging, shadowed imports, held-out rejection before tracker construction,
reference-free detector inputs, public gaps, both anchor formulas, invalid
outputs, digest/JSON consistency and fail-closed reset/replay failures:

```sh
python -m pytest tests/test_traffic_runner.py
```

## What comes next

1. The existing IoU-0.5 tracking evaluator and separate contact-localization
   diagnostics are now [implemented and fixture-tested](TRAFFIC_RELIABILITY_DIAGNOSTICS.md),
   stratified by true scene region and scheduled perturbation window. The
   in-memory record includes them; matching history is not reset per stratum.
2. Reproducible result export and all four development-condition summaries,
   paired differences and the frozen interaction are now
   [complete for 120 development cases](TRAFFIC_RELIABILITY_DEVELOPMENT.md),
   including unfavorable outcomes and explicit missingness.
3. Freeze the complete harness commit and input digests **before** one-pass
   held-out tracking. This milestone does not open that evaluation or authorize
   a fix, tuning, an acceptance claim, a C++ port or a traffic-product pivot.

No owner recording or external reply is needed for these implementation steps.
RQ5 recording, dataset admission and practitioner validation remain separate.
