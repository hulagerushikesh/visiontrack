# UVH-26 validation consensus: label-stability audit

**2026-11-11 decision: keep UVH-26 as development material only.** The
[publisher's v1.0 card](https://huggingface.co/datasets/iisc-aim/UVH-26/blob/v1.0/README.md)
releases Majority Voting (MV) and STAPLE (ST) annotation files under CC BY 4.0.
Its [technical report, §4](https://arxiv.org/html/2511.02563v1) says both
methods aggregate the same crowdsourced, model-assisted annotations; most box
coordinates were left unchanged by annotators. The expert-labeled gold set is
not public. Thus, comparing MV with ST diagnoses *consensus stability*, not
localization accuracy or independent truth.

The [pinned audit code](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/uvh26_consensus_audit.py) read only the
two official validation COCO JSON files, checked both SHA-256 digests and box
geometry, aligned images by filename, then matched boxes within shared images
without using class. It maximized eligible match count then total IoU at a
fixed 0.5 threshold. Raw JSON stayed outside Git; the
[compact receipt](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/uvh26_consensus_audit_v1_result.json) contains
aggregates and source hashes. No image pixels or detector outputs were opened.

| Check | Observed in the released validation files |
| --- | ---: |
| MV / ST listed images | 5,297 / 4,339 |
| Shared / MV-only / ST-only images | 4,339 / 958 / 0 |
| MV boxes on MV-only images | 9,793 |
| MV / ST boxes on shared images | 53,704 / 57,163 |
| Matched at IoU ≥ 0.5 | 53,187 |
| Unmatched MV / ST boxes on shared images | 517 / 3,976 |
| Matched boxes with identical coordinates | 43,752 (82.26%) |
| Matched boxes with different fine class | 2,866 (5.39%) |
| Matched boxes with nonzero bottom-center shift | 4,150 |

The matched median IoU and median bottom-anchor difference are 1 and 0. These
medians conceal unmatched boxes and a disagreement tail: 1,271 matched pairs
have IoU below 0.9, and 2,526 of the shared images contain at least one
unmatched box. The pair assignment is a geometry comparison under this audit's
policy, **not** proof that every matched pair represents the same physical
object in a crowded scene. The 958 absent ST image records are missing from
that file; the files alone do not explain why.

The [paper's evaluation mapping, §6.1](https://arxiv.org/html/2511.02563v1)
maps Hatchback/Sedan/SUV/MUV/Van to COCO car, Bus/Mini-bus to bus and Truck to
truck. It excludes two-wheelers/cycles because rider-inclusive UVH boxes differ
from COCO's geometry. Using only pairs whose labels both fall into those three
comparable classes, 299 of 14,811 still disagree on the broad class. This is a
mapping diagnostic, not a new accuracy score.

**Research consequence:** do not use one consensus as ground truth and the
other as an independent validation of proposal spread. Do not infer a held-out
camera/site split from this release: camera and session identifiers are absent
from the JSON, and the publisher describes a randomized image-level split.
The one-image [capture preflight](UVH26_LOCALIZATION_PREFLIGHT.md) remains a
useful engineering check. An outcome comparison still requires independently
checked boxes, a verifiable scene-separated split, a frozen class/ignore policy
and the [predeclared comparison](LOCALIZATION_SIGNAL_AUDIT.md). No tracker or
C++ implementation change follows from this audit.

Reproduce with local source and the exact publisher files outside the repo:

```bash
PYTHONPATH=src python -m experiments.uvh26_consensus_audit \
  --mv /private/UVH-26-MV-Val.json \
  --st /private/UVH-26-ST-Val.json \
  --output /private/consensus-audit.json
```
