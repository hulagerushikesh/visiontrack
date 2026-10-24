# MOT17 preprocessing: case agreement and policy boundaries

Checkpoint: **2026-10-24**. The independent raw-output check passes on every
one of the **1,050 MOT17-04-FRCNN frames**: exact ordered scoring IDs and boxes,
**27,842 raw public outputs → 25,781 kept outputs** in both implementations.
The reference's resulting JSONL is byte-identical to the sealed baseline's
scored JSONL. No tracker execution, tuning, footage or historical rewrite.

This closes the case-specific ignore/distractor check left open by
[evaluator v2](EVALUATOR_V2.md). It does **not** establish correct visual labels,
all-dataset equivalence or a successful tracking intervention.

## What was checked independently

The official annotation archive is fingerprinted and all cache arrays are
reverified against its stored-precision conversion. Every saved raw frame's GT
IDs, boxes, classes and consider flags are checked against these source rows.
The pinned TrackEval dataset constructor and **its own** preprocessing method,
IoU geometry and SciPy assignment are then used on all raw public predictions.
Our saved preprocessing must also reproduce exactly, independently of the
reference result. Any frame discrepancy gives a nonzero exit, not a silent pass.

The adapter supplies XYWH detection arrays plus independently calculated XYXY
similarities. All predictions have pedestrian class 1. Saved public outputs do
not contain confidence; the reference's unused confidence field carries original
track IDs solely to invert its dense relabelling, including identical boxes.
It does not influence matching. Temporary empty inventory files satisfy the
actual constructor; no alternative class map or fake preprocessing is used.
**The reference text loader/export roundtrip is not tested.** Annotation/cache
precision, adapter lineage and source fingerprinting are explicit boundaries.

## General policy discrepancies found in authored examples

A pass on this particular input does not make the old policy universally right.
Regression examples expose three differences requiring a separately versioned
correction before treating the pipeline as generally reference-aligned:

- MOT17 removes predictions assigned to classes **2, 7, 8 and 12**, not every
  non-scoring class. Cars, bicycles, motorbikes and occluder labels are not
  automatically prediction-removal regions in this pinned reference policy.
- A zero-marked pedestrian GT is excluded from scoring, but its matched
  prediction is **not** removed merely for that flag.
- The reference zeroes sub-threshold overlap edges **before** full assignment;
  maximizing all IoUs and rejecting weak pairs afterwards is not equivalent.

These describe evaluation rules, not which detections are physically correct.
Current source at this audit checkpoint still uses the broad historical policy.
The next implementation must preserve explicit legacy reproduction and avoid
claiming an accuracy gain from changing a measuring rule.

## Reproduction and receipt

```bash
PYTHONPATH=src:. python -m experiments.mot17_preprocessing_audit \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /path/to/a/new/check-directory
```

Actual audit: `../visiontrack-walkthrough/mot17-preprocessing-audit-xqgBG7/check`.
The method was written before reference execution and pins the full original
baseline manifest, annotation/cache source correspondence, harness, local
preprocessor/core and all reference Python sources. Inputs and sources are
rechecked afterwards; full artifacts remain outside Git.

| Artifact | SHA-256 |
| --- | --- |
| Pre-execution method | `ae38fbc34c8a2dbec226f7a25b94a10843d3666984c00fd205cc355f4234a304` |
| Summary | `5a501e3970aafb9db4289e60a5c4194b99377a4a7bb6af00f29935721e8e6b2b` |
| Reference-scored rows | `f9d1fc75a92861510ef63e50dd808b128e0feb7e520083cbf42f94b93a04ccf8` |
| Manifest | `5fc70a972fb47537b111bf0e222346d68660f175ef20262369fdc63ea84af967` |

Reference: TrackEval `12c8791b303e0a0b50f753af204249e622d0281a`, the same pinned
dev-only reference used by the metric check. Its optional BURST import warning
about `pycocotools` does not affect this MOT17 preprocessing check.

Local authored tests: **26 pass**, covering class policy, zero-marking, empty
sides, identity recovery, malformed inputs, immutability and CLI failure status.
The tests expose old-policy counterexamples rather than pretending they pass.

Next: correct and version the general preprocessing policy, recheck it against
the independent implementation, then re-derive the v2 missed-object partition.
Independent lawful pixel/reference review remains separate and open.
