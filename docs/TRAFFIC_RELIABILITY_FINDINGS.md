# Traffic mechanism v1 — development and held-out findings

Completed 2026-10-22: **120 development + 120 held-out cases**, with no failed,
skipped or unattempted case in either grid. This closes the scoped synthetic
characterization and its interpretation, **not** real-traffic validation or a
claim that we have improved the tracker. The baseline, configuration, protocol,
public API and C++ implementation were not changed.

## The result in plain language

Imagine a person walking smoothly through a counting line. The detector's box
can nevertheless shrink or jump. Our unchanged tracker can see most of that
journey yet fail to produce the continuous, same-ID crossing needed to count it.
That failure occurs in these intentionally perturbed toy scenes.

- **Box instability matters here.** Both conditions with imposed box errors
  miss every primary bottom-centre crossing, in development and held-out paths.
- **Perspective alone does not worsen the primary count or ID-switch results
  here.** Keep this negative finding: this experiment does not demonstrate a
  counting benefit for geometry-aware tracking. Localization does change.
- **Combining the factors is not uniformly worse.** Some ID-switch contrasts
  improve slightly, while misses/FP can increase; one metric is not a winner.
- **High frame coverage is not enough.** Roughly 97% mean completeness under box
  errors can coexist with missing the critical crossing. Operational event
  errors and trajectory diagnostics answer different questions.

These are controlled observations about this model, not statements about all
cameras, detectors, pedestrians or traffic systems. The fixed severe error
pulse overlaps the crossing period; the recipe intentionally probes that
failure, rather than estimating how often it happens in practice.

## What was evaluated, and when

The [v1 protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) fixed six paths, split into
three development and three held-out scenarios, ten noise seeds per scenario,
and four conditions. Each run has 300 frames and three reset/fresh-instance
passes. The ten seeds repeat measurement noise; they are **not ten camera sites**.

Development ran from `19a7c821ea4b8d1f54d0ffc0450beb9391b38e1e`.
The [whole held-out harness and all input fingerprints](TRAFFIC_RELIABILITY_HOLDOUT.md)
were frozen at `fe88a169a5c86b7f80400fa8f6f605f4d1802d02` before opening outcomes.
The single held-out export then ran from the documentation-only descendant
`5ac67f230ea67fc600f8ce446d996e685af80c69`, consuming its original opening claim.
There was no held-out tuning, intervention, seed selection or selective rerun.

All runs use the unchanged package at
`16c287a6b18c5c142a28e4bce70b3232946459db`. The runtime was Python 3.12.9,
NumPy 2.3.1, Darwin arm64, little endian; this is not a universal numerical
bit-parity or native-library compatibility claim.

## All held-out primary results

Values are **means over ten noise seeds**; ID-switch brackets give min/max,
not confidence intervals. Conditions use paired latent paths and random draws.
The [development tables](TRAFFIC_RELIABILITY_DEVELOPMENT.md) remain separate:
we do not pool different paths into an independent-site estimate.

| Path | Condition | Primary crossing misses + extras | ID switches, mean [range] | Missed object-frames, mean | False-positive rows, mean | Completeness, mean |
| --- | --- | --- | --- | --- | --- | --- |
| offcentre | control | 0 | 0 [0, 0] | 2 | 0 | 0.993333 |
| offcentre | perspective_only | 0 | 0 [0, 0] | 2 | 0 | 0.993333 |
| offcentre | box_error_only | 1 | 3.6 [3, 4] | 8 | 1.2 | 0.973333 |
| offcentre | combined | 1 | 3.6 [3, 4] | 8 | 1.2 | 0.973333 |
| close_opposing | control | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| close_opposing | perspective_only | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| close_opposing | box_error_only | 2 | 7.3 [6, 8] | 16 | 2.6 | 0.973333 |
| close_opposing | combined | 2 | 7.3 [6, 8] | 16.1 | 2.7 | 0.973167 |
| slanted | control | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| slanted | perspective_only | 0 | 0 [0, 0] | 4 | 0 | 0.993333 |
| slanted | box_error_only | 2 | 7.3 [6, 8] | 16 | 2.6 | 0.973333 |
| slanted | combined | 2 | 7.2 [6, 8] | 16.6 | 3 | 0.972333 |

