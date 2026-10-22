# Crossing-event scorer — fixture milestone

Completed 2026-10-22. The directed crossing rules in the
[frozen v1 protocol](TRAFFIC_RELIABILITY_PROTOCOL.md) now have an implementation
and hand-checked fixture tests. **These are scorer correctness checks, not
tracker outcomes, traffic accuracy results or a completed traffic-flow study.**
The frozen recipe and its SHA-256 lock remain unchanged.

## What it does in plain language

Imagine drawing a line across the floor. We know when a reference object should
cross it. Later, we will ask the tracker when it believes an object crossed.
This scorer compares those two event lists and keeps several errors separate:

- **Miss:** an expected crossing has no eligible predicted event.
- **Extra:** a predicted crossing has no eligible expected event. Two different
  tracking IDs crossing for one reference object can create an extra.
- **Timing/position error:** a matched event happened at a different time or
  position along the line.
- **Wrong counting window:** a matched event belongs to a different time window.
- **Window-count error:** absolute differences in each direction/time-window
  count, added together instead of allowing signed totals to cancel.

For example, a true crossing at frame 29.9 and a prediction at frame 30.0 can
match under the frozen tolerance, yet fall in different windows. The scorer
reports zero missed/extra events, one matched wrong-window event, and a window
count error of two: one missing in the earlier window and one extra in the next.
If two objects swap windows, aggregate counts can even stay correct while both
matched events are mistimed. That is why no single count summarizes everything.

## Rules implemented without changing the protocol

`extract_crossings` consumes world-coordinate anchor samples, each with an
integer frame and a local tracking/reference ID. It sorts inputs and rejects
duplicate frame/ID records. It does not fill missing frames or join different
IDs. Only adjacent-frame samples can establish a crossing.

An arrival at Y=10 counts; starting or dwelling on the line does not. The first
eligible crossing per ID and direction is retained. Time and X are interpolated
without rounding or an added epsilon; only crossing X in `[-6,6)` is accepted.
Anchors themselves can be outside the ROI: they are not clamped into a crossing.

`score_crossings` matches events one-to-one using the frozen direction, time
and position gates: same direction, time error at most 30 frames, X error at
most one toy world unit. These are synthetic protocol choices, not validated
operational tolerances. Reference IDs need not equal predicted tracking IDs.

The matching priorities are exact and ordered:

1. Match as many eligible events as possible.
2. Minimize total absolute frame-time error.
3. Minimize total absolute X error.
4. Break exact ties by lexicographically sorted reference/prediction ID pairs.

This is not greedy matching or an approximation that mixes priorities using
arbitrary weights. All event arithmetic uses float64-compatible Python floats.
Windows are half-open, 30 frames wide; exact boundaries belong to the later
window. Positive and negative directions have separate counts.

The result includes all input events, explicit matches, unmatched events,
per-match errors/windows, ten window counts per direction, summaries, frozen
rule values and protocol hashes. Timing/position means are `null` if nothing
matches; recall is `null` if there are no reference events. Invalid/nonfinite
data fail rather than becoming flattering zero-error scores.

## Deliberately bounded scope

The six registered paths have at most two true crossings per run. The scorer
therefore uses exact exhaustive assignment for **at most two truth events**,
with a capacity of 1,200 predicted events. Extraction accepts at most 100,000
samples. Over-capacity inputs are rejected, never silently truncated. These are
implementation safety limits, not additional study observations or a claim
that this matcher scales to unrestricted traffic datasets.

The scorer checks the frozen artifact integrity before extraction or scoring.
It writes no results, invokes no tracker/RNG/detector, and imports no footage.
It is experiment code, not a new public package API or production counting SDK:

- [`experiments/traffic_crossing.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/traffic_crossing.py)
- [`tests/test_traffic_crossing.py`](https://github.com/hulagerushikesh/visiontrack/blob/main/tests/test_traffic_crossing.py)

Run the hand-checked fixtures from a local repository root:

```sh
python -m pytest tests/test_traffic_crossing.py
```

Coverage includes perfect, duplicate, missing, fragmented, reverse-direction,
boundary, dwelling, gapped, wrong-window, spatially ineligible and ambiguous
matching examples, all four matching priorities, invalid inputs and capacity
limits. A test prevents tracker or scene-generator execution in these fixtures.

## Next implementation step

The [development-only runner](TRAFFIC_RELIABILITY_RUNNER.md) now connects the
verified inputs to the pinned baseline and this scorer. Source/configuration
verification, reference-free detector inputs, reset/fresh replay checks and
in-memory provenance are implemented. Full tracking/localization diagnostics,
result exports and paired development summaries remain next.

Only after those checks pass do we freeze the complete harness revision and
input digests, followed by the one-pass held-out tracker evaluation. No new
algorithm, tuning, real-data conclusion, origin/destination flow validation or
C++ change is completed by this scorer milestone. No owner action is needed yet.
