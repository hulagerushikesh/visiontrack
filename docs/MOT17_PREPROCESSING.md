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
Regression examples exposed three differences. They now have a separately
versioned correction; the first audit below is retained, not rewritten:

- MOT17 removes predictions assigned to classes **2, 7, 8 and 12**, not every
  non-scoring class. Cars, bicycles, motorbikes and occluder labels are not
  automatically prediction-removal regions in this pinned reference policy.
- A zero-marked pedestrian GT is excluded from scoring, but its matched
  prediction is **not** removed merely for that flag.
- The reference zeroes sub-threshold overlap edges **before** full assignment;
  maximizing all IoUs and rejecting weak pairs afterwards is not equivalent.

These describe evaluation rules, not which detections are physically correct.
At the first audit checkpoint the broad historical policy was still the default.
The current MOT17 runner instead defaults to
**`visiontrack.mot17-preprocessing/v2`**. An explicit
`policy="visiontrack.mot17-preprocessing/v1"` preserves the original function
body structurally unchanged. Unknown policies and malformed thresholds are
rejected. V2 uses evaluation-only geometry and our own NumPy/Hungarian assignment;
TrackEval/SciPy remain dev-only independent references, not runtime dependencies.

The corrected policy passes all **1,050 frames again**, retaining exactly the
same 25,781 public outputs in this case. Authored class/zero-marking/empty/lineage
checks, a threshold-before-assignment counterexample, and **160 crowded frames
across eight deterministic seeds** also match the independent reference. These
are regression examples, not a guarantee of tie-specific IDs for all inputs.

### Lab compatibility boundary

Existing Lab metric schemas v1/v2 retain their historical preprocessing meaning.
The stored identifier `visiontrack.eval.mot17.preprocess_frame` is explicitly
executed with the **legacy** policy by the Lab's shared frame builder. This is
intentional: changing a dataset runner's default must not change stored Lab
metrics or failure extraction. Adopting the new dataset policy in Lab artifacts
requires a separate explicit contract migration and mixed-policy rejection;
it is not silently folded into the metric-v2 tag. That
[Lab migration is now implemented](LAB_EVALUATION_POLICY.md) for **new schema-3
metrics**, with policy-bearing failures/reports. Existing schema-1/2 semantics
are unchanged. No existing report is rewritten.

## Reproduction and receipt

```bash
PYTHONPATH=src:. python -m experiments.mot17_preprocessing_audit \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /path/to/a/new/check-directory
```

Initial audit: `../visiontrack-walkthrough/mot17-preprocessing-audit-xqgBG7/check`,
with its exact harness retained at repository revision `69f319c`.
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

The subsequent corrected-policy receipt is separately retained at
`../visiontrack-walkthrough/mot17-preprocessing-v2-0UcNhb/check`. Its adapter
verifies that reference XYWH boxes are unchanged, then recovers the exact original
XYXY boxes by verified IDs; it does not let an unnecessary floating-point
roundtrip manufacture geometry differences. The unused confidence carrier is
also checked against the independently relabelled IDs. No IoU/count tolerance
was relaxed to obtain agreement.

| Corrected-policy artifact | SHA-256 |
| --- | --- |
| Pre-execution method | `ed9e7977b2133d3fd8a129150721b5c3055d00953df6ebed828489edee55b33c` |
| Summary | `7dbd33ac9ff11972a05e81dfe856d6389a0ea783a2fb5163cf930d1e8280d68c` |
| Reference-scored rows | `f9d1fc75a92861510ef63e50dd808b128e0feb7e520083cbf42f94b93a04ccf8` |
| Manifest | `7091e51a25dd059d3915e5ecdfb1cf69232d89bdfcb20518103247e43b179898` |

Both receipts pin pre-execution sources and check them afterwards. The source
precision/adapter/text-loader limits above still apply. The current **44**
authored preprocessing tests pass, including original-body preservation and
malformed/unknown-policy guards. This is no tracker accuracy improvement.

The [v2 coverage and same-event trace](MOT17_COVERAGE_V2.md) are now also complete.
Independent lawful pixel/reference review remains separate and open before
selecting a tracking intervention.
