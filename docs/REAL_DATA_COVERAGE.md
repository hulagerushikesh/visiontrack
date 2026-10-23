# Where the real-data misses come from: a bounded box diagnostic

Checkpoint: **2026-10-23**. We analyzed the **saved, unchanged MOT17-04-FRCNN
baseline**, not a new tracker run or candidate. All 1,050 frames, scoring
preprocessing and canonical failure events were rechecked against the
[sealed baseline](REAL_DATA_BASELINE.md). No pixels, model, tuning or C++ changes.

## What we learned in plain language

**Most missed reference boxes do not have a sufficiently overlapping raw detector
box in this input.** Changing how we remember tracking IDs alone is therefore
not a demonstrated answer to the main coverage problem. We also have a smaller,
specific set of misses with overlapping eligible detections to investigate.

These are **geometric descriptions, not proven causes**. "No overlapping box"
can mean absent detection, inaccurate localization, partial visibility relative
to a full reference box, or an annotation issue. We cannot distinguish those
possibilities without appropriate evidence. The reference labels are still not
independently visually verified. Counts are object-frames, not distinct people.

## Exact partition of the 21,825 canonical misses

IoU **≥0.5**, inclusive, is the fixed scoring-overlap threshold. The low-score
boundary is the unchanged **0.1**. Apply the following tests in table order;
each missed reference box belongs to exactly one group.

| Descriptive group | Missed boxes | Share of all misses | What the test establishes |
| --- | --- | --- | --- |
| No raw geometric neighbour | **19,387** | **88.83%** | No supplied detector box at any score has IoU ≥0.5 with this reference |
| Overlap only below the low-score boundary | **149** | **0.68%** | Overlapping raw boxes exist, but all score below 0.1 |
| Eligible overlaps removed by ignore preprocessing | **270** | **1.24%** | Score-eligible overlaps exist, but none survives the canonical full-reference ignore assignment |
| Eligible retained neighbour, no canonical scored match | **2,019** | **9.25%** | At least one overlapping score-eligible box survives ignore handling, but this reference is still a baseline miss |
| **Total** | **21,825** | **100%** | Exactly reconciles the unchanged baseline FN count |

The 270 ignore cases are **scoring pedestrians whose neighbouring detections were
removed**, not 270 ignored pedestrians wrongly added to FN. The preprocessing
matches against all reference rows before removing predictions assigned to ignore
objects. We retain that exact existing policy rather than silently changing it.

The last group is **not 2,019 guaranteed recoverable misses**, nor 2,019 proved
Kalman/gating failures. A detection can overlap multiple reference boxes, be
consumed in association, fail confirmation, or be geometrically changed by the
filter. We need assignment/lifecycle evidence before attributing a mechanism.

## Why one box cannot count as two detections

For each score pool, we apply score selection **before** the existing ignore
preprocessing, then construct a graph between scoring GT boxes and retained raw
boxes. Edges exist only at IoU ≥0.5. A binary-cost assignment finds the maximum
number of **disjoint** valid edges, rather than maximizing IoU and discarding
sub-threshold pairs afterwards. Only the count is interpreted; optimal identities
and tie-specific GT choices are not claimed.

| Static raw-box pool | Input boxes | Retained after ignore handling | GT boxes with any neighbour | Maximum disjoint GT/raw-box pairs | Missed GT with any neighbour | FN-only disjoint capacity |
| --- | --- | --- | --- | --- | --- | --- |
| All supplied scores | 28,406 | 26,338 | 27,881 | **26,241** | 2,168 | 2,122 |
| Score ≥0.1 (eligible) | 28,230 | 26,162 | 27,732 | **26,096** | 2,019 | 1,977 |
| Score ≥0.5 (high) | 27,824 | 25,756 | 27,370 | **25,739** | 1,869 | 1,827 |
| Score ≥0.6 (spawn-score boundary) | 27,753 | 25,685 | 27,300 | **25,672** | 1,846 | 1,804 |

All pools remove 2,068 raw detections in this case. The baseline removed 2,061
**tracker outputs**; these are different geometries/objects, not a contradiction.
Changing score selection can change the ignore assignment. Kept pools are not
assumed nested per frame, even when their aggregate counts happen to be ordered.
High/spawn-score rows are descriptive pools, **not simulated alternate settings**;
actual recovery, creation and confirmation depend on tracker state and stage.

The eligible FN-only capacity, **1,977**, ignores detections needed by already
matched reference objects. **Do not add it to the baseline's 25,732 TP.** The
full eligible graph supports only 26,096 simultaneous raw-box pairs across all
frames; pointwise neighbour counts would double-count shared boxes.

