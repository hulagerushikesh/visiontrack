# Jitter-proof counting rule — development record

Status, 2026-11-20: **development candidate, not adopted.** Every number here
comes from RoundaboutHD, which this project has already used. It can suggest a
counting rule. It cannot validate one.

## The problem

The counter used in the RoundaboutHD tests counts every step, between two
adjacent frames, in which a track's box centre moves across the line. When a
box changes shape on the line, its centre can wobble back and forth. In the
gate test, one gate-off track on c003 crossed three times within 10 frames
(B→A, A→B, B→A). One vehicle produced three counts, two of them false, and
that single track decided the test.

## Two candidate rules

Both are in `experiments/crossing_rules.py`, with tests in
`tests/test_crossing_rules.py`. Each is applied to the reference tracks and to
the tracker output alike.

- **Cancel reversals.** A crossing followed by the same track crossing back
  within a short window cancels both. The primary window is 15 frames, one
  second at 15 fps, chosen before any run. 8 and 30 frames are reported as a
  sensitivity check. A vehicle that really goes there and back slowly is still
  counted twice.
- **Dead band (hysteresis).** A track only changes side once its centre is
  more than a set distance past the line. The count is reported at the frame
  and point of its last real crossing, so timing matches the plain counter.
  The primary band is 50 pixels on 3,840×2,160 frames, chosen before any run.
  25 and 100 pixels are reported as a sensitivity check. With a band of zero,
  it gives exactly the plain counter.

## Development results

RoundaboutHD, all four cameras, full 9,000 frames each, the counting lines
already fixed for the earlier tests. Correct / false / missed counts, pooled:

| Counting rule | Reference crossings | Gate on | Gate off | Aspect-free gate |
| --- | ---: | --- | --- | --- |
| Plain (earlier tests) | 361 | 226 / 5 / 135 | 333 / 9 / 28 | 316 / 5 / 45 |
| Cancel reversals, 15 frames | 359 | 225 / 6 / 134 | 330 / 6 / 29 | 315 / 6 / 44 |
| Dead band, 50 px | 359 | 216 / 5 / 143 | 328 / 5 / 31 | 311 / 6 / 48 |

What the numbers show:

- **The jitter is real but rare.** Cancel reversals removes 3 of gate off's 9
  false counts, including both extra counts on c003, and costs 3 correct ones.
  The reference itself loses 2 crossings on c001, where the interpolated
  labels also wobble on the line.
- **The window barely matters.** 8, 15 and 30 frames give the same totals to
  within one count.
- **The dead band costs real counts.** It loses 5–10 correct counts per
  variant, most on gate on. A track that ends or restarts inside the band never
  commits to the new side, and gate on fragments tracks the most. Wider bands
  lose more.
- **The motion-gate comparison does not change.** Under every rule, the
  aspect-free gate recovers about 90 crossings over gate on with no more false
  counts.

**Preferred candidate: cancel reversals, one second.** It removes the jitter
double counts the c003 failure exposed, it does not punish fragmented tracks,
and it needs no distance setting tied to image size.

**Post-hoc observation, not a result.** Re-scored with either rule, the
earlier gate test (gate on versus off, c001, c003 and c004) would pass its own
decision rule, because the c003 jitter counts disappear. That test was frozen
with the plain counter and stays **not supported**. Changing the counter after
seeing a result cannot change a verdict.

Runner: `python -m experiments.counting_rule_dev --roundabout <root> --cache
<dir> --output <json>`. The result JSON and tracker-output cache stay
owner-local with the dataset.

## What this does not show

- It does not show the rule is right on other video. The cameras and lines
  were seen before the rule was written.
- It does not change any earlier verdict, any library code, or C++.
- On 2026-11-20, before any download, the owner chose this rule for the
  [UA-DETRAC protocol](UA_DETRAC_TEST_PROTOCOL.md): a dated amendment with a
  25-frame window (one second at 25 fps). That test, not this record, decides
  whether the rule holds on unused video.
