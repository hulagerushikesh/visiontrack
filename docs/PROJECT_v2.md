# VisionTrack v2 — When Does Appearance Help? A Controlled Study of Motion, Appearance, and Uncertainty in Online Multi-Object Tracking

> An online tracking-by-detection platform, built from first principles on NumPy,
> used to run a **rigorous, reproducible ablation study** across three real datasets
> (MOT17, DanceTrack, SportsMOT). The project's contribution is not another tracker —
> it is a **controlled measurement** of *when* the field's standard tricks (appearance
> Re-ID, learned motion, uncertainty-aware association) actually pay off, and where they
> silently hurt, reported with seed variance and significance testing.

- **Repository:** `github.com/hulagerushikesh/visiontrack`
- **Language / stack:** Python 3.10+, NumPy core. Torch (learned motion residual, offline), ONNX Runtime (detector + Re-ID inference), pytest + SciPy (tests), Hydra/OmegaConf (experiment config), pandas + matplotlib (analysis).
- **Status:** research platform; CI-green; results reproducible from a single `make reproduce`.
- **Artifacts:** (1) mini-paper README with result tables + plots, (2) deployed interactive demo, (3) reproducible benchmark that runs a named baseline and reports our delta with confidence intervals.

---

## 0. What changed from v1 (and why it matters)

VisionTrack v1 was a correct, well-tested reimplementation of Kalman + Hungarian + ByteTrack,
evaluated on a synthetic scene. That demonstrates *engineering depth* but makes no *empirical
claim* — every number is discounted because there is no real-data baseline to compare against.

v2 keeps the from-scratch core (that is the moat) and adds the thing that makes it research:
**a falsifiable question, real data, a baseline we actually run, and statistical rigor.**

| Dimension | v1 | v2 |
|---|---|---|
| Data | Synthetic oracle only | MOT17 + DanceTrack + SportsMOT (real), synthetic retained as a controlled probe |
| Claim | "It works" (asserted) | "Appearance helps iff X; motion residual helps iff Y" (measured, with CIs) |
| Baseline | None | Public ByteTrack/SORT numbers reproduced in-repo, our variants compared head-to-head |
| Appearance | Placeholder hook | Real Re-ID branch (pretrained ONNX embeddings), cosine-cost fusion, ablatable |
| Motion | Constant-velocity Kalman | CV Kalman **+ optional learned residual** (Thesis 2), head-to-head |
| Association | Fixed Mahalanobis gate | **Calibrated uncertainty-weighted** cost (Thesis 3), head-to-head |
| Rigor | Single-run ablation | N-seed runs, mean±std, paired significance test, failure-regime analysis |
| Reproducibility | CLI demo | `make reproduce` regenerates every table and figure from cached detections |

---

## 1. Research questions (the spine)

The project answers three questions the tracking literature tends to assert rather than measure.

**RQ1 — Appearance (the main thesis).**
> Under what conditions does an appearance (Re-ID) association cost improve tracking, and
> under what conditions does it *degrade* it?

Hypothesis: appearance helps monotonically with (a) inter-object appearance diversity and
(b) occlusion duration, but **hurts** when objects are near-identical (uniformed teams, dancers),
because the embedding contributes noise that competes with a reliable motion prior. We predict a
measurable crossover as a function of crowd density × appearance similarity, and we expect the
sign of appearance's contribution to **flip between MOT17 (helps) and DanceTrack (hurts).**

**RQ2 — Learned motion residual.**
> Does a small learned residual on top of the constant-velocity Kalman prediction reduce identity
> switches during abrupt maneuvers, at acceptable latency?

Hypothesis: yes on SportsMOT/DanceTrack (non-linear motion), negligibly on MOT17 (near-linear
pedestrian motion). This directly attacks v1's stated failure mode.

**RQ3 — Calibrated uncertainty-aware association.**
> Does propagating calibrated Kalman uncertainty into the *full* association cost (not just a
> hard gate) reduce IDSW under high detector noise versus a fixed-threshold gate?

Hypothesis: yes under high FP/FN regimes; marginal under clean detections. Tests whether the
filter's own covariance is *calibrated* enough to trust as a soft weight.

The value is the same whichever way each result falls: a controlled study that shows appearance
*hurts* on DanceTrack is a contribution, not a failure.

---

## 2. System architecture (v2)

