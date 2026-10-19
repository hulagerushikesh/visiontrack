# RQ5 synthetic stress probe — first result

Run date: 2026-10-14. Protocol: [RQ5 first experiment](IDENTITY_CONTINUITY_PROTOCOL.md).
This is a **dataset-free evaluator and policy stress test**, not evidence that
the system can recognize or safely reconnect real people. The ordinary
VisionTrack tracker and its public outputs are unchanged.

## Fixed setup

The probe uses 64-dimensional random unit vectors and a fixed gallery per
partition. About 55% of events are eligible returns, 10% are returns whose
true identity is unavailable, and 35% are new arrivals. Some gallery vectors
share a nearby base to create ambiguous pairs. Query noise has two levels.
Development and held-out partitions use different seeds and independently
generated galleries. Each has 3,000 events. Exact cosine search is used; no
approximate index or learned model is involved.

For each gallery size, the threshold-only and threshold-plus-margin rules are
selected on development events using the registered 1% synthetic
false-restoration upper bound. Only after selection are they scored on the
held-out events. Abstain-all and forced-nearest are fixed baselines. The
one-sided Wilson bound here describes independent synthetic events; it is
not the real-video grouped uncertainty method in the protocol.

## Held-out results

| Gallery | Rule | Eligible recall | False / attempted restores | Upper 95% false-restoration risk |
|---:|---|---:|---:|---:|
| 10 | forced nearest | 98.9% | 1,369 / 3,000 | 47.1% |
| 10 | threshold only | 75.7% | 0 / 1,249 | 0.22% |
| 10 | threshold + margin | 84.9% | 4 / 1,404 | 0.63% |
| 100 | forced nearest | 94.6% | 1,466 / 3,000 | 50.4% |
| 100 | threshold only | 76.3% | 0 / 1,237 | 0.22% |
| 100 | threshold + margin | 76.3% | 0 / 1,237 | 0.22% |
| 1,000 | forced nearest | 88.2% | 1,541 / 3,000 | 52.9% |
| 1,000 | threshold only | 71.8% | 0 / 1,188 | 0.23% |
| 1,000 | threshold + margin | 73.6% | 8 / 1,225 | **1.16%** |
| 10,000 | forced nearest | 80.8% | 1,693 / 3,000 | 57.9% |
| 10,000 | threshold only | 73.0% | 0 / 1,180 | 0.23% |
| 10,000 | threshold + margin | 72.9% | 1 / 1,179 | 0.38% |

The abstain-all baseline makes zero false restorations and zero correct
restorations at every size; its selective risk is **undefined**, not 0%.

The margin intervention helps at gallery size 10, ties at 100, misses the
pre-registered held-out risk bound at 1,000, and slightly hurts eligible recall
at 10,000. This refutes any simple claim that adding a margin always improves
the risk/recall tradeoff. The forced-nearest rule restores every event, so all
genuinely new arrivals are falsely linked in this deliberately open-set setup.

## What this result can and cannot support

This probe demonstrates that the event taxonomy, open-set baselines,
development/test separation, and explicit abstention can be run at the planned
gallery sizes. It also exposes a transfer failure that an average-only metric
would hide. It cannot estimate real ReID accuracy: its vectors have no camera,
clothing, occlusion, annotation, or detector distribution. Gallery size here
is a candidate-count stress variable; the probe does not measure long-term
storage or retrieval latency.

The next experiment needs lawful, identity-annotated video, a frozen detector
and crop path, held-out identities and recordings, grouped uncertainty, and
predefined memory expiry. Until those exist, RQ5 remains a hypothesis and
VisionTrack C++ has no new identity behavior to port.

## Reproduce

From the VisionTrack checkout, with NumPy installed:

```bash
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 10 --events 3000
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 100 --events 3000
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 1000 --events 3000
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 10000 --events 3000
```

