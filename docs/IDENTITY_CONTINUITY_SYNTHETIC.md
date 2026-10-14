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
