# First real-data diagnostic: annotation intake

**Subsequent checkpoint (2026-10-25):** the originally annotation-only admission
below is preserved. The fixed 36–57 source-image window now has a separate bounded
local non-commercial admission and [preliminary visual review](MOT17_VISUAL_REVIEW.md).
Independent human review and public image redistribution are not approved by that
step; the original cache/annotation receipt remains unchanged.

Checkpoint: **2026-10-23**. The owner clarified that confidence in substantive
research, not demonstration polish or a deadline, is the priority. The prepared
synthetic demo remains an internal teaching aid. It is not a prerequisite for
technical evidence work or a declaration of public readiness.

## Decision

**Admit `MOT17-04-FRCNN` for local, non-commercial, annotation-only tracking
diagnosis. Hold the complete visual case study.** This is a narrower admission
than a permitted, visually reviewed case study. It does not complete that gate.

We already have this sequence's compact cache and the previously acquired official
annotation archive. No footage, embeddings or detector weights were downloaded,
read, uploaded or redistributed in this step. No tracker or comparison was run.

Selection is based on available source-checkable detections/labels and the
official description: an elevated night-time pedestrian street. It was chosen
before any new diagnostic outcome, not because a candidate wins on it. Camera
stability and the cause of any tracking error have **not** been visually verified.
The scene is not the blurred, multi-class OpenTrafficCam deployment domain.

The [official MOT17 archive](https://motchallenge.net/data/MOT17/) lists these
sequence properties and **CC BY-NC-SA 3.0**, with possible additional source
conditions. The [licence summary](https://creativecommons.org/licenses/by-nc-sa/3.0/)
does not supply every possible privacy/publicity permission. This decision covers
local non-commercial research on existing annotations only; it is not a legal
clearance for commercial use, people recognition or public footage distribution.
Attribute MOTChallenge and Milan et al.,
[MOT16: A Benchmark for Multi-Object Tracking](https://arxiv.org/abs/1603.00831),
when describing this data. Dataset material does not become MIT-licensed because
our software is MIT-licensed. Review any proposed distribution separately.

## What actually passed

The bounded, read-only
[intake script](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/mot17_case_intake.py)
pins the existing archive fingerprint, reads only this sequence's three
annotation members without extracting them, and compares **all nine** cached
arrays to independently parsed source columns at the cache's stored precision.
It preserves frame-stream row order, ignored objects and float32 rounding;
it does not accept approximate equality or rewrite the cache to make it pass.

| Item | Observed result |
| --- | --- |
| Source range | Entire sequence, frames **1–1,050 inclusive**, one-based |
| Metadata | 1,920 × 1,080; nominal 30 FPS; 35 seconds |
| Existing cache | 628,190 bytes; schema 1; FRCNN |
| Public detections | **28,406** rows; supplied scores retained |
| Raw reference boxes | **108,005** rows including non-scoring objects |
| Scored pedestrian boxes | **47,557**, belonging to **83** reference IDs |
| Non-scoring rows | **60,448**; not 60,448 extra missed pedestrians |
| Pixel/independent label review | Not performed |
| New tracker results or comparison | Not performed |

The source FRCNN member has seven columns, not the optional ten-column format
with trailing world coordinates. The intake checks the actual pinned format.
Source labels are published benchmark reference annotations, **not labels we
have independently verified against pixels**. Hash correspondence establishes
lineage and conversion correctness, not ground-truth infallibility.

### Reproduction and fingerprints

From the VisionTrack repository, with NumPy installed:

```bash
PYTHONPATH=src:. python -m experiments.mot17_case_intake \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip
```

The command prints a summary JSON to stdout only. Paths refer to existing local
files, not bundled or automatically downloaded data. Its synthetic unit fixtures
test intake mechanics, not real tracker performance.

Verification at this checkpoint: the command passed on the actual local inputs;
**1,888 non-slow tests passed, one slow test deselected**. Ruff, the strict
documentation build and all six prior protocol-file checksum checks passed.
No previous frozen study artifact, production tracker or C++ code changed.

| Input | SHA-256 |
| --- | --- |
| Cache | `75652705b632a3467846033ad8d74d91b5cfd8aa50a8b51c309e6f4bd8d5ef29` |
| Official labels ZIP | `0aa79322e91583369f42f17c4d79a0b145380d8732487bba59272048dc82b2b9` |
| Source `seqinfo.ini` | `f2d5bbe2c4d2a884422571987bc5363b61bb7e2c6748d1cff444e55b4886b888` |
| Source `det/det.txt` | `e1494db52e85cc13dad52ac01e7efe972e4e432f6ce788da8a4dfa0d38edce75` |
| Source `gt/gt.txt` | `f8cfbe36ef38a2e1857d7ebfe7d754b2355a3ffb9e1f9cedea435e86e4fbc948` |

## Next bounded action: unchanged baseline, not a new intervention

**Completed after this intake:** the [unchanged full-sequence baseline](REAL_DATA_BASELINE.md)
now reproduces all four run artifacts byte for byte from two fresh trackers.
It records 43 scored ID switches; the first is reference 85, track 19 → 31 at
source frame 54. The checklist below records the original scope, not pending
baseline work. No pixels were reviewed or candidate evaluated.

1. Recheck these inputs and record the code revision, environment and complete
   `TrackerConfig()` defaults **before** execution. Use the full range above
   with a fresh tracker starting at frame 1; no warm-start, embedding or tuning.
2. Run the existing MOT17 evaluation path. Preserve its pedestrian/consider and
   matched-ignore preprocessing (`visiontrack.eval.mot17.preprocess_frame`),
   which the Lab metric path also uses. Do not drop ignore rows before matching.
   Retain raw outputs as well as scored outputs so a discrepancy is explainable.
3. Reproduce the baseline from a fresh tracker. Report detection misses, false
   positives and identity errors alongside association/overall metrics. Do not
   substitute one good number for the trade-offs.
4. Inspect the **first chronological scored identity switch**, if one exists,
   with its adjacent inputs and track outputs. If none exists, report that;
   do not keep changing the range to manufacture one. Metadata may identify
   what changed, but cannot prove visual occlusion or a causal mechanism.

This full-sequence, cold-start diagnostic is **not** the historic second-half
`mot17_val_half` run: range/start-state differences preclude direct headline
comparison. MOT17 has already informed this project's development. Neither
the full sequence nor its second half is newly untouched validation.

Only after diagnosis should we justify and freeze a single new comparison,
including relevant failure/trade-off measures, before its outcomes. Do not
automatically retry the rejected gate-off or stopped counting-band candidate.
If the evidence suggests no defensible intervention, retain that conclusion.

## Gates still open

- [x] Baseline output, reproducibility and a bounded annotation diagnostic event;
      see [the measured results and limits](REAL_DATA_BASELINE.md).
- [ ] Lawful access to the relevant pixels and actual independent label/context
      review before making a visually grounded explanation. No new image
      download is authorized by this document.
- [ ] An explicitly justified comparison and prospective evaluation scope.
- [ ] A readable case study with a supported decision and clear limitations.
- [ ] Representative domain evidence before any transfer or adoption claim.

There are **no annotated traffic flow definitions, calibrated counting line or
source-to-world mapping** admitted here. Benchmark reference IDs do not establish
long-term person identity or exit/return truth. This route can advance ordinary
tracking diagnosis without pretending to complete RQ5, traffic counting,
customer validation or public-demonstration readiness. C++ remains unchanged.
