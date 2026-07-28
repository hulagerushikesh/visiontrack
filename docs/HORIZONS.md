# VisionTrack — Horizons (post-v2 roadmap)

v2 answered the three research questions and shipped the three deliverables
(mini-paper, reproducible benchmark, deployed demo). This document is the roadmap
for what comes after, organised as **three horizons**. The ordering is by value
per effort, not ambition: deepen the research first (it's the identity), make it
usable second, shape a product third.

**The moat to protect.** The defensible parts of this project are (1) the
from-scratch NumPy core and (2) the honest evaluation harness (from-scratch
HOTA/IDF1 cross-checked to 1e-3, paired significance tests, config hashing).
Every horizon leans on those. We do **not** try to out-run optimized
C++/CUDA trackers — that is a separate sibling project (see
[`CPP_CUDA_TRACKER_PLAN.md`](CPP_CUDA_TRACKER_PLAN.md)), not a horizon.

---

## Horizon 1 — Deepen the research (portfolio-strengthening)

Extends the study's identity; low risk, reuses the whole harness.

### H1.1 — Tracker zoo (significance-tested lineage) ✅ *done*
A named-preset registry (`tracking/presets.py`) expresses the tracking-by-detection
lineage on the shared core — single-stage **SORT**, **DeepSORT**-style (single-stage
+ Re-ID), **ByteTrack** (two-stage), **ByteTrack+ReID** (BoT-SORT-lite), GIoU — so
they compare on identical detections/metrics/seeds. `experiments/tracker_zoo.py`
runs the whole family and reports a mean±std leaderboard + paired Wilcoxon vs the
ByteTrack baseline. This upgrades the project from "a study of 3 tricks" to "a
rigorous MOT benchmarking platform". Run it with `make zoo`.

**First result (hard synthetic scene, 15 runs/variant, vs `bytetrack`):** the
regime decides the winner — on ambiguous-motion scenes appearance re-ID helps
(`bytetrack_reid`: IDF1 +0.002, p=0.04\*; HOTA +0.001, p=0.03\*) while GIoU hurts
(`bytetrack_giou`: MOTA −0.009, p=0.03\*; HOTA −0.005, p=0.02\*); on easier
occlusion-heavy scenes the two-stage recovery is the significant win over
single-stage SORT instead. "It depends" — measured, not asserted.

### H1.2 — OC-SORT (observation-centric) ✅ *done*
The first method needing **new mechanics**, not a config flag — **ORU**
(observation-centric re-update along a virtual trajectory across an occlusion
gap) + **OCM** (observed-velocity-direction consistency term). Implemented from
scratch in `tracking/motion/oc.py`, gated off by default (baseline bit-identical),
in the zoo as the `oc_sort` preset. Details → [`OC_SORT.md`](OC_SORT.md).

**Finding — an honest across-the-board negative (in this study's setting).**
OC-SORT's mechanics don't help: neutral on clean/linear synthetic motion, mildly
harmful under synthetic noise, and — on the **fair DanceTrack test** (its intended
non-linear regime) — *significantly* harmful (IDSW **+19.8, p=0.01\*** vs the
single-stage `sort` baseline). Key insight: ORU's **straight-line** virtual
trajectory poorly models non-linear dance motion, so it injects a wrong velocity
and causes switches. The component ablation also caught a real bug (naive ORU
re-init blew the covariance open, −0.058 MOTA; fixed by anchoring to the pre-gap
state → −0.009). Scoped: not a refutation of OC-SORT's paper (different detectors/
tuning). Bonus: the same DanceTrack run reproduced RQ1 (appearance cuts IDSW
−15, p<0.01\*), cross-validating the harness. Details → [`OC_SORT.md`](OC_SORT.md).

### H1.3 — Error taxonomy ✅ *done* · Camera-motion compensation (RQ4) — *queued*
- **Error taxonomy ✅** — auto-classifies each ID switch by cause (occlusion /
  crowding / fast motion) via an opt-in `on_switch` hook on the CLEAR-MOT
  accumulator, reporting each condition's *lift* over its base rate. **DanceTrack
  finding:** switches are ~**4× over-represented under fast motion** (lift 3.86×),
  while occlusion/crowding barely discriminate (so pervasive they're near base
  rate). The discriminating driver of switches is *motion*, not occlusion —
  explains why DanceTrack is hard and why motion is the lever. Details →
  [`ERROR_TAXONOMY.md`](ERROR_TAXONOMY.md). `make taxonomy`.
- **RQ4 (CMC/GMC) ✅** — from-scratch phase-correlation global motion compensation
  (translation-only, NumPy FFT; `use_gmc` gated off by default). The estimator
  recovers MOT17's known static/moving split with no priors (static seqs ~0px,
  moving 3–9px). **Finding:** GMC helps *iff* the camera moves — a strict no-op on
  static cameras (Δ=0, p=1) and a consistent improvement on moving ones (IDSW
  −6.25, IDF1 +0.021), though underpowered (n=4, p≈0.12). Details →
  [`GMC_RQ4.md`](GMC_RQ4.md). `make gmc`.

**Horizon 1 complete.**

### H1.x — Optional, resource-heavier
- Real **YOLOX** detector on DanceTrack (removes the oracle-perturbed-GT caveat).
- **SportsMOT** as a second maneuver dataset for RQ2.

---

## Horizon 2 — Make it usable (study → tool)

Today the tracker is dataset-bound. This horizon lets anyone point it at their
own video.

### H2.1 — Run on an arbitrary video ✅ *done*
`visiontrack track input.mp4 out.mp4 --model yolox_nano.onnx` — decodes the video
(imageio+ffmpeg, `[video]` extra), detects with a YOLOX ONNX model, tracks, and
writes an annotated H.264 video with per-track coloured boxes + ids. The
`track_video` pipeline is detector-agnostic (any `detect(frame)->[Detection]`),
so it's tested end-to-end over a real mp4 with a stub detector — no model in CI.
Details → [`VIDEO.md`](VIDEO.md).

### H2.2 — Real-time webcam demo + per-component profiling
Local webcam loop; report FPS per component on the M2 (honest performance numbers).

### H2.3 — Package & document
`pip install visiontrack`, a stable public API, an mkdocs API-reference site.
Turns the repo into a real library, not just a study.

---

## Horizon 3 — Product direction (the future)

Ranked by fit to the actual moat:

1. **Honest MOT benchmarking tool** *(best fit)* — plug in a tracker/detector,
   get a rigorous, significance-tested comparison + failure analysis +
   reproducible report. This is the H1 harness, productized; evaluation done
   *well* is a real gap.
2. **Teaching product** — an interactive MOT course/mini-textbook on this
   codebase + the existing study guide and roadmap (already ~60% of a curriculum).
3. **Vertical app** (retail footfall / sports / traffic) — highest ceiling, but a
   full product far from current scope; competes on detector + infra, not tracking.

**Steer away from:** productizing the NumPy tracker as a *fast production* tracker
— the one direction where it loses (speed) and abandons the moat.

---

## Quick wins (any time)
- Open-Graph / meta tags so `visiontrack.hulage.in` previews nicely when shared.
- A "reproduce in Colab" badge.

## Status
- **Horizon 1 complete** (H1.1 zoo, H1.2 OC-SORT, H1.3 error taxonomy + RQ4 GMC).
- Next: **Horizon 2** — H2.1 run on an arbitrary video.
