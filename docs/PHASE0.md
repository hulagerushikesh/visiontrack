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
