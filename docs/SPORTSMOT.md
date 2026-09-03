# SportsMOT — the second non-linear-motion dataset (RQ2)

SportsMOT (NeurIPS 2022) is the second maneuver-heavy dataset in the study, added
to strengthen **RQ2 (learned motion)**. Where DanceTrack couples two hard things
— non-linear motion *and* near-identical appearance — SportsMOT **decouples**
them: athletes move fast and change direction sharply (so the constant-velocity
prior is stressed), but players are visually distinguishable (so appearance is
*informative*, unlike dancers). It is the cleaner test of "does a better motion
model help when motion is the hard part but appearance isn't?".

It ships in the standard **MOT-Challenge layout** (`<seq>/seqinfo.ini`,
`<seq>/gt/gt.txt`, `<seq>/img1/*.jpg`), so the from-scratch loader reads it
**verbatim** — the same generic reader used for DanceTrack, exposed under the
neutral aliases `MotSequence` / `MotDetectorSequence` / `discover_mot_sequences`.

## Status

**Code path complete and tested; awaiting the dataset download to produce
numbers.** The loader, the cache pipeline, `--dataset sportsmot` in both the
benchmark and the error-taxonomy tool, and the `precompute_sportsmot.py` script
are all wired and covered by `tests/test_sportsmot.py` (a tiny hand-written MOT
sequence, no download, runs in CI). What is *not* here is the dataset itself
(~a few GB of frames) — that is the one manual step below.

## Reproduce

1. **Download** SportsMOT (see the official repo) and unzip so a split dir
   (`val/`) of MOT-format sequences exists, e.g. `~/Downloads/sportsmot/val`.

2. **Precompute the caches** (one `.npz` per sequence, shared schema). Two modes,
   mirroring the DanceTrack protocol:

   ```bash
   # perturbed-GT — isolates association from detector quality (oracle protocol)
   python data/cache/precompute_sportsmot.py \
       --data-root ~/Downloads/sportsmot --split val \
       --out data/cache/sportsmot

   # real detector — detection quality is part of the measurement (like MOT17)
   python data/cache/precompute_sportsmot.py \
       --data-root ~/Downloads/sportsmot --split val \
       --out data/cache/sportsmot_yolox \
       --detector-model models/yolox_nano.onnx
   ```

   For the appearance presets, also precompute Re-ID embeddings for the crops
   (same as DanceTrack: `precompute_embeddings.py --glob 'v_*.npz'`), which land
   as `<seq>.<embedder>.emb.npz` sidecars and are picked up automatically.

3. **Run the benchmark** (leaderboard + paired significance + ID-switch taxonomy):

   ```bash
   python -m experiments.benchmark --dataset sportsmot \
       --out-md report.md --out-html web/benchmark-sportsmot.html
   # cache dir defaults to data/cache/sportsmot; override with --cache-dir
   ```

   and the standalone error taxonomy:

   ```bash
   python -m experiments.error_taxonomy --dataset sportsmot --preset bytetrack
   ```

## RQ2 hypothesis to test once the data is cached

The learned motion-residual was an honest negative on DanceTrack (it helped the
one-step predictor but hurt the tracker, via a train/serve distribution shift).
SportsMOT is the discriminating follow-up: if the residual **still** hurts here —
where appearance can rescue identity — the conclusion generalizes beyond the
dancer confound; if it helps, the negative was appearance-specific. Either way,
the same frozen-baseline, seed-varied, paired-significance harness reports it.

## What to wire once numbers exist

- serve the report at `/benchmark/sportsmot` (add the build + route to
  `vercel.json`, a `/benchmark/sportsmot` case to `_route()` in
  `experiments/_benchmark_html.py`, and a fourth tab to the `.dataset-tabs`).
- tick RQ2/SportsMOT in [`HORIZONS.md`](HORIZONS.md) and [`STATUS.md`](STATUS.md).
