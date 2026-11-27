# GRAM-RTM motion-gate test — frozen protocol

**Frozen 2026-11-20, before any GRAM-RTM image is viewed, any detector or
tracker runs on it, or any counting line touches its labels.** This is the
backup for the [UA-DETRAC test](UA_DETRAC_TEST_PROTOCOL.md). It shares that
test's question, variants and counter. Only the dataset-specific parts below
differ. Any later change must be a dated amendment written before the first
detector run. After that run, no rule may change.

So far the [intake](GRAM_RTM_INTAKE.md) has opened only the label kit, for
completeness counts, and the archive lists of the images.

## Data

- **Sequences:** M-30 (7,520 frames, 800×480) and M-30-HD (9,390 frames,
  1200×720), all frames, both 30 fps. Their images are CC BY 3.0, recorded by
  the dataset authors. Urban1 is excluded until the authors confirm its image
  rights. If it is later admitted, it gets its own dated amendment before use.
  *2026-11-27: admitted under its own
  [Urban1 protocol](GRAM_RTM_URBAN1_TEST_PROTOCOL.md); this result is
  unchanged.*
- **Reference:** every labelled vehicle (car, van, truck, big truck,
  motorbike), using the box centre.
- **Frame alignment:** label file *k* is expected to belong to image *k*+1.
  Before any detector run, this is checked against the authors' own 2013
  detections, which are numbered from 1. On 200 evenly spaced frames, take the
  mean best-overlap between label boxes and those detections at offsets −1, 0,
  +1 and +2. The offset with the highest mean is used. If it is not +1, record
  that here before going on. No tracker or counting is involved.

  **Result and amendment, 2026-11-20, before the full detector run.**
  M-30-HD: +1 is best (0.515, against 0.498 at 0 and 0.497 at +2). M-30 is
  a near tie: +2 scores 0.311 and +1 scores 0.306. The 2013 detections find
  only about half the vehicles, so this check is weak. It is repeated with the
  pinned detector on the 20 timing frames per sequence. That repeat decides
  the offset for each sequence. If it does not clearly favour one offset (a
  lead under 0.01), +1 is kept, as both the numbering and M-30-HD indicate.

  **Repeat with the pinned detector: +1 on both sequences, clearly.** The
  mean best overlap at offsets −1 / 0 / +1 / +2 was 0.663 / 0.753 / **0.808**
  / 0.711 on M-30 and 0.732 / 0.825 / **0.874** / 0.804 on M-30-HD. Label
  file *k* belongs to image *k*+1. The same run measured **0.91–0.94 seconds
  per frame**, so the full detector run is about **1.9 hours for M-30 and
  2.4 hours for M-30-HD**.
- **Exclusion regions:** the kit marks areas where vehicles were not labelled
  (`ROI/M-30-map.jpg`, `ROI/M-30-HD-map.jpg`). A crossing whose point lies in
  an excluded area is dropped from both the reference and every variant. The
  map is read as excluded wherever its pixel is dark (grey value below 128),
  scaled to the frame size. Detections are not filtered. The M-30 map was
  viewed after freezing, to confirm this reading. It is a black-and-white mask
  whose black part covers the top band and the upper-left corner, the far end
  of the road, which fits "dark = not labelled". On M-30 the half-height line
  loses about its leftmost 130 pixels to that region.

## Detector

The supplied 2013 detections fail the 0-to-1 score rule, so one pinned
detector is run instead:

- local YOLOX-X ONNX file, SHA-256
  `c892d7aaf1c4746d8a4d675bec669a4db4f434b4ee1efb654bc9b353379c7c55`, the
  same file used in the SVMOT screens;
- 640-pixel input. **Amendment, 2026-11-20, before any detector run:** the
  `upstream` preprocessing needs OpenCV, which is not installed. The run uses
  the library's `legacy` resize instead, given frames in BGR order, which is
  the colour order YOLOX was trained on. Nothing was installed for this test.
- confidence floor 0.10, so the tracker's low-score recovery stage gets its
  inputs; NMS IoU 0.45;
- COCO classes car (2), motorcycle (3), bus (5) and truck (7), each kept as
  its own class.

Detections are computed once per sequence, saved with a hash, and replayed
identically into every variant. The run is moderate laptop load and needs the
owner's approval first. A 20-frame timing is measured and reported before the
full run.

**Run note, 2026-11-21. No rule changes.** The first full M-30 detector run
was stopped by the owner after 2 hours 38 minutes, past the 2.5-hour limit set
for it. It saved nothing, because the detections were written only at the end.
No detection, tracker output or crossing from it exists or was seen. The
20-frame timing had missed the slowdown a fanless laptop shows under long
load. From now on the detector saves a part every 500 frames, resumes from the
last saved part, and runs in owner-approved sessions of at most 40 minutes.
The detector, its settings and the frames are unchanged. Parts are joined in
frame order into the same single detections file and receipt as before.