Nor is 26,096 a tracker-recall ceiling or an achievable target: tracker filtering
changes boxes, and the canonical scorer preserves previous correspondences.
Indeed **18 actually matched reference boxes have no raw IoU ≥0.5 neighbour at
any score**, and **19 have none in the retained eligible pool**. The output can
overlap where its source detection does not. An authored test also demonstrates
this counterexample. No improvement margin is inferred by subtracting these
diagnostic capacities from actual baseline TP.

Of all canonical misses, **1,610 have at least one scored public output with
IoU ≥0.5**, but are not matched to it under the canonical scoring correspondence.
This flags shared geometry/matching-policy ambiguity; it does not prove a tracker
gate failure, a wrong reference identity, or that each output was free to reuse.

## Connection to the first ID switch

The same preselected event remains reference **85**, track **19 → 31** at source
frame **54**. In its fixed context **51–57**, its three misses (51, 52, 53) all
belong to the eligible-retained-neighbour group:

| Source frame | Best retained eligible raw IoU | Best scored-output IoU to reference 85 |
| --- | --- | --- |
| 51 | 0.7604 | 0.1367 |
| 52 | 0.8459 | 0.1015 |
| 53 | 0.9122 | 0.1051 |

Thus these three misses cannot be described as "no sufficiently overlapping
supplied detection". This is a useful **specific mechanism question**, not a
reason to change thresholds immediately. The best scored output is not always
track 19; this table must not be confused with its individual-track IoU table.
Across the full sequence, 48 of the 2,019 eligible-neighbour misses occur at the
first two cold-start frames, where tentative tracks are not publicly emitted.
They remain in the scoring totals; we did not discard startup errors.

## Reproduction and integrity

```bash
PYTHONPATH=src:. python -m experiments.mot17_case_coverage \
  --baseline ../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle \
  --output /path/to/a/new/coverage-directory
```

The parent must exist; existing output directories are refused. The script pins
the original baseline manifest and verifies all **11 listed members**, including
both byte-identical runs. It checks every saved frame's preprocessing, regenerates
the canonical failures from saved scored pairs, reconciles all CLEAR metrics,
and writes one record per missed reference object-frame. It does not call the
tracker. Baseline production/wrapper source fingerprints are checked before and
after analysis. This reuses our evaluator, not an independent scoring implementation.

Actual local output, outside Git:
`../visiontrack-walkthrough/mot17-coverage-EJArI7/diagnosis`.
It contains `method.json`, `misses.jsonl`, `summary.json` and `manifest.json`.
The method is recorded before analysis; this is a post-baseline diagnostic,
**not a prospectively registered intervention study**. Execution used the new
analyzer/tests untracked on revision `e1c4d35`; code fingerprints are retained.
Dataset/derived raw records stay outside Git and have not been uploaded.

| Artifact | SHA-256 |
| --- | --- |
| Analyzer | `75b95165ea44f22372a5cd85f65dc9b7f079cfae66574b1cda82f68a98f72eaa` |
| Tests | `709cc85db6248fb39fe9db4db8c83383de5cb139823e8fded7a4b8eeeb028891` |
| Method | `ed778b30fd948b9cb5e3f6525a500f00a457e8fcc78e2d2646931b94b375260c` |
| Summary | `7733623d6466a2b6edc324337b972bdc3047911abb1d556e6fdfdf842cb43df1` |
| All 21,825 miss records | `2296eabd359321845caf5c30a985751634a114cc8bae504a01f2805216fa4d50` |
| Output manifest | `f5d6b0d2b8a86d20868002e72fa72606c72ad67fdbaba5b35348317a03359d85` |

All 21,825 `(source_frame, gt_id)` rows are unique and reconcile with the summary;
output checksums and the original baseline hashes pass. **1,923 non-slow tests
pass, one slow test deselected**. The 23 new tests include exhaustive small
assignment graphs, score/IoU boundaries, ignored objects, shared detections,
filter-geometry counterexamples, canonical failure reconciliation and input
fingerprint/symlink rejection. Ruff, strict documentation and all six prior
protocol-file checksums pass. No production or C++ files changed.

## Decision and next action

Do **not** treat persistent identity memory, a gate-off retry or a lower
confirmation threshold as a proven answer. The dominant miss group lacks raw
geometric support; the smaller eligible-neighbour group is not an automatic
tracker improvement budget. This supports evaluating detector and tracker
**together**, while retaining the narrower tracking research question.

Next inspect actual association/lifecycle decisions for the **same first
switch**, under unchanged defaults, and verify any replay against the saved
baseline outputs. Resolve why well-overlapping detections at 51–53 did not become
scored public output before proposing a single controlled intervention. No
second failure hunt, tuning, new imagery or C++ port is needed for that task.
Independent lawful pixel/reference review remains a separate open gate before
visual cause, annotation correctness or a completed real-clip case study claims.
