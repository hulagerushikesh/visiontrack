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

To reproduce privately from the pinned derivative stored outside Git:

```bash
PYTHONPATH=src:. python -m experiments.lta_localization_preflight \
  --root /private/lta-localization-preflight \
  --model models/yolox_nano.onnx \
  --output /private/lta-localization-preflight/receipt.json
```