**M-30 detections complete, 2026-11-21.** Four approved sessions of 47, 42,
48 and 9 minutes saved all 16 parts. The joined file has **107,842
detections** on all 7,520 frames, in frame order, with scores from 0.10 to
0.95: 97,764 car, 8,170 truck, 1,001 bus and 907 motorcycle. Its SHA-256 is
`e62d4f3e2315c1253c3b8769c80fd10e1052bce14e1447f3b2160131e8616355`. The
image archive hash in the receipt matches the intake receipt. No tracker has
run on these detections, and no label has been used for counting yet.
M-30-HD comes next, in the same kind of sessions.

**M-30-HD detections complete, 2026-11-21.** Six approved sessions saved
all 19 parts. The first was stopped early by a power cut, which lost only the
part in progress, and a 5-minute cool-down came before each later session.
The joined file has **135,759 detections** on all 9,390 frames, in frame
order, with scores from 0.10 to 0.96: 128,302 car, 6,654 truck, 461 bus and
342 motorcycle. Its SHA-256 is
`465fdf04475841338d9261224c73037a5e5304f8b1b2ebdeef75d7f35eb7f7db`. The
image archive hash in the receipt matches the intake record. No tracker has
run on either sequence's detections, and no label has been used for counting
yet. The tracker comparison is next and needs the owner's approval.

## Result, 2026-11-21

Run once, with the owner's approval, under the rules above. Each variant ran
twice on each sequence, and both runs gave byte-identical output. Full numbers
are in [`experiments/gram_rtm_gate_v1_result.json`](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/gram_rtm_gate_v1_result.json).

Main line, cancel-reversals counter (correct / false / missed):

| Sequence (reference) | Gate on | Gate off | Aspect-free gate |
|---|---|---|---|
| M-30 (266) | 248 / 2 / 18 | 254 / 1 / 12 | 248 / 1 / 18 |
| M-30-HD (236) | 224 / 0 / 12 | 224 / 0 / 12 | 224 / 0 / 12 |
| **Pooled (502)** | 472 / 2 / 30 | 478 / 1 / 24 | 472 / 1 / 30 |

- **Aspect-free gate versus gate on: no harm.** Missed crossings did not
  fall (30 and 30). Pooled total errors fell by one, from 32 to 31.
- **Gate off versus gate on: supported.** Missed crossings fell from 30 to
  24, false crossings fell from 2 to 1, and neither sequence got worse.
- **Preference:** both pass. Gate off has 25 pooled total errors against 31
  for the aspect-free gate, 19% fewer, with no more false crossings, so by the
  rule gate off is preferred on this data.
- The plain counter gives identical totals. On M-30-HD the three variants tie
  at the main and 40% lines. The 60% sensitivity line on M-30 is the one place
  the aspect-free gate does worse than gate on: 31 missed against 27.

**What this allows.** The aspect-free gate does not damage ordinary straight-road
counting, but it does not improve it either. On its own this cannot back a
default change. The stronger signal is that the motion gate itself cost six
crossings on M-30, all with the same detections. That is a question for a new,
separately frozen test, not a conclusion from this one. Turning traffic, which
the gate was designed for, is not tested here.

## Counting lines

Both sequences look along a motorway from above, so traffic moves mainly up
and down the image. As in the UA-DETRAC protocol, each sequence gets **one
horizontal line across the full width at half the image height**: y = 240 for
M-30 and y = 360 for M-30-HD. Lines at 40% and 60% of the height are reported
as a sensitivity check only.

## Counter and matching

- The one-second cancel-reversals counter, with a **30-frame** window at 30
  fps, applied to the reference and every variant alike. Plain-counter totals
  are reported as a secondary table.
- Matching: same direction, at most **6 frames** apart (0.2 seconds, as on
  RoundaboutHD), and crossing points at most **3.9% of the frame width**
  apart: **31 pixels** on M-30 and **47 pixels** on M-30-HD.

## Variants

Gate on (default), gate off, and the aspect-free gate, unchanged since
2026-11-20, with every other setting at the library default. Each variant
runs twice, and both runs must give byte-identical output.

## Decision rule

There are only two sequences, so the UA-DETRAC sign test cannot apply. For
**aspect-free gate versus gate on**, the result is:

- **Supported** if pooled missed crossings fall; pooled false crossings rise
  by no more than 2, or by 10% of the pooled gain in correct crossings,
  whichever is larger; and neither sequence's total errors (false plus missed)
  rise by more than 2.
- **No harm** if it is not supported but pooled total errors rise by no more
  than 2.
- **Harmful** otherwise.

Gate off is judged by the same rule. If both pass, the aspect-free gate is
preferred unless gate off has at least 10% fewer pooled total errors and no
more pooled false crossings.

## What a result allows

Cars on a straight motorway rarely turn, so this data tests mostly whether the
aspect-free gate is safe on ordinary traffic. It does not test the turning
behaviour it was designed for.

- **Supported or no harm:** evidence that the candidate does not damage
  ordinary vehicle counting. Together with a supported UA-DETRAC result, it
  can back a default-change proposal. On its own, it cannot.
- **Harmful:** the candidate is not proposed as a default, whatever UA-DETRAC
  later shows, until the harm is explained and a new frozen test passes.
- All numbers are published with this protocol. Images and labels stay
  owner-local.

## Runner

`experiments/gram_rtm_gate.py` will be written and committed before the
detector run. It reuses the shared crossing, matching and cancel-reversals
code.
