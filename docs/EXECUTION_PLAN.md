# VisionTrack v2 — Phased Execution Plan (for autonomous Claude Code sessions)

Each phase is **independently shippable**: if you stop after any phase, the repo is still in a
better, coherent state than before. Phases are ordered so the highest-value / lowest-risk work
(getting real data + a real baseline number) comes first, and the fragile research bits come last.

Give Claude Code **one phase per session**. Each phase lists a goal, concrete tasks, and an
acceptance test so the session has a clear "done" signal.

---

## Phase 0 — Real data + cached detections (the unlock)
**Goal:** stop being synthetic-only. Get MOT17 loading and a from-scratch baseline scored on it.

- Add `detection/mot_loader.py`: parse MOT17 `gt/gt.txt` and `det/det.txt`, seqinfo, frame rate.
- Define a fixed **train/val split** (e.g. half of each MOT17-train sequence held out) and freeze it.
- Add `data/cache/` with a `precompute.py` that serializes `(frame → boxes, scores, gt)` to disk.
- Wire the existing ByteTracker to consume cached MOT17 detections.
- Add HOTA + IDF1 to `eval/` (own impl cross-checked against `trackeval`, or vendor `trackeval`).

**Acceptance:** `visiontrack eval --dataset mot17 --split val` prints MOTA/IDF1/HOTA for the
from-scratch ByteTrack baseline on real data, and the number is in a sane published neighborhood.

---

## Phase 1 — Statistical rigor harness
**Goal:** every result is mean±std with a significance test. This is what makes it research.

- `eval/stats.py`: N-seed runner, paired bootstrap + Wilcoxon signed-rank, effect size, CI.
- `experiments/run_matrix.py`: takes a Hydra config sweep, runs all cells over seeds, writes a
  tidy results dataframe (one row per config×seed×sequence).
- `experiments/analyze.py`: consumes the dataframe → LaTeX/markdown tables + figures.
- Introduce Hydra/OmegaConf configs; a run is fully specified by its config hash.

**Acceptance:** `run_matrix.py` produces a `results.parquet`; `analyze.py` emits a markdown table
with mean±std and a p-value column for baseline-vs-baseline (sanity: p≈1).

---

## Phase 2 — Refactor cost into an ablation surface
**Goal:** make appearance/uncertainty/motion independent toggles without touching the solver.

- Extract `tracking/cost.py` with the factored cost: `w_iou`, `w_app`, `w_unc` + gate.
- Keep behavior identical when only IoU is on (regression-test against Phase 0 numbers).
- Every weight/branch is a config field.

**Acceptance:** with appearance and uncertainty weights at 0, MOT17 val numbers are **bit-identical**
to Phase 0 (proves the refactor is behavior-preserving).

---

## Phase 3 — RQ1: appearance branch (main thesis)
**Goal:** the appearance study, across all three datasets. This is the shippable centerpiece.

- `appearance/reid_onnx.py`: pretrained OSNet/FastReID ONNX embedder (lazy import, ONNX Runtime).
- `appearance/gallery.py`: per-track EMA appearance gallery, cosine cost into `cost.py`.
- `precompute.py`: extend to cache **embeddings per detection** (one-time, GPU-optional via Colab).
- Add DanceTrack + SportsMOT loaders (reuse MOT-format parser; note per-dataset quirks).
- Run the appearance-on vs appearance-off sweep across all three datasets, N seeds.
- **Failure-regime figure:** appearance's Δ-metric stratified by crowd density × occlusion length,
  including the continuous synthetic probe to trace the crossover curve cleanly.

**Acceptance:** a table + figure showing appearance's signed contribution flipping between MOT17
(helps) and DanceTrack (hurts), with p-values. This alone is a strong portfolio result.

---

## Phase 4 — RQ2: learned motion residual
**Goal:** the "we also propose a method" hook.

- `tracking/motion/residual.py`: tiny GRU/MLP predicting a correction to the CV Kalman mean;
  trained offline on GT trajectories (Colab, minutes), exported to ONNX, CPU inference.
- Training script + a held-out trajectory eval of the residual in isolation (before tracking).
- Ablate Kalman vs Kalman+residual across datasets; expect wins on SportsMOT/DanceTrack.

**Acceptance:** IDSW/HOTA improvement from the residual on maneuver-heavy data, with significance;
negligible on MOT17 (predicted null result, reported honestly).

---

## Phase 5 — RQ3: calibrated uncertainty-aware association
**Goal:** the state-estimation-flavored contribution.

- Reliability diagram: are gated innovations actually χ²? Calibrate if not.
- Fold normalized Mahalanobis into the cost with `w_unc`; sweep vs fixed-gate baseline under
  injected detector noise (reuse synthetic noise model + a noised real-data variant).

**Acceptance:** IDSW reduction under high-noise regime with significance; a calibration plot.

---

## Phase 6 — Artifact polish (mini-paper + demo + reproduce)
**Goal:** the three deliverables reviewers actually see.

- `make reproduce`: regenerates every table/figure from cache; CI runs a smoke subset.
- README rewritten as a mini-paper (abstract → RQs → method → results → limitations), figures embedded.
- Interactive web demo (`viz/webdemo/`): pick a clip, toggle the three branches, watch IDSW change.
- Deploy the demo (static host; pre-baked inference or lightweight ONNX-in-browser / server).

**Acceptance:** a fresh clone runs `make reproduce` green; the deployed demo link works; the README
reads like a short paper.

---

## Session-kickoff template (paste to Claude Code)

> Working on VisionTrack v2, Phase <N>: <goal>. Read PROJECT_v2.md and EXECUTION_PLAN.md first.
> Implement the Phase <N> tasks. Keep the from-scratch NumPy core intact; all new heavy deps
> (torch, onnxruntime) stay lazily imported and out of the core. Every experiment must read cached
> detections/embeddings — no GPU in the inner loop. End the session by running the phase's
> acceptance test and reporting the numbers. Do not start the next phase.

## Risk notes
- **Biggest risk:** dataset download friction (MOT17 needs registration). Do Phase 0 by hand-ish,
  supervised — don't let an autonomous session stall on a gated download.
- **Second risk:** metric mismatch. Cross-check your HOTA/IDF1 against `trackeval` early (Phase 0),
  or a reviewer won't trust any downstream number.
- **Scope discipline:** Phases 3 → 4 → 5 are each a real result. Ship Phase 3 publicly before
  starting 4; don't let the whole thing block on being "complete."
