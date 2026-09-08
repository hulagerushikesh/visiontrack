# VisionTrack — Status & Roadmap Checklist

A living checklist of what's shipped and what's planned. Tick items as they land.
Last updated: 2026-09-08 — the two remaining research extensions are now marked
**compute-blocked with measured numbers**, not merely "planned". Previously:
2026-09-07, SportsMOT oracle numbers landed (45 val sequences, `/benchmark/sportsmot`
live); v0.2.0 (`/live` in-browser tracker + SportsMOT code path + site redesign,
published to PyPI).

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

### Horizon 2 — make it usable  *(complete)*
- [x] H2.1 — run on arbitrary video (YOLOX + `track_video` CLI)
- [x] H2.2 — run on a live camera (`visiontrack webcam` — real-time preview + FPS)
- [x] H2.1 — real-footage annotated demo (+ YOLOX raw-grid decode fix)
- [x] H2.2 — throughput/FPS profiling
- [x] H2.3 — pip-installable + stable public API + release automation
- [x] **Published to PyPI** — `pip install visiontrack-mot` (**0.2.0** live; 0.1.0 first cut)
      via tag-triggered Trusted-Publishing Action; GitHub Release page per tag

### Horizon 3 — product
- [x] H3.1 — honest MOT benchmarking tool (leaderboard + significance + taxonomy)
- [x] H3.1 — live on synthetic, DanceTrack (oracle), and **real-detector DanceTrack**

### Deliverables & deployment
- [x] Mini-paper README
- [x] `make reproduce` (real-data) + `make reproduce-synth` (no data)
- [x] Interactive web demo — `/demo`
- [x] **Live in-browser tracker — `/live`** — the from-scratch association (8-state
      Kalman + O(n³) Hungarian + ByteTrack + lifecycle) ported to JavaScript
      (`assets/tracker.js`), run on-device over webcam or a sample clip via a COCO-SSD
      detector. No video committed; nothing leaves the browser. Node-tested logic.
- [x] "Open in Colab" reproduce notebook
- [x] Deployed to Vercel — **visiontrack.hulage.in**
- [x] Open-Graph / social meta + 1200×630 preview card
- [x] Narrative write-up page — `/writeup`
- [x] Study guide + CV roadmap (in repo)
- [x] Live routes: `/`, `/live`, `/teaching`, `/demo`, `/writeup`, `/video`, `/benchmark`, `/benchmark/dancetrack`, `/benchmark/dancetrack-yolox`, `/benchmark/sportsmot`, `/docs`
- [x] **Site UI redesign** — one shared stylesheet across every page, unified type/
      spacing/light-dark theming, live tracking hero on the landing page