The v1 strict-layering core is preserved. New modules are additive and independently ablatable
so every experiment toggles one variable.

```
┌──────────────────────────────────────────────────────────────────────┐
│ experiments/   Hydra configs · run_matrix.py · analyze.py (tables/figs)│
├──────────────────────────────────────────────────────────────────────┤
│ cli.py         demo · eval · ablate · reproduce   (argparse/Hydra)     │
├──────────────────────────────────────────────────────────────────────┤
│ serve/         stream_service.py  (batched inference, latency SLO)     │  optional
├──────────────────────────────────────────────────────────────────────┤
│ viz/           draw.py · webdemo/  (deployed interactive demo)         │  optional
├──────────────────────────────────────────────────────────────────────┤
│ eval/          mot.py (CLEAR-MOT) · hota.py (HOTA/IDF1) · stats.py     │
│                                     (seeds, paired tests, bootstrap CI)│
├──────────────────────────────────────────────────────────────────────┤
│ tracking/      tracker.py (association orchestrator)                    │
│                cost.py    (IoU ⊕ appearance ⊕ uncertainty — ablatable) │
│                motion/    kalman.py · residual.py (learned, optional)  │
│                track.py (FSM) · config.py (typed)                      │
├──────────────────────────────────────────────────────────────────────┤
│ appearance/    reid_onnx.py (pretrained embedder) · gallery.py (EMA)   │
├──────────────────────────────────────────────────────────────────────┤
│ detection/     base.py · mot_loader.py (real datasets + public dets)  │
│                onnx_yolo.py · synthetic.py (controlled probe)          │
├──────────────────────────────────────────────────────────────────────┤
│ core/          geometry.py · kalman.py · assignment.py  ← from-scratch │
├──────────────────────────────────────────────────────────────────────┤
│ data/          cache/  (detections + Re-ID embeddings, computed once)  │
└──────────────────────────────────────────────────────────────────────┘
```

**Key design idea — compute once, experiment cheaply.** Detection and Re-ID embedding are the
only GPU-hungry steps. They run *once per dataset* and serialize to `data/cache/`. Every tracking
experiment then reads cached `(boxes, scores, embeddings, gt)` and runs **CPU-only in seconds**,
so the full N-seed × 3-thesis × 3-dataset matrix is tractable on a laptop.

---

## 3. The association cost — the ablation surface

All three theses reduce to *what goes into the cost matrix* that Hungarian minimizes. v2 factors
the cost so each term is a config flag:

```
cost(track_i, det_j) =  w_iou · (1 − IoU_or_GIoU)                     # v1 motion/shape
                      ⊕ w_app · (1 − cosine(emb_i, emb_j))            # RQ1 appearance
                      ⊕ w_unc · mahalanobis_soft(track_i, det_j)      # RQ3 uncertainty
   subject to  Mahalanobis gate (hard)  and  motion from  Kalman  or  Kalman+residual (RQ2)
```

- **Appearance term** — a per-track appearance gallery updated by EMA of matched-detection
  embeddings (DeepSORT-style), cosine distance to candidate detections. Pretrained OSNet/FastReID
  ONNX embedder; **no training required**, embeddings cached per dataset.
- **Uncertainty term** — instead of only *gating* on Mahalanobis distance, fold a calibrated,
  normalized Mahalanobis distance directly into the cost with weight `w_unc`. Calibration checked
  by a reliability diagram (are 95%-gated innovations actually χ²-distributed?).
- **Learned motion** — `motion/residual.py` predicts a small correction to the CV Kalman mean
  before association; a tiny GRU/MLP trained offline on GT trajectories, exported to ONNX, run on
  CPU at inference. Ablatable to exactly isolate its contribution.

Every weight and every branch is a Hydra config field, so a run is fully specified by its config
hash — which is what makes the study reproducible and the ablations honest.

---

## 4. Evaluation & statistical rigor (the part that makes it "research")

v1 reported single-run CLEAR-MOT. v2 adds the machinery a reviewer looks for.

- **Metrics:** CLEAR-MOT (MOTA/MOTP/IDSW/MT/ML) **plus HOTA and IDF1** — HOTA is the modern
  standard because MOTA over-weights detection and under-weights association; IDF1 measures
  identity consistency directly. From-scratch or via `trackeval` with our numbers cross-checked.
