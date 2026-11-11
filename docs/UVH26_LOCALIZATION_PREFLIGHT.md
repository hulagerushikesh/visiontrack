# UVH-26 localization input: one-image preflight

**2026-11-11: exploratory engineering result, not an accuracy result.** The
[IISc dataset card](https://huggingface.co/datasets/iisc-aim/UVH-26/tree/v1.0)
labels UVH-26 v1.0 as CC BY 4.0 and provides sampled fixed-camera Bengaluru
traffic images with two consensus box-label sets. Its
[technical report](https://arxiv.org/html/2511.02563v1) says the released
training/validation split is stratified and randomized at the image level. The
validation COCO JSON does not expose camera, scene, session or timestamp fields.
This source therefore supports a bounded image-level feasibility probe, but
**cannot satisfy the planned scene-separated outcome test** from its released
metadata alone. It also has no temporal IDs or flow counts, so it cannot test
tracking, identity continuity or the intended traffic-counting product outcome.

The [offline preflight](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/uvh26_localization_preflight.py) checks
the publisher's validation-annotation SHA-256, the local YOLOX nano model hash,
COCO references and box geometry, selected image dimensions, full-frame proposal
capture, `detect()` parity, and spread-feature abstention. The
[small receipt](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/uvh26_localization_preflight_v1_result.json) uses
one publisher image, `UVH-26-Val/data/000/100341.png`, retained outside Git.
The annotation file contains 5,297 images and 63,497 boxes; all referenced
images/classes and box boundaries passed this preflight. In 2,387 rows the
publisher's `area` field differs from `bbox` width × height; 217 differ by more
than 1%, and all 217 touch an image edge. This is consistent with clipping, but
the preflight does not establish the publisher's calculation. Any later geometry
must derive area from the box rather than trust that field.

On the selected real image, the pinned 416-pixel YOLOX nano produced three road
class detections. Its 3,549 proposal rows fit the full-frame cap, all three
returned groups supported the fixed spread calculation, and ordinary
`detect()` returned exactly the same detections. The selected image has 11
publisher annotations across its fine-grained classes. These counts are **not**
recall or feature-quality scores: no class correspondence, reference matching,
independent label review or scene-level comparison was performed. The model's
COCO classes do not map one-to-one onto the dataset's 14 vehicle classes.

To reproduce the narrow check with the original publisher files stored outside
the repository, run from the checkout with the local source code on the path:

```bash
PYTHONPATH=src python -m experiments.uvh26_localization_preflight \
  --annotations /private/UVH-26-MV-Val.json \
  --image /private/100341.png \
  --model models/yolox_nano.onnx \
  --output /private/preflight.json
```

**Next decision:** keep this as a development source for proposal coverage and
annotation-interface checks. Before any localization outcome run, obtain a
camera-separated source or verifiable camera provenance, independently inspect
the relevant reference boxes and visibility, freeze the COCO-to-source class
mapping and ignore policy, then use the predeclared B0–B3 comparison in the
[signal audit](LOCALIZATION_SIGNAL_AUDIT.md). A few images or a random image
split cannot stand in for independent camera/session units. Bath's RoundaboutHD
clarification remains a separate possible route; it does not hold this
exploratory work.

The subsequent [MV/ST label-stability audit](UVH26_CONSENSUS_AUDIT.md) found that
ST omits 958 validation images listed by MV and that the two correlated consensus
files disagree on some boxes and classes. Neither file independently validates
the other or closes the localization-outcome gate.
