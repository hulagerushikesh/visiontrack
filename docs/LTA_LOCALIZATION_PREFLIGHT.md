# Singapore LTA still-image localization preflight

**2026-11-11 — development feasibility, not an accuracy study.** This is the
first full small-source real-image pass through the current proposal extractor.
It does not select a detector, assess localization error, or change tracking.

## Source and rights

The [LTA Traffic Images dataset](https://data.gov.sg/datasets/d_6cdb6b405b25aaaacbaf7689bcc6fae0/view)
is distributed under the [Singapore Open Data Licence 1.0](https://data.gov.sg/open-data-licence).
Its licence allows research and commercial use with attribution, but does not
grant rights over personal data. This work uses a separately published
[63-image human-corrected subset](https://huggingface.co/datasets/LOVEIII486/isy5002-lta-traffic-images)
at revision `78428468834612d7fdd77e7cd097e8311c2754fe`; its author marks
the annotations CC BY 4.0. Required attribution: contains information from
LTA's Traffic Images dataset, accessed through the cited derivative on
2026-11-11, under Singapore Open Data Licence 1.0; annotations by the ISY5002
Project Team under CC BY 4.0. Neither LTA nor the Singapore Government endorses
VisionTrack. The images and annotation files remain owner-local outside Git;
only aggregate counts and source/file hashes are committed.

The subset comprises 63 images, 1,197 vehicle boxes and eight declared camera
IDs. The author states that one annotator corrected YOLO26x pre-labels, 17
dense/dark validation images were excluded, and the retained frames were already
used for model comparisons. There is no independent holdout here. This source
also has still images sampled roughly every ten minutes, with no object IDs or
flow truth; it cannot test tracking continuity or counts.

## Fixed engineering pass

The [preflight code](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/lta_localization_preflight.py)
pins the dataset revision, metadata hashes and existing YOLOX nano ONNX model
hash. It verifies all 63 image SHA-256 values against the pinned manifest,
dimensions, camera/path metadata, 1,197 annotation boxes and classes. For every
image it compares ordinary `detect()` with `detect_with_proposals()` exactly,
retaining all 3,549 proposal rows of the 416-pixel model and auditing group
completeness. No reference-box matching or B0–B3 comparison is run.

The [aggregate receipt](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/lta_localization_preflight_v1_result.json)
reports 223,587 proposal rows, 87 returned road-class detections, 71 supported
spread values, 10 groups with too few same-class proposals, and six singleton
groups. All images, metadata and detector parity passed. Camera 2701 yielded
zero returned road-class detections in seven retained images. On the fixed
416-pixel input, 850 of 1,197 source boxes are under ten pixels high; for
camera 2701, 246 of 268 are under ten pixels high. The small projected sizes
are a plausible contributor to low detector coverage, not a proven cause.
These raw reference and detection totals are **not recall**: boxes were not
matched, label reliability has not been independently checked, and model/source
class semantics may differ.

## Decision

This fixed 416-pixel YOLOX nano configuration is **not ready for a B2/B3
localization comparison on this source**. Its supported proposal signal exists
only for returned detections, and a camera with no returned detections cannot
contribute paired localization outcomes. Do not tune confidence or image size
on these already inspected validation frames and call the result held out.
The next comparison needs a predeclared detector configuration, independent
scene-separated evaluation images, and independently checked reference boxes.
Bath's RoundaboutHD rights/label clarification remains a separate route. The
C++ tracker has no new accepted behavior to port.

There is a further design limit: eight cameras total cannot provide eight
test camera units **and** a separate camera-disjoint development set. The
existing scene-level interval floor is eight test scenes. These 63 frames
therefore cannot become the frozen B2/B3 result even if box coverage improves.

## Predeclared development-only overlap screen

Before opening another detector result, use the same pinned 63 images and
supplied boxes in a bounded engineering diagnostic. Compare the already used
YOLOX nano at 416 input with the existing local YOLOX-X at its fixed 640 input;
both use confidence 0.25, NMS IoU 0.45 and the same four COCO road classes.
Verify both model hashes, every image hash and proposal-capture parity with
ordinary detections. Count, by camera, supplied class and projected box height,
how many supplied boxes have *any* same-class returned box at IoU ≥ 0.5 and
how many have a supported proposal-spread box. This is not one-to-one matching:
one detection can overlap multiple supplied boxes. Keep images and annotation
rows outside Git; commit only aggregate counts. The comparison is an
engineering coverage check, not recall, accuracy, causal evidence about input
size or a new model choice for held-out work. Nano and X differ in both weights
and input size. No threshold will be tuned based on these 63 validation frames.

**Result, 2026-11-12.** The predeclared [development screen](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/lta_detector_agreement.py)
passed pinned source/model hashes and exact ordinary-detection parity for both
models. The [aggregate receipt](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/lta_detector_agreement_v1_result.json)
contains no image or annotation rows. Nano returned 87 road-class detections;
51 supplied boxes had any same-class IoU ≥ 0.5 overlap and 45 had overlap with
a supported-spread detection. YOLOX-X returned 406 road-class detections; the
corresponding counts were 302 and 273. Nano had no returned box at camera
2701; X returned 81 there, with 54 supported-overlap supplied boxes. Across all
images, nano had no returned detections in 27 of 63 images versus 10 for X.
The under-10-pixel projected-box bins contained 850 supplied boxes at 416 and
551 at 640; only 2 and 48 respectively had any overlap. Size bins differ
because the models' input resolutions differ, so bin comparisons are not
controlled effects. One detection can overlap multiple supplied boxes, and
those annotations are model-assisted and single-annotator. None of these
counts is recall, precision, a held-out score or evidence that X improves
tracking. The result only supports seeking a better detector/source pairing;
it cannot make the eight-camera source meet the independent-scene protocol.

To reproduce privately from the pinned derivative stored outside Git:

```bash
PYTHONPATH=src:. python -m experiments.lta_localization_preflight \
  --root /private/lta-localization-preflight \
  --model models/yolox_nano.onnx \
  --output /private/lta-localization-preflight/receipt.json
```
