# Aspect-free motion gate — development record

Status, 2026-11-20: **development candidate, not adopted.** Every number here
comes from data this project has already used (RoundaboutHD, all four cameras,
and MOT17 val-half). It can suggest a candidate. It cannot validate one. The
deciding test is a frozen comparison on unused video (UA-DETRAC, pending the
authors' terms). The library default, `TrackerConfig`, saved traces and the
C++ parity contract are unchanged.

## Why the gate blocks vehicles

The [gate test](REAL_TRAFFIC_EVIDENCE_GATE.md) showed that switching the
Mahalanobis gate off recovers many missed line crossings. The working
explanation was speed: a gate tuned for 30 fps pedestrians rejecting fast cars
at 15 fps. A decomposition of every blocked pair contradicts that.

For each gated association, we took the pairs that passed the IoU and class
checks but failed the gate, and split the distance into its parts:

| Camera | Pairs blocked by the gate | Fail on aspect ratio | Fail on position | Would pass with aspect left out |
| --- | ---: | ---: | ---: | ---: |
| c001 | 9,118 | 94% | 16% | 84% |
| c002 | 7,290 | 95% | 16% | 86% |
| c003 | 11,518 | 86% | 37% | 69% |
| c004 | 8,791 | 88% | 25% | 76% |

The median blocked pair changes aspect ratio by about 0.45 against a fixed
aspect noise of 0.1. Its position error is ordinary: a median of 1.3–2.9
against a 2-D limit of 6.0. The filter's aspect noise is an absolute 0.1, about
25% of an upright pedestrian's aspect (about 0.4) but only about 5% of a
car's (about 2). A turning vehicle changes shape faster than that. **The main
cause is shape change, not speed.**

## Candidate

`experiments/aspect_gate.py` keeps the same Kalman filter and computes the gate
on centre and height only (3 degrees of freedom, 95% limit 7.8147). Aspect ratio
still updates the filter and still enters IoU. It just stops vetoing a match on
its own. Tests: `tests/test_aspect_gate.py`.

A second idea was tried in a scratch run and dropped: aspect noise proportional
to the aspect ratio, which changes the filter as well as the gate. It recovered
fewer crossings (309 vs 316 pooled) and is harder to explain.

## Development results

RoundaboutHD, full 9,000 frames per camera, the counting lines already fixed
for the threshold and gate tests (361 reference crossings):

| Variant | Correct counts | False counts | Missed | Public IDs |
| --- | ---: | ---: | ---: | ---: |
| Gate on (default) | 226 | 5 | 135 | 4,564 |
| Gate off | 333 | 9 | 28 | 2,031 |
| Aspect-free gate | 316 | 5 | 45 | 2,457 |

The aspect-free gate recovers 90 of the 107 crossings that switching the gate
off recovers, with no increase in false counts (5 vs 9). Most of the remaining
gap is on c002 (94 vs 110), where position failures are the blocked minority.

MOT17 val-half, FRCNN public detections, mean over the seven videos, to check
the pedestrian setting the default was tuned for:

| Variant | HOTA | IDF1 | MOTA | ID switches (sum) |
| --- | ---: | ---: | ---: | ---: |
| Gate on (default) | 47.78 | 56.63 | 49.17 | 190 |
| Gate off | 47.97 | 56.98 | 49.25 | 185 |
| Aspect-free gate | 47.96 | 56.79 | 49.14 | 196 |

On pedestrians, both changes are within noise of the default.

Runner: `python -m experiments.aspect_gate_dev --roundabout <root> --output
<json>`. The result JSON stays owner-local with the dataset.

## What this does not show

- It does not show that either change is better on unseen traffic. The
  cameras, lines and candidate were all chosen after seeing this data.
- It does not fix the counter's double counting when a track jitters across the
  line (the c003 failure in the gate test). That is a counting-rule question,
  kept separate.
- It does not justify a default change, a release or a C++ port.

## Next: the frozen test on unused video

The rules are now fixed in writing, before any download: the
[UA-DETRAC test protocol](UA_DETRAC_TEST_PROTOCOL.md) sets the sequences,
counting lines, reference-crossing rule and decision rule. When the terms
allow use, it compares three variants on identical supplied detections: gate
on, gate off and aspect-free gate. Only a candidate that passes there moves toward a
default change. Only then does C++ get a synchronisation milestone.