- [x] **Two-audience teaching page — `/teaching`** — a developer lane (install, the
      real public API, what runs inside `update()`) and a plain-English lane
      (what tracking is, why it's hard, glossary) on one page
- [x] **Product-first landing** — hero leads with the product, application-domain
      use-cases, the controlled study demoted to an "under the hood" section

### Quality / infra
- [x] 349 tests passing (1 slow, opt-in) · ruff clean · CI on py3.10/3.11/3.12
- [x] Batched Kalman hot path — per-frame predict + Mahalanobis gating run as one
      `(N, 8)` NumPy call over the whole track set: ~1.4–1.5× faster, bit-identical
      (2841 → 294 FPS across 4–64 objects; MOTA/IDSW unchanged)
- [x] Weight-clean + imagery-clean repo · fully reproducible (config hash + seeds)

### User-only actions (cleared)
- [x] Cloudflare edge-cache freshness resolved (site serves fresh HTML)
- [x] PyPI account + Trusted Publishing + first release published

---

## 🔲 Planned / next

### Ready to build (self-contained)
- [x] **Real-time webcam CLI** (H2.2) — `visiontrack webcam` runs the tracker on a
      live camera with an optional OpenCV preview, mirror, and real FPS readout.
      Frame source is injectable, so the whole detect→track→draw loop is tested
      headlessly; only the literal camera + preview window need real hardware.
- [x] **mkdocs documentation site** — `docs/` is a browsable Material site (`make docs`),
      built on Vercel and **live at visiontrack.hulage.in/docs**
- [x] **Landing page redesign** — stronger hero/typography — shared-CSS redesign +
      live tracking hero shipped in v0.2.0
- [x] Put the real-footage YOLOX video on the site — **live at `/video`**
      (public-domain Bangkok-traffic clip; 300 frames, 107 tracks, ~1.8 MB mp4)

### Research extensions (heavier)
- [x] **SportsMOT (oracle protocol)** — second non-linear-motion dataset for RQ2.
      Dataset downloaded and verified (45 val sequences / 26,970 frames, each
      sequence's frame count checked against its `seqinfo.ini`), caches + OSNet
      embeddings built, leaderboard live at **`/benchmark/sportsmot`**.
      With appearance informative, re-ID turns significant on all four metrics
      (−7.13 IDSW, p<0.05) — but a *smaller* ID-switch win than DanceTrack's
      −15.3, and motion carries a 1.31× switch lift on a 6.6% base rate.
      Results → [`/benchmark/sportsmot`](https://visiontrack.hulage.in/benchmark/sportsmot).
- [ ] SportsMOT **real-detector** pass (`--detector-model`) — the oracle protocol
      isolates association; this adds detector quality to the measurement.
      **Blocked on compute, not on code or data.** At the yolox-x rate measured
      below, the 45-sequence val split (26,970 frames) is ~11.7 h of sustained
      multi-core inference — not viable on this laptop. Needs a rented GPU box, or
      a pre-registered subset small enough to finish in one supervised sitting.
- [ ] Stronger detector on DanceTrack (yolox-x) — test if it restores appearance
      significance. **Attempted 2026-09-07, abandoned — see below.** Two findings
      worth keeping even though no numbers shipped:
      1. **Cost.** `yolox_x.onnx` measured **1.40–1.62 s/frame** at 640×640 on this
         machine (~350–390% CPU). A 7-sequence subset (8,920 frames) is ~3.9 h of
         pure compute; the run was killed at 3/7 after ~14.5 h of wall clock,
         because the machine slept and thermally throttled overnight.
      2. **Confound.** `yolox_x.onnx` has a fixed 640×640 input, while the shipped
         nano cache was built at 416. Model capacity and input resolution therefore
         change together, so any accuracy delta could not be attributed to the
         detector alone. A clean version of this experiment needs the nano
         re-run at 640, doubling an already-infeasible budget.
      Verdict: **not worth the compute** as specified. The claim it was meant to
      test — that a stronger detector restores appearance significance — is already
      answered more cheaply by SportsMOT, where appearance is informative *by
      construction* rather than by upgrading the detector.

### Product direction (far)
- [ ] H3.2 — teaching product (course / mini-textbook)
- [ ] H3.3 — vertical app (retail footfall / sports / traffic)

### Sibling project (parked)
- [ ] **C++/CUDA optimized ByteTrack — Phase 1** — separate repo; needs
      `brew install eigen` + `pip install pybind11`. Phases 1–2 local (NEON);
      Phase 3 CUDA needs a cloud GPU (or a Metal path).

### Housekeeping
- [x] Cleaned up the dual `visiontrack` + `visiontrack-mot` install in the base env.
      Both stale 0.1.0 distributions were shadowing the repo, so `import visiontrack`
      resolved to a **0.1.0 wheel in site-packages** rather than the source. Now a
      single editable `visiontrack-mot 0.2.0` resolving to `src/visiontrack/`.
- [x] `ruff check .` is clean again (newer ruff lints notebooks; the Colab cells'
      long lines are whole shell commands, so `notebooks/*.ipynb` ignores E501).

---

## What is actually left

Everything that can be finished without a large download is **done**: the research
questions (RQ1–RQ4), both usability horizons, the benchmarking tool, the site
(`/live`, `/teaching`, product-first landing), the PyPI release, 349 passing tests,
clean lint, and a clean local install.

**SportsMOT is done under the oracle protocol** — the dataset is on disk and verified,
and `/benchmark/sportsmot` is live. What is left there is the real-detector pass, which
is compute, not a blocker.

The remaining research item is **gated on compute, no longer on downloads** — the data
and weights this repo deliberately does not carry (weight-clean / imagery-clean by
design) have now been fetched locally:

| Item | State | What it needs |
|---|---|---|
| **SportsMOT real detector** (RQ2) | dataset + oracle caches on disk | a `precompute_sportsmot.py --detector-model` pass over 26,970 frames, then a second leaderboard labelled `sportsmot (real YOLOX)` |
| **yolox-x on DanceTrack** (RQ1) | weights **and** raw frames both on disk now | re-run `precompute_dancetrack.py --detector-model models/yolox_x.onnx` (hours; a 7-sequence subset gives a directional read first) |

Deliberately parked: the **C++/CUDA sibling** (separate repo; eigen + pybind11 now
installed locally, held pending a plan).

Next after this: **Horizon 3 product direction** (H3.2 teaching product / H3.3
vertical app) — the site already seeds both with `/teaching` and the use-case section.
