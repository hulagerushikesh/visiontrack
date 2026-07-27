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

**Finding (synthetic scope):** OC-SORT's mechanics don't help here — neutral on
clean/linear motion (Kalman already suffices), mildly harmful under high
observation noise (MOTA −0.010, p<0.01). The component ablation also caught a real
bug (a naive ORU re-init blew the covariance open, −0.058 MOTA; fixed by anchoring
to the pre-gap state → −0.009). The regime OC-SORT is *designed* for — non-linear
motion with clean detections — needs real data; **DanceTrack is the fair test**,
queued.

### H1.3 — Camera-motion compensation (RQ4) + error taxonomy
- **RQ4:** add global motion compensation (GMC, BoT-SORT's key idea) and ask
  *when does it help?* — a genuinely new research question, strongest on
  moving-camera sequences.
- **Error taxonomy:** auto-classify each ID switch by cause (occlusion /
  crowding / fast motion) → the "money figure" that turns numbers into insight.

### H1.x — Optional, resource-heavier
- Real **YOLOX** detector on DanceTrack (removes the oracle-perturbed-GT caveat).
- **SportsMOT** as a second maneuver dataset for RQ2.

---

## Horizon 2 — Make it usable (study → tool)

Today the tracker is dataset-bound. This horizon lets anyone point it at their
own video.

### H2.1 — Run on an arbitrary video
`visiontrack track input.mp4 --out annotated.mp4` with a real ONNX detector
(the biggest usability unlock — no "my own video" path exists today). A clean
`Tracker` façade API for library use.

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
- H1.1 — done. H1.2 (OC-SORT) — done. Next: H1.3 (CMC/RQ4 + error taxonomy).
