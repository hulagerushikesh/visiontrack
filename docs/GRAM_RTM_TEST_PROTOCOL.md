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
- **Reference:** every labelled vehicle (car, van, truck, big truck,
  motorbike), using the box centre.
- **Frame alignment:** label file *k* is expected to belong to image *k*+1.
  Before any detector run, this is checked against the authors' own 2013
  detections, which are numbered from 1. On 200 evenly spaced frames, take the
  mean best-overlap between label boxes and those detections at offsets −1, 0,
  +1 and +2. The offset with the highest mean is used. If it is not +1, record
  that here before going on. No tracker or counting is involved.
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
- 640-pixel input, `upstream` preprocessing (the official YOLOX colour order
  and resize);
- confidence floor 0.10, so the tracker's low-score recovery stage gets its
  inputs; NMS IoU 0.45;
- COCO classes car (2), motorcycle (3), bus (5) and truck (7), each kept as
  its own class.

Detections are computed once per sequence, saved with a hash, and replayed
identically into every variant. The run is moderate laptop load and needs the
owner's approval first. A 20-frame timing is measured and reported before the
full run.

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