The primary event-error and absolute window-count-error values coincide in
these runs. Bottom-centre recall is 1 for every control/perspective-only run
and 0 for every box-error/combined run. Missing crossings make matched timing
and crossing-position errors **undefined**, not zero. Initial confirmation
accounts for two control missed object-frames per object.

The count-error interaction is zero in every seed of every held-out path.
Interaction is `combined - perspective_only - box_error_only + control`, not
a comparison against an improved algorithm. Selected tracking interactions:

| Held-out path | ID switches, mean [range] | Missed object-frames, mean [range] | FP rows, mean [range] | Completeness, mean |
| --- | --- | --- | --- | --- |
| offcentre | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 |
| close_opposing | 0 [-1, 1] | 0.1 [-5, 6] | 0.1 [-3, 4] | -0.000167 |
| slanted | -0.1 [-1, 0] | 0.6 [0, 6] | 0.4 [0, 4] | -0.001000 |

The two-object development ID-switch interaction was -0.2 on each path;
held-out values are 0 and -0.1, with mixed per-seed behavior in close_opposing.
This is descriptive, not a significance claim or a general combined-factor law.

## Position errors and the secondary anchor do not pick a winner

For held-out `offcentre`, mean matched bottom-contact error is approximately
0.000199 toy units in control, 0.001058 with perspective alone, 0.408418 with
box errors, and 0.333514 with both. These are not surveyed metres. Matched-track
means exclude missed object-frames and must be read alongside sample counts
and completeness. Smaller conditional error is not evidence of better counts.

The box-centre secondary event errors are 2, 2, 3.4, 1 for offcentre;
4, 4, 5.3, 3.3 for close_opposing; and 4, 4, 4.2, 4.2 for slanted, in condition
order control, perspective_only, box_error_only, combined. Box-centre is not
the true ground contact in this model. Some smaller secondary errors do not
authorize replacing the primary anchor after inspecting results.

## Evidence and independent checks

The machine-readable held-out index is
[`experiments/traffic_heldout_v1_evidence.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_heldout_v1_evidence.json).
Raw bundles, the original freeze and its consumed opening claim remain in the
external local research folder, outside Git. They contain generated geometry
and tracking evidence, not footage or persistent person identities.

After execution, a separate read-only calculation checked **both** bundles:
all 124 non-manifest file digests per bundle, the manifest self-excluding
digest, exact 120-case coverage, all 240 ordered ledger entries, every record
and output digest, configuration and three-pass replay evidence. The held-out
inputs, environment, baseline and frozen-source hashes match the original
freeze. All 37 endpoints, paired differences, interactions and descriptive
aggregates were independently reconstructed from saved records, including null
propagation: 8,880 per-seed values and 888 aggregated endpoints per split.
These checks establish consistency/integrity, not independent scientific truth.

Historical bundles and the freeze index are not rewritten. Their
`complete_study_report: false` remains accurate for a full research study:
no intervention benefit or real-data transfer has been evaluated. This page
completes only the scoped synthetic v1 interpretation.

## Next gates — not more tuning on this held-out set

1. **Design a separate minimal intervention study**, before implementation:
   choose one question, a fixed comparator and practical success/failure
   margins; register new untouched scenarios/seeds. Explicitly separate
   continuity/association errors from counting-anchor behavior. Do not assume
   that geometry-aware motion, a different anchor or a longer track lifetime
   fixes the observed failures. The opened v1 set is now characterization
   evidence, not a reusable untouched acceptance set.
2. **Admit representative real evidence separately**: permission/license,
   fixed-camera domain, detector version, privacy conditions, labels and
   crossing/flow truth. A single line crossing is not origin-to-destination
   flow validation; toy box noise is not actual blur, class variation or
   detector failure. The volunteer re-entry rehearsal is a different question.
3. **Only then consider production/C++ changes** if a useful behavior is
   accepted in Python, its API/settings and exact decision/output fixtures
   are frozen, and parity plus latency/memory tests justify a port.

No website behavior change, C++ feature, release, new outreach or third-party
performance claim follows automatically from this result. RQ5 and its
real-data admission requirements remain separate.
