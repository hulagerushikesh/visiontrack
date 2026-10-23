# Real-data baseline: what fails before we change anything

Checkpoint: **2026-10-23**. The unchanged tracker has now run twice on the
[admitted annotation-only MOT17 case](REAL_DATA_CASE_INTAKE.md). Both fresh runs
produce byte-identical inputs/outputs, scored pairs, failures and summaries.
This establishes a reproducible starting point, **not an improvement**.

## Plain-language outcome

On this 35-second pedestrian sequence, the tracker keeps some identities well,
but many expected pedestrian boxes are not successfully matched. We must explain
the detection/localization and tracking losses together, rather than optimize
only the identity-switch number. A missed box means one reference object at
one frame; it does **not** mean a different person every time.

The first scored ID switch happens at **source frame 54**: reference pedestrian
**85**, previously matched to track **19**, is matched to track **31**. Track 19
is still publicly output at a different box. This is not simply evidence that
an expired ID should have been remembered forever. No pixels were examined, so
the visual cause and the correctness of the reference annotation remain open.

## What was fixed before execution

- Entire source range **1–1,050 inclusive**, one-based; fresh cold start at 1.
  This is not the historic second-half `mot17_val_half` evaluation.
- Existing source-verified public FRCNN detections and all raw reference rows.
  No new detector, embedding, camera compensation, tuning or candidate.
- All **20 `TrackerConfig()` defaults**, recorded in `plan.json` before creating
  a tracker: high/low scores 0.5/0.1, new-track score 0.6, IoU 0.3/recovery 0.5,
  three-hit confirmation, max age 30, Mahalanobis/class gates enabled,
  IoU weight 1, appearance/uncertainty/OCM weights 0, GIoU/ORU/GMC disabled,
  EMA 0.9, noise scale 1, residual path null, OCM delta 3.
- Existing `preprocess_frame` handling: scored pedestrian/consider rows only
  **after** predictions are matched against the full reference set for ignore
  removal. Ignored rows are not silently converted into missed pedestrians.
- Existing CLEAR-MOT, identity and HOTA implementations, with rounded display
  metrics **and full-precision result fields/per-alpha HOTA** retained.
- First chronological canonical scored ID switch, if any, and its fixed
  **±3 source-frame** window. No searching for a more impressive failure.

The wrapper saves `raw.jsonl` (detections, scores, all GT fields, public outputs),
`scored.jsonl`, `failures.jsonl` and `summary.json` per run. It never equates
internal alive/coasting tracks with actual public outputs. A second tracker and
reader are created afresh; all four run files agree exactly. This is same-code,
same-environment repeatability, **not an independent evaluator or accuracy proof**.

## Measured baseline

| Measure | Observed result |
| --- | --- |
| Source frames / reference pedestrian IDs | 1,050 / 83 |
| Scoring pedestrian boxes | 47,557 |
| Public detection rows | 28,406 |
| Raw public tracker boxes | 27,842 |
| Boxes removed by ignore preprocessing | 2,061 |
| Public tracker boxes retained for scoring | 25,781 |
| True-positive matched boxes | 25,732 |
| Missed reference boxes (FN) | **21,825** |
| False-positive output boxes (FP) | **49** |
| Scored ID switches | **43** |
| Fragmentation/interruption count | **148**, using the existing accumulator definition |
| Recall / precision at CLEAR IoU 0.5 | **54.11% / 99.81%** |
| MOTA / IDF1 / HOTA | **53.91% / 61.32% / 52.55%** |
| HOTA detection / association components | DetA **48.54%** / AssA **57.03%** |
| Mostly / partially / mostly-lost reference trajectories | 16 / 40 / 27 |

`TP + FN = 47,557`; `TP + FP = 25,781`. The 2,061 removed predictions are
neither scoring FP nor extra FN. ID switches are events, not 43 different people.
Precision alone would give a misleadingly favourable impression given recall.
These are our implementation's results, not a new official MOTChallenge score,
independent TrackEval run, deployment benchmark or calibrated flow-count measure.

## First-switch inspection: what the saved boxes actually show

The canonical event is zero-based `frame_index=53`, one-based `source_frame=54`.
Its reference box is `[392, 49, 441, 210]`; track 31's public box is
`[389.4274214085465, 49.20312913178651, 441.6839632601134, 217.99020880808285]`.
The sealed primary context is frames **51–57**. Reading earlier saved rows for
this **same event** establishes the last prior match at frame 46 and seven
consecutive misses at 47–53; it does not select another failure or rerun tracking.

The table uses IoU against reference 85, not the tracker's internal association
cost. "Best detection" is the single largest raw-detection IoU to this reference;
it is **not** a unique multi-object assignment or proof a detection was available
to this track after matching other objects. Values below are rounded for reading.

| Source frame | Best raw detection: IoU / score | Public track 19 IoU | Public track 31 IoU | Scored status for reference 85 |
| --- | --- | --- | --- | --- |
| 46 (last prior match) | 0.5151 / 1.000 | 0.5215 | Not output | Matched to 19 |
| 47 | 0.3842 / 1.000 | 0.4033 | Not output | Miss |
| 48 | 0.2878 / 1.000 | 0.3004 | Not output | Miss |
| 49 | 0.2121 / 1.000 | 0.2206 | Not output | Miss |
| 50 | 0.1912 / 1.000 | 0.1840 | Not output | Miss |
| 51 | 0.7604 / 0.296 | 0.1367 | Not output | Miss |
| 52 | 0.8459 / 0.817 | 0.0993 | Not output | Miss |
| 53 | 0.9122 / 0.991 | 0.0673 | Not output | Miss |
| **54** | **0.8759 / 0.999** | **0.0395** | **0.8923** | **Switch 19 → 31** |
| 55 | 0.9214 / 0.999 | 0.0141 | 0.8872 | Matched to 31 |
| 56 | 0.8860 / 1.000 | 0.0000 | 0.8916 | Matched to 31 |
| 57 | 0.8612 / 1.000 | 0.0000 | 0.9072 | Matched to 31 |

