# VisionTrack — Status & Roadmap Checklist

A living checklist of what's shipped and what's planned. Tick items as they land.
Last updated: 2026-08-08 (HEAD `01307e0`).

---

## ✅ Done

### Core & method (the moat)
- [x] From-scratch 8-state Kalman filter (NumPy, Joseph-form, Mahalanobis gate)
- [x] From-scratch rectangular O(n³) Hungarian solver (validated vs SciPy)
- [x] ByteTrack two-stage association + Tentative→Confirmed→Deleted lifecycle FSM
- [x] From-scratch CLEAR-MOT / IDF1 / HOTA — cross-checked vs `trackeval` to 1.4e-3
- [x] Factored, gated ablation cost surface (bit-identical to `1−IoU` at zero weights)
- [x] Statistical-rigor harness (seed variance, paired bootstrap + Wilcoxon, Cohen's d, config hash)

### Research questions
- [x] **RQ1 — appearance:** MOT17 (colour-hist + deep OSNet re-ID)
- [x] RQ1 — multi-detector significance (21 seq×detector units)
- [x] RQ1 — synthetic crossover probe + descriptor-drift probe
- [x] RQ1 — DanceTrack (oracle-perturbed GT) — hypothesis refuted
- [x] RQ1 — DanceTrack (**real YOLOX detections**) — caveat removed
- [x] **RQ2 — learned motion residual:** honest negative (helps prediction, hurts tracking)
- [x] **RQ3 — calibrated uncertainty:** honest negative (loose gate is a feature)
- [x] **RQ4 — global motion compensation:** helps iff camera moves

### Horizon 1 — deepen research  *(complete)*
- [x] H1.1 — tracker zoo (significance-tested lineage)
- [x] H1.2 — OC-SORT (OCM + ORU) — honest negative
- [x] H1.3a — ID-switch error taxonomy
- [x] H1.3b — RQ4 GMC
- [x] H1.x — real YOLOX detector on DanceTrack (+ full-lineage zoo cross-check)

### Horizon 2 — make it usable  *(complete except webcam GUI)*
- [x] H2.1 — run on arbitrary video (YOLOX + `track_video` CLI)
- [x] H2.1 — real-footage annotated demo (+ YOLOX raw-grid decode fix)
- [x] H2.2 — throughput/FPS profiling
- [x] H2.3 — pip-installable + stable public API + release automation
- [x] **Published to PyPI** — `pip install visiontrack-mot` (0.1.0, live)

### Horizon 3 — product
- [x] H3.1 — honest MOT benchmarking tool (leaderboard + significance + taxonomy)
- [x] H3.1 — live on synthetic, DanceTrack (oracle), and **real-detector DanceTrack**

### Deliverables & deployment
- [x] Mini-paper README
- [x] `make reproduce` (real-data) + `make reproduce-synth` (no data)
- [x] Interactive web demo — `/demo`
- [x] "Open in Colab" reproduce notebook
- [x] Deployed to Vercel — **visiontrack.hulage.in**
- [x] Open-Graph / social meta + 1200×630 preview card
- [x] Narrative write-up page — `/writeup`
- [x] Study guide + CV roadmap (in repo)
- [x] Live routes: `/`, `/demo`, `/writeup`, `/benchmark`, `/benchmark/dancetrack`, `/benchmark/dancetrack-yolox`

### Quality / infra
- [x] 335 tests passing (1 slow, opt-in) · ruff clean · CI on py3.10/3.11/3.12
- [x] Weight-clean + imagery-clean repo · fully reproducible (config hash + seeds)

### User-only actions (cleared)
- [x] Cloudflare edge-cache freshness resolved (site serves fresh HTML)
- [x] PyPI account + Trusted Publishing + first release published

---

## 🔲 Planned / next

### Ready to build (self-contained)
- [ ] **Real-time webcam GUI** (H2.2) — live preview window over `track_webcam`
      *(code-able; can't verify headlessly here — no camera/display)*
- [x] **mkdocs documentation site** — `docs/` is a browsable Material site (`make docs`)
- [ ] **Landing page redesign** — stronger hero/typography *(optional)*
- [ ] Put the real-footage YOLOX video on the site — `/video` route
      *(deferred by you; clip is public-domain so it's hostable)*

### Research extensions (heavier)
- [ ] **SportsMOT** — second non-linear-motion dataset for RQ2 *(large download)*
- [ ] Stronger detector on DanceTrack (yolox-x) — test if it restores appearance significance

### Product direction (far)
- [ ] H3.2 — teaching product (course / mini-textbook)
- [ ] H3.3 — vertical app (retail footfall / sports / traffic)

### Sibling project (parked)
- [ ] **C++/CUDA optimized ByteTrack — Phase 1** — separate repo; needs
      `brew install eigen` + `pip install pybind11`. Phases 1–2 local (NEON);
      Phase 3 CUDA needs a cloud GPU (or a Metal path).

### Housekeeping
- [ ] Clean up the dual `visiontrack` (stale editable) + `visiontrack-mot` (wheel)
      install in the base env — `pip uninstall visiontrack && pip install -e .`

---

## Suggested priority order
1. Real-detector strengthening is done — the study is now maximally honest.
2. **Webcam GUI** — completes the "usable tool" story.
3. **`/video` route** — surface the real-footage demo already produced.
4. **mkdocs site** — polish once content is stable.
5. **SportsMOT** — the last sizeable research extension.
6. **C++/CUDA sibling** — a systems/GPU piece when the toolchain is set up.