The seed defaults to 7 and the JSON output carries every count, rate,
selected development parameter, and held-out result. No data is downloaded
or written. The probe retains only the two highest candidate scores for each
event, so a 10,000-candidate run does not retain a full score matrix.

## Full fixed-grid trade-offs

Added 2026-10-19: the optional `--include-curves` export closes the protocol's
trade-off reporting gap. It does **not** introduce a new identity policy,
change the original calibration grid, or modify the live tracker. Without the
flag, the original report structure and numerical results are preserved.

```bash
PYTHONPATH=src python -m experiments.reentry_stress --gallery-size 1000 --events 3000 --seed 7 --include-curves
```

The command prints JSON to standard output and does not save files. Its
`operating_curves` section has `schema_version: 1` and two policy families:

- `threshold_only`: all 10 original thresholds with margin zero.
- `threshold_and_margin`: all 60 pairs from those same thresholds and the six
  original margins. The ten margin-zero pairs also appear in the first family;
  they are not extra events or independent experiments.

Thresholds remain `[0, .2, .3, .4, .5, .6, .7, .8, .9, 1]`; margins remain
`[0, .03, .06, .10, .15, .20]`. A point restores the best candidate only when
both its similarity and its best-versus-runner-up gap reach their thresholds
(inclusive comparisons). Every point carries:

- `threshold`, `margin`, and `selected_on_development`.
- Separate `development` and `held_out` metrics on the same respective events
  used by the original probe, with all existing raw counts and rates.
- An explicit `attempted_restorations` count, the denominator of selective risk,
  alongside the eligible-return denominator and the independent-synthetic
  one-sided Wilson bound.

No point is dropped, ranked, interpolated, or chosen using held-out results.
The existing development-only calibration runs first. Exactly its chosen pair
is marked in each family, or no pair is marked when development evidence is
insufficient. Fixed abstain-all and forced-nearest results remain in
`fixed_baselines` outside the grid. The margin grid is a family of curves, not
a single ordering in which every point must be better than the previous one.

### How to read the trade-off

Coverage asks **how often we attempted a link**. Eligible recall asks **how
many available true returns we restored correctly**. Selective risk asks
**what fraction of attempted links were incorrect**. They have different
denominators and must be read together. Lower coverage is not proof of lower
risk, and abstaining on everything is not useful recovery.

Tightening one gate while holding the other fixed can only remove attempts,
but may remove correct links disproportionately. Therefore the *rate* of
incorrect links among the remaining attempts can increase even while the
absolute false-link count falls. `null` means an absent denominator, not zero
risk. A zero-error point still has a nonzero Wilson upper bound when it has
attempts; too few attempts cannot establish the registered risk budget.

These are descriptive grid results, not confidence bounds for an adaptively
chosen test-set winner, significance tests, or real-video guarantees. Do not
retune from the held-out curve and call the resulting policy held-out validated.
A follow-up policy needs a new registered study and untouched evaluation data.
The synthetic unavailable-return group models absence from the gallery; it
does not execute or validate a real expiry/eviction mechanism.

### Verification and current conclusion

The 2026-10-19 reproduction used seed 7 and 3,000 events per partition at gallery
sizes 10, 100, 1,000, and 10,000. For all four sizes, the original report
(including selected parameters, baselines, counts, and rates) exactly matched
the pre-export implementation. The newly marked curve points matched those
selected held-out metrics. In particular, the 1,000-candidate margin rule still
made **8 false links among 1,225 attempts**, with a one-sided synthetic upper
bound of **1.16%**: it still fails the primary 1% operating point. No test-set
alternative has replaced it.

Tests cover hand-scored eligible, novel, and unavailable returns; empty and
no-attempt denominators; gate/count monotonicity without assuming monotone
risk; deterministic output; unchanged default output; and a held-out truth
perturbation that cannot change development selection. Ordinary CI runs these
tests. This closes a **synthetic reporting** gap only: lawful real-video data,
frozen splits and preprocessing, grouped uncertainty, and the product/C++
handoff gates remain unfinished.