This establishes a loss of scored overlap followed by a new matched public ID,
with well-overlapping raw detections present before the new ID becomes public.
It does **not** establish which detections updated which internal track, a
Mahalanobis rejection, an actual tentative-track creation frame, an occlusion,
camera motion, annotation error or a causal fix. The source visibility field
increases over this interval, but that metadata is not our own visual review.
Do not prescribe gate-off, lower confirmation thresholds or appearance matching
from this table alone. Both missed-output and wrong-association trade-offs matter.

## Provenance and reproduction

Run from the repository with NumPy and the already admitted local inputs:

```bash
PYTHONPATH=src:. python -m experiments.mot17_case_baseline \
  --cache data/cache/mot17/MOT17-04-FRCNN.npz \
  --labels ../visiontrack-walkthrough/mot17-label-audit-NQQO7d/MOT17Labels.zip \
  --output /path/to/a/new/baseline-directory
```

The output's parent must exist; an existing output is refused. Input/source hashes
are checked before each run and after both. Failure leaves available artifacts,
without a success manifest or automatic retry. The selected range and defaults
are not command-line tuning options.

The actual local bundle is outside Git at
`../visiontrack-walkthrough/mot17-baseline-NvcCNo/bundle` (11 manifest-listed
files, **33,342,697 bytes**, plus the manifest). It contains no images. No dataset
annotations or derived raw tracking files were added to Git or uploaded.

Execution used production revision `4cceb37ac40e94477aca17882f521da1e93bfa20`
with the new tested wrapper and its test **untracked at execution**; this was
not a clean, already-committed harness run. `plan.json` records that status,
every production Python source hash and the wrapper/intake hashes before execution.
Python **3.12.9**, NumPy **2.3.1**, macOS 27 ARM64; no latency claim is made.
The current wrapper's bytes must match the fingerprint below to reproduce this
specific implementation. Input fingerprints are in the linked intake document.

| Artifact | SHA-256 |
| --- | --- |
| Baseline wrapper | `3bee8c65d614d5d1aa12662a2800012452aa541185a0ec623ffcd87349b4af9a` |
| Bundle manifest | `4ff57df09d5b4cf06491e984cf7b61f37b79ee22c0a087677f6587d5081984a8` |
| Pre-execution plan | `44de0d5536d88c1346bf26c94734be47dbf1f450263f60b61a681c480525988c` |
| Either run summary | `ddd3a22d252ea5f19bcc41015f73f79a402313035329d116e6ec94fe462f78c8` |
| Either raw input/output stream | `696151fe38fc5ab32f46f0f5ddfed944f5c4add3505896ed0cc5b5d9384baec4` |
| Either scored stream | `f9d1fc75a92861510ef63e50dd808b128e0feb7e520083cbf42f94b93a04ccf8` |
| Either failure stream | `49af3023fb69e753cd37f47484232d9ee3d97e952edefcdc033dc2322150ce94` |
| First-switch context | `b01495e29377f11d11b2c4f512edfa41392479357516668232fa9e3f8fa0b2c8` |

Verification: **1,900 non-slow tests pass, one slow test deselected**; 12 new
authored baseline tests cover raw/scored ignore separation, canonical switch
selection, a gap, no-event retention, default-tracker compatibility with the
existing runner, fresh byte equality, frame/appearance rejection, plan-before-run,
code drift and mismatch retention. The actual bundle's hashes, frame coverage,
failure totals and four repeatability comparisons also pass read-only checks.
Ruff, strict documentation build and all six old protocol checksums pass.

## Next bounded decision

**Coverage diagnosis is now complete:** [the saved-box decomposition](REAL_DATA_COVERAGE.md)
reconciles every miss, accounts for score/ignore rules and unique detection
capacity, and makes no causal or achievable-recall claim. The next task is the
unchanged association/lifecycle trace of the same first switch (item 2 below),
not a new parameter comparison.

1. **Before tuning**, decompose the missed boxes on this same fixed sequence:
   which have no sufficiently overlapping raw detection versus a detection
   that does not become a scored output? Respect unique assignment, ignore
   handling, score thresholds and public-output semantics; distinguish an
   upper-bound diagnostic from an achievable tracker result.
2. If needed, inspect actual assignment/lifecycle evidence for this same first
   switch under unchanged settings. The saved public boxes alone cannot prove
   internal gate or spawn decisions. Do not rerun a rejected intervention.
3. Resolve lawful pixel access and independent reference/context review, or
   retain a specific hold. Do not declare the visual case study complete.
4. Only then justify and prospectively fix one comparison, or conclude that the
   evidence does not support an intervention yet.

No owner action is needed for the next annotation diagnostic. Review/permissions
may need help later; private volunteer recording is not required to compute this
baseline. No C++ behavior change, deployment, outreach, accuracy improvement,
validated product demand or public-demonstration readiness follows from this step.