- **Seed variance:** every configuration run over N seeds (detector NMS jitter / stochastic
  components), reported as **mean ± std**, never a single number.
- **Significance:** paired comparison (same sequences, same seeds) between a variant and its
  baseline via a **paired bootstrap / Wilcoxon signed-rank** test; report p-values and effect size.
- **Failure-regime analysis:** stratify results by occlusion duration, crowd density, and camera
  motion, so RQ1's crossover is *shown as a curve*, not claimed. This is the money figure.
- **Baseline reproduction:** we run SORT and ByteTrack (our from-scratch versions) end-to-end on
  the same cached detections and confirm we land in the neighborhood of published numbers, so the
  comparison is apples-to-apples and self-contained.

---

## 5. Datasets & the GPU-optional plan

| Dataset | Role in the study | Why |
|---|---|---|
| **MOT17** | Appearance-*helps* case | Pedestrians, diverse appearance; ships **public detections** (DPM/FRCNN/SDP) so trackers compare without a detector confound |
| **DanceTrack** | Appearance-*hurts* case | Near-identical outfits + heavy non-linear motion — the crossover that makes RQ1 interesting |
| **SportsMOT** | Maneuver-heavy case | Fast erratic motion; stresses RQ2's learned residual |
| synthetic (v1) | Controlled probe | The only place we can *dial* occlusion/noise continuously to trace RQ1's curve cleanly |

**GPU is optional.** Detection uses MOT17's public detections (no detector needed) or a one-time
YOLOX/YOLOv8 ONNX pass; Re-ID uses a **pretrained** ONNX embedder (no training). Both run once and
cache. GPU is only nice-to-have for (a) faster embedding extraction and (b) training the small RQ2
residual — both fit comfortably in free Colab. The core research loop is CPU-only.

Start on **MOT17 train** (local GT via a fixed train/val split), get everything green, then add
DanceTrack and SportsMOT. Portfolio evaluation uses train/val splits with seed variance — more
rigorous for an ablation than a single test-server submission.

---

## 6. Deliverables (all three artifacts)

1. **Mini-paper README** — abstract, RQ statements, method, result tables (mean±std, p-values),
   the RQ1 crossover figure, honest limitations. Reads like a short paper.
2. **Deployed interactive demo** — upload/select a clip, toggle appearance/residual/uncertainty
   live, watch IDSW change. Makes the thesis tangible in 10 seconds. (Static-hosted; inference
   pre-baked or lightweight.)
3. **Reproducible benchmark** — `make reproduce` runs the full matrix from cached detections and
   regenerates every table and figure; CI runs a smoke subset as a regression gate.

---

## 7. Design decisions & trade-offs (v2 additions)

| Decision | Rationale | Trade-off |
|---|---|---|
| Study, not a new SOTA tracker | A well-run controlled result can't be "wrong"; far more defensible than a fragile SOTA claim | Less flashy headline than "beats X by N points" |
| Cache detections + embeddings | Makes the N-seed×3-thesis×3-dataset matrix CPU-tractable | Upfront one-time GPU pass; cache storage |
| Pretrained Re-ID, no training | Removes the biggest GPU dependency; isolates the *association* question from embedder quality | Can't claim a novel embedder (not the point) |
| Train/val splits + seed variance | Rigorous, self-contained, no eval-server dependency | Numbers aren't directly comparable to test-leaderboard |
| HOTA/IDF1 alongside MOTA | Modern association-aware evaluation | More metric plumbing |
| Keep from-scratch NumPy core | The depth moat; still the thing that separates this from a wrapper | More code than importing a tracker |

---

## 8. Limitations (stated up front — reviewers trust honesty)

- Train/val evaluation, not test-server leaderboard numbers (deliberate, for reproducibility).
- Pretrained embedder means embedder quality is a fixed confound, not a studied variable.
- Constant-velocity + small residual is still a short-horizon motion model.
- Three datasets is a sample, not the universe; claims are scoped to the studied regimes.

---

## 9. One-line summary

VisionTrack v2 keeps the from-scratch Kalman/Hungarian/ByteTrack core of v1 and turns it into a
reproducible research platform that measures — on MOT17, DanceTrack, and SportsMOT, with seed
variance and significance testing — *when* appearance, learned motion, and uncertainty-aware
association actually help online multi-object tracking, and where they quietly hurt.
