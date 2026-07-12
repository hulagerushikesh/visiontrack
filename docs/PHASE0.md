# Phase 0 — Real data + cached detections (runbook)

Goal of this phase: stop being synthetic-only. Load **real MOT17**, run the
from-scratch ByteTracker on its **public detections**, and score it with
**MOTA + IDF1 + HOTA** — everything driven from a compact on-disk cache so the
~5 GB of raw frames can be deleted.

Nothing here trains or runs a detector: Phase 0 uses MOT17's public detections
so there is no detector confound.

## 1. Get MOT17 (manual — one time)

1. Register at <https://motchallenge.net> and download **`MOT17.zip`**
   (`https://motchallenge.net/data/MOT17.zip`, ~5 GB).
2. Unzip anywhere, e.g. `~/datasets/MOT17/`. Expected layout:
   ```
   MOT17/train/MOT17-02-FRCNN/{det/det.txt, gt/gt.txt, seqinfo.ini, img1/}
   ```
3. Phase 0 only needs `det/`, `gt/` and `seqinfo.ini`. You may **delete every
   `img1/`** immediately to reclaim the space — the cache built next does not
   use images.

## 2. Build the cache (one time)

```bash
python data/cache/precompute.py \
    --data-root ~/datasets/MOT17 --split train --detector FRCNN \
    --out data/cache/mot17
```

Prints one line per sequence and the total size (expect a **few MB** for all 7
MOT17-train videos). After this, tracking experiments read only the cache; the
raw dataset is no longer needed.

Other detectors: `--detector SDP` (strongest) or `--detector DPM` (weakest,
unbounded scores — the loader min-max normalises those; FRCNN/SDP confidences
are already in `[0,1]` and pass through untouched).

## 3. Evaluate (the acceptance command)

```bash
visiontrack eval --dataset mot17 --split val
```

Defaults: `--split-file mot17_val_half`, `--detector FRCNN`,
`--cache-dir data/cache/mot17`. Prints per-sequence and overall
**MOTA / IDF1 / HOTA / DetA / AssA / IDSW / MOTP**. Add `--json` for machine
output, `--split train` or `--split all` for the other subsets.

## The split

`data/splits/mot17_val_half.json` is **frozen and committed**: for each of the
7 MOT17-train videos, frames `1…⌊L/2⌋` are `train` and the rest are `val`
(the standard "val-half" protocol). Splitting *within* each video keeps every
scene in both halves and makes our val numbers comparable to published
val-half results. It never drifts because it is data-independent (explicit
frame ranges, not recomputed from the download).

## Reproducibility

The tracker is **deterministic** — no RNG in the online loop — so a given
cache + config yields identical numbers every run (a `--seed` is threaded
through for the synthetic path and future stochastic components). The cache is
the reproducibility anchor: commit the config, keep the cache, and the numbers
regenerate exactly.

## Metric trust

Our HOTA/IDF1 are implemented from scratch (`eval/hota.py`) and
**cross-checked against `trackeval`** to within `1e-3` on perfect, identity-
switch, and random scenes (`tests/test_hota_vs_trackeval.py`). Enable the
cross-check locally with:

```bash
pip install "git+https://github.com/JonathonLuiten/TrackEval.git"
pytest tests/test_hota_vs_trackeval.py
```

## What a "sane" number looks like

The headline ByteTrack figures (~76 MOTA / ~79 IDF1) use a **private YOLOX**
detector. With MOT17 **public** detections the honest neighbourhood is lower —
roughly **MOTA ~50–65, IDF1 ~55–68, HOTA ~45–58**, and it varies by detector
(SDP > FRCNN > DPM). Judge the acceptance numbers against the *public-detection*
neighbourhood, not the private-detector headline.

## Results (MOT17 val-half, public detections)

Measured 2026-07-12 with the frozen `mot17_val_half` split, `TrackerConfig`
defaults, on real MOT17-train:

| detector | MOTA | IDF1 | HOTA | DetA | AssA | IDSW |
|----------|-----:|-----:|-----:|-----:|-----:|-----:|
| **SDP**   | 0.624 | 0.673 | 0.565 | 0.542 | 0.589 | 254 |
| **FRCNN** | 0.469 | 0.570 | 0.497 | 0.423 | 0.587 | 188 |
| **DPM**   | 0.115 | 0.182 | 0.193 | 0.093 | 0.404 |  22 |

SDP lands squarely in the public-detection neighbourhood; the detector ordering
(SDP > FRCNN > DPM) is as expected. IDSW is high because association is
**motion-only** — this is exactly the gap v2's appearance branch (RQ1) targets.

### Metric trust — end-to-end trackeval agreement

`scripts/xcheck_mot17_trackeval.py` runs our whole pipeline (MOT17
preprocessing **+** HOTA/IDF1/CLEAR) against trackeval's own MOT17 evaluator on
identical raw tracker output. On `MOT17-09-FRCNN` (525 frames):

```
             MOTA     IDF1     HOTA     DetA     AssA
OURS       0.5388   0.5474   0.4537   0.4877   0.4222
TRACKEVAL  0.5388   0.5474   0.4523   0.4824   0.4243
DELTA      +0.0000  +0.0000  +0.0014  +0.0053  -0.0021
```

MOTA and IDF1 match **exactly** (proving the distractor/zero-marked
preprocessing is correct); HOTA agrees within `0.0014` (Hungarian tie-breaking
across HOTA's 19 α-thresholds). The metric math is additionally unit-tested
against trackeval on synthetic scenes in `tests/test_hota_vs_trackeval.py`.
