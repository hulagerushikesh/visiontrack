# VisionTrack — Status & Roadmap Checklist

A living checklist of what's shipped and what's planned. Tick items as they land.
Last updated: 2026-10-23 — a bounded traffic-reliability probe is planned in
[TRAFFIC_RELIABILITY_PLAN.md](TRAFFIC_RELIABILITY_PLAN.md), following a read-only
public-source pipeline inspection. Its [v1 synthetic recipe](TRAFFIC_RELIABILITY_PROTOCOL.md)
now freezes geometry, observation errors, baseline settings, scenario/seed
splits and crossing-score semantics with integrity checks before comparisons.
Its separate [input generator](TRAFFIC_RELIABILITY_GENERATOR.md) now implements
the locked recipe, with tests of all 120 development input combinations,
paired random draws, projection validity, anchor shifts and replay digests.
The [crossing scorer](TRAFFIC_RELIABILITY_SCORER.md) passes hand-checked
event/matching/window fixtures. The [development runner](TRAFFIC_RELIABILITY_RUNNER.md)
now connects generated detections to the unchanged baseline and scorer, verifies
pinned source/configuration, and checks reset/fresh replay equality. Development
smoke/fixture runs have begun. [Tracking/contact diagnostics](TRAFFIC_RELIABILITY_DIAGNOSTICS.md)
now retain canonical IoU matches, misses, FP, ID switches and fragmentation,
with independent observation errors and conditional matched-track errors,
region/pulse strata and explicit missing values. The [complete development grid](TRAFFIC_RELIABILITY_DEVELOPMENT.md)
has now run all 120 cases from committed harness `19a7c82`, retaining full results,
37 endpoint comparisons, paired differences, interactions and independently
verified bundle hashes. Box errors harmed the baseline in these toy paths;
perspective alone did not change primary count/ID outcomes. The complete
[held-out harness/input freeze](TRAFFIC_RELIABILITY_HOLDOUT.md) is now prepared
and verified from committed harness `fe88a16`, with all 120 input manifests,
19 harness/test/settings files and 57 baseline source files bound. The separate
one-pass execution gate has now completed all 120 held-out cases from `5ac67f2`
without failures or selective reruns. The [combined scoped findings](TRAFFIC_RELIABILITY_FINDINGS.md)
retain the primary perspective-only negative, severe box-error crossing failures
and mixed tracking interactions. Both bundles' hashes, complete ledgers and all
37 endpoint/contrast summaries were independently checked from saved records.
The package and parity fixtures remain unchanged.
A separate [one-switch box-gate ablation](BOX_GATE_ABLATION_PROTOCOL.md) now
registers the comparator, fresh scenario/seed sets, practical ID-switch margins
and per-case tracking/count non-regression gates before new outcomes. Its
read-only preflight and geometry checks execute no tracker comparison. The
separate [paired input generator](BOX_GATE_INPUTS.md) now checks all 120 new
development input combinations, immutable arrays, detector-only fingerprints,
and independent arithmetic/draw order, without generating new tracking outcomes.
The [development reference scorer](BOX_GATE_SCORING.md) now retains all 37
endpoints and canonical matching history, with hand-worked ID-switch, gap,
count-window, missing-value and input-integrity tests. It executes no tracker;
supplied-row scoring does not establish either variant's performance.
The [paired replay adapter](BOX_GATE_REPLAY.md) is implemented with detector-only
payload receipts, isolated one-switch configs and reset/fresh checks. Its tests
use doubles, not actual new tracker comparisons. The
[development export and numerical-rule harness](BOX_GATE_REPORT.md) now checks
full coverage, source/input/output lineage, independent re-scoring consistency,
all 37 endpoints, exact margins and every per-case regression. It retains
finished variants when a later attempt fails. Hand-worked tables/doubles test
all four outcomes. The [actual development grid and saved-record audit](BOX_GATE_DEVELOPMENT.md)
have now completed all 120 pairs / 240 variant runs / 720 passes from clean
committed harness `817e6f7`, with no errors, skipped cases or selective retries.
Gate-off removed ID switches in these fixtures but failed non-regression:
174 endpoint violations affected all 60 box-error pairs. The 60 control pairs
were unchanged across all 37 endpoints. The candidate is not accepted; the
development-only numerical summary is inconclusive by design. Both splits are
now retained and the combined interpretation is recorded below.
Independent saved-record arithmetic checked all file hashes, ledger coverage,
8,880 endpoint values, 4,440 differences, 1,332 descriptive endpoint groups
and exact rational margins. This does not independently establish raw input
geometry or canonical matching. The [held-out preparation safeguards](BOX_GATE_HOLDOUT.md)
now bind the exact committed revision, runtime, reviewed negative development
evidence and all 120 future input manifests. Preparation/verification reject drift,
forgeries, existing output directories and consumed openings; the checks re-audited the 365-file
development bundle without a tracker run. The separate held-out scorer/replay/export
and exclusive execution gate is now implemented/tested (7b), retaining partial variants and stopping on the
first error without retry. Public development split guards remain intact.
Shared-core reference scoring exactly reproduced all 24 saved development
variant records for seed 2001; no tracker was rerun for those checks.
The [actual exact freeze and once-only held-out run](BOX_GATE_HELDOUT_RESULTS.md)
now completed from clean `c99c4e7`: **120 pairs / 240 variants / 720 passes**,
with no errors, skipped cases or selective retries. A separate read-only inventory
verified all 365 files, 480 ordered ledger entries, exact settings, replay receipts,
freeze/opening lineage, 41 committed harness files and 57 baseline files.
Saved scorer endpoints show 206 safety violations in all 60 box-error pairs,
despite zero candidate ID switches; all 60 control/perspective-only pairs remain
identical across 37 endpoints. This inventory is not independent endpoint
arithmetic or a combined verdict. The opening is consumed and the candidate
remains not accepted. **Milestone 8 is now complete:** the separate
[combined audit and final findings](BOX_GATE_FINDINGS.md) check all 730 raw files,
960 ledger entries, 17,760 endpoint values, 8,880 contrasts and 2,664 descriptive
endpoint groups without a new tracker run. The unchanged development arithmetic
helpers are reused independently of the scorer, not reimplemented twice;
saved input manifests and canonical correspondence remain trusted primitives.
Separate exact rational decision checks confirm **failure**: 380 safety violations
across 120 pairs, despite the ID-switch benefit. Original indices, auditor,
freeze/opening and raw split summaries remain unchanged. No defaults/C++ adoption.
All **1,620 non-slow tests pass**, including 47 new saved-audit/table/forgery tests;
Ruff and the strict documentation build pass.
Real-data transfer and product validation remain incomplete.
The [two-project progress overview](PROGRESS_OVERVIEW.md) separates completed
foundations, all eight completed groups of this experiment and the later
real-data/product/C++ adoption gates. The subsequent
[development-only symptom diagnosis](BOX_GATE_DIAGNOSIS.md) covers all 120 saved
pairs with no new tracker runs or held-out reads. Across the 60 error pairs,
misses on frames with no public output fall from 600 to 200, but below-IoU misses
increase from 112 to 757 (total misses 712 to 957). Stable IDs do not establish
correct localization or counts. A retained solo crossing is about 15 frames early;
a shared separated-case extra crossing precedes the first imposed shape pulse.
Internal association causes remain unproven without trace data. All **1,650
non-slow tests pass**, including 30 new diagnosis tests; Ruff and strict docs pass.
The [internal tracing preparation](BOX_GATE_TRACE.md) now specifies and tests an
opt-in in-memory observer outside production. It captures actual association
matrices, forbidden masks, solver proposals, accepted matches and pre/post state,
without recalculating costs or adding Kalman updates. Authored fixtures check
exact public outputs and final state, budgets and profiler cleanup; **no saved
study trace or held-out replay has run**. All **1,695 non-slow tests pass**,
including 45 tracing tests; Ruff and the strict documentation build pass.
The [development-only provenance/replay wrapper](BOX_GATE_TRACE_REPLAY.md) now
authenticates saved evidence, source/runtime, regenerated inputs, configurations,
actual pre-update payloads and complete public outputs before allowing a sealed
complete-grid exploratory manifest. Tests exercise explicit doubles, partial
failure/interruption retention, exclusive writes and output-tampering refusal.
At that preparation checkpoint the actual trace was still pending.
All **1,739 non-slow tests pass**, including 43 new wrapper tests and an additional
observer payload-receipt test; Ruff and the strict documentation build pass.
The [new exploratory development trace](BOX_GATE_TRACE_FINDINGS.md) has now
completed from clean `dd653aa`: all **120 pairs / 240 variants**, one fresh
300-update traced pass per variant, exact saved-output parity throughout, no
errors/skips/retries or held-out data reads. A separate read-only post-run auditor
verified all 482 trace files and 365 original files, historic code/lineage and
55,578 recorded association stages over 18,526 selected frame/variant records.
Actual masks, default costs, solver proposals, acceptance and selected-frame
publication eligibility were checked; filter math/payload receipts/execution are
not independently recomputed or witnessed. Concrete traces explain startup
confirmation, a pulse-triggered 4D veto followed by a replacement confirmation
delay, and post-update same-ID anchor recrossing before a pulse. Stable identity
is not sufficient for accurate boxes/counts; the earlier failure stands.
All **1,768 non-slow tests pass**, including 29 new trace-audit diagram/forgery tests;
Ruff and strict docs pass. Raw traces stay local; a compact evidence index pins
the execution and post-run audit separately. Next choose/register a narrower
association-versus-anchor/count-stability comparison with fresh validation.
Observer records alone retain provenance/interpretation/validation flags false.
Any later intervention needs fresh validation, not rescue tuning on the consumed
held-out set. Defaults and C++ remain unchanged.

The next [counting-only confirmation-band study](CROSSING_BAND_PROTOCOL.md) is
now locally registered, not executed. Both counters will consume identical
unchanged tracker outputs. The fixed 0.25 toy-unit band is tested prospectively
against noisy counts **and** genuine shallow/return/start/end crossings, with
per-case missed/extra and timestamp/emission-window safety gates plus a 15-frame
maximum confirmation delay. Fresh development/held-out paths and seeds are
defined; no noisy inputs, tracker outcomes or old held-out bundles were opened
for this registration. Byte-integrity/scope/ideal-geometry tests are preparation,
not evidence of efficacy. The counter is now implemented as described below;
the complete guarded replay/report harness is still pending. There is no
accepted fix, production change or C++ port.
At this registration checkpoint, **1,802 non-slow tests pass** (34 new
definition/scope/ideal-geometry cases); Ruff and the strict documentation build
also pass. The prior negative findings and their frozen artifacts are unchanged.

The [isolated counter implementation](CROSSING_BAND_COUNTER.md) now retains
line-arrival and emission times separately, every pending/cancellation fate,
first-event/gap/segment semantics and late events without suppressing them.
**64 authored tests** include all 625 small four-sample diagrams for legacy
equivalence and candidate invariants. Shallow/start/end ideal passages remain
misses; a retained 18-frame delay exceeds the registered limit. These are unit
feasibility examples, not registered study outcomes or an accepted accuracy fix.
The structural review now **stops this candidate at engineering feasibility**:
do not build its full grid harness as the next task. This is not a registered
development/held-out verdict, and the original definitions/locks remain intact.
See the [decision](CROSSING_BAND_COUNTER.md#feasibility-decision-2026-10-23).
No new noisy registered inputs/tracker outcomes, held-out opening, production or
C++ changes. At this checkpoint **1,866 non-slow tests pass**; Ruff and strict
documentation build pass. The registered artifacts/locks remain unchanged.

The active delivery goal is now [one understandable diagnostic case study](SHOWCASE_MILESTONE.md),
starting with a short existing-report demo and then a permitted real clip with
checked labels. The research alpha can be demonstrated now with synthetic
evidence disclosed; real-world improvement and product demand are not established.
The proposed first audience is fixed-camera CV engineers/applied researchers.
The conditional technical estimate is 4–5 focused working days after suitable
data/labels are available; external acquisition/review delays remain separate.

The Reliability Lab now explains failures, optional
image verification, and metric trade-offs for beginners. The selective
anonymous re-entry probe can export its complete fixed-grid synthetic curves
without changing development selection or its original results. The
1,000-candidate margin rule still fails the primary synthetic risk bound.
These are usability and research foundations, not real-data validation.
The owner-selected existing-dataset route has begun with a reproducible MEVID
annotation-only intake; its source-video timing/exit truth is still unverified.
The official annotation-tool source was inspected without execution: a populated
crop-to-source mapping was not recovered, so same-session MEVID admission is on
hold. An optional local recording metadata checker now flags technical setup
issues without reading identity results or claiming constant frame timing.
A separate, plain-language recording-day guide is ready for the proposed
volunteer pilot. No recording or real-data RQ5 comparison has been performed.
The zero-to-hero and research-lead learning paths are surfaced in the React
site. `visiontrack-mot 0.3.0` remains the
published Reliability Lab technical alpha with a versioned Python/C++
synchronization boundary; the two earlier research extensions remain
**compute-blocked with measured numbers**. Previously:
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
- [x] **Published to PyPI** — `pip install visiontrack-mot` (**0.3.0** live;
      Reliability Lab release, with 0.2.0 and 0.1.0 preserved in history)
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
      detector. The shared React shell owns the accessible controls and privacy
      explanation; a mountable adapter owns media cleanup. No video is uploaded;
      track IDs are session labels rather than person identities. Node-tested logic.
- [x] "Open in Colab" reproduce notebook
- [x] Deployed to Vercel — **visiontrack.hulage.in**
- [x] Open-Graph / social meta + 1200×630 preview card
- [x] Narrative write-up page — `/writeup`
- [x] Study guide + CV roadmap (in repo)
- [x] Live routes: `/`, `/live`, `/teaching`, `/demo`, `/writeup`, `/video`, `/benchmark`, `/benchmark/dancetrack`, `/benchmark/dancetrack-yolox`, `/benchmark/sportsmot`, `/docs`
- [x] **Site UI redesign** — one shared visual system across every page, unified
      type/spacing and light-first theming, with dark reserved for tracking stages
- [x] **Two-audience teaching page — `/teaching`** — a developer lane (install, the
      real public API, what runs inside `update()`) and a plain-English lane
      (what tracking is, why it's hard, glossary) on one page
- [x] **Product-first landing** — hero leads with the product, application-domain
      use-cases, the controlled study demoted to an "under the hood" section

### Quality / infra
- [x] 560 tests passing (1 slow, opt-in) · ruff clean · CI on py3.10/3.11/3.12
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

### Product direction
- [x] H3.2 — learning product and guided curriculum
- [x] H3.3 — local-first Reliability Lab technical alpha (immutable local
      bundles, verified comparisons, evidence, decisions, synchronized playback,
      and browser acceptance workflow)
- [x] H3.3 — synthetic onboarding and browser-to-Python decision round trip:
      fresh generated reports, both human outcomes, exact file bytes, valid
      UTC calendar dates, and immutable import checked in CI
- [x] H3.3 — practitioner discovery protocol and lawful failure-evidence intake
- [x] RQ5 first protocol, event-level restore/abstain scoring, and synthetic
      held-out stress probe for galleries of 10–10,000 candidates
- [x] RQ5 metadata-only DanceTrack GT gap extraction: 1,370 candidate windows,
      a frozen 20-event duration-stratified audit sample, and no re-entry truth
      or real-data accuracy claim
- [x] RQ5 owner-local pilot preflight: pre-recording manifest validation and
      fingerprinting plus a two-reviewer event-ledger contract; no footage or
      participant records collected by these tools
- [x] RQ5 owner-local pilot CLI: strict private JSON/JSONL preflight, frozen
      fingerprint check, split-integrity validation, and aggregate-only output;
      example records are synthetic and no actual participant data was taken
- [x] RQ5 planned-take inventory: private recorded/missing/excluded slot
      reconciliation and exact event linkage, with aggregate-only gap reporting;
      declared recordings and labels still require human verification
- [x] RQ5 grouped descriptive uncertainty: participant/recording-connected
      bootstrap for future real-video scoring, with no claim of a certified
      operating-risk bound or real-data result
- [x] First-study data-source decision: preserve the DanceTrack gap audit but
      do not use its unverified gaps as re-entry truth; prioritize an
      owner-controlled, consented capture after rights and privacy review
- [ ] H3.3 — practitioner validation and initial vertical selection
- [ ] Selective anonymous identity-continuity **real-data** research under
      bounded memory and a rights-reviewed evaluation protocol
- [ ] Choose a vertical only after practitioner interviews and design-partner validation

### Sibling project (all four phases resolved)
- [x] **C++/CUDA optimized ByteTrack — Phase 1** — the port and the parity gate.
      Both trackers emit identical `(frame, track_id, box, score)` streams over
      all three MOT17-09 detector variants: 7,545 observations, zero divergences,
      tier-3 metric agreement exactly 0.0.
- [x] **Phase 2 — CPU optimization.** Five optimizations implemented and
      measured; the finding is that the parity rule ("same operations, same
      order, same rounding") forecloses most of the standard playbook, and the
      remaining headroom is small. `PHASE2.md` has the catalogue.
- [x] **Phase 4 — package + benchmark.** `visiontrack-cpp` 0.1.0 built (sdist +
      wheel, `twine check` clean, clean-venv install verified); a benchmark that
      refuses to report a ratio it has not first proved is between two identical
      computations — 100,765 observations compared bit-for-bit, 0 differences —
      and the one figure. **55–74×** on real sequences, **71–91×** synthetic.
- [x] **Cross-platform parity.** CI builds 12 wheels — CPython 3.10–3.13 on
      macOS arm64, Linux x86_64 and Windows x86_64 — and gates each on the full
      suite: **190 passed, 0 failed on every one**, against NumPy 2.2.6, 2.4.6
      and 2.5.3. Three compilers, two architectures, and **two different LAPACK
      implementations** (Accelerate and OpenBLAS). The Kalman gain is solved
      rather than inverted, so agreeing to the last bit with both is stronger
      evidence than either alone.
- [x] **Linux / Windows wheels** — done, via `cibuildwheel` + trusted
      publishing in `.github/workflows/release.yml`.
- [x] **Phase 3 — GPU: closed by measurement**, not blocked. Apple GPUs have no
      float64, so the plan's Metal alternative does not exist for a codebase
      that computes in double. And even granting a float64 GPU, Amdahl caps the
      win at 1.82× on synthetic scenes while dispatch overhead exceeds the
      *entire* gating computation on real ones — MOT17-09's median frame spends
      0.85 µs there. `PHASE3.md`, reproducible via `bench/gpu_feasibility.py`.
- [x] **Published to PyPI** — `visiontrack-cpp 0.1.0` released on 2026-09-13
      after Linux, macOS, Windows, CPython 3.10–3.13, wheel, sdist, oracle, and
      parity gates passed.

An aside worth keeping: adding CI surfaced four defects, all in the release
harness rather than the tracker — a `continue-on-error` that rewrote a failed
step's conclusion to success, MSVC misreporting `__cplusplus`, an optional test
dependency able to kill the parity gate, and a BLAS allowlist that rejected
NumPy's own official wheels. The one scare that looked like a real divergence
(three Kalman `update` tests failing by 1–2 ULP on Linux) turned out to be pip
compiling NumPy from source on a too-old base image, i.e. the oracle being
rebuilt underneath the comparison. `ci/check_oracle.py` now refuses to measure
parity against a NumPy it did not download.

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

The **C++/CUDA sibling** is finished as an engineering project. All four phases
are resolved in its own repo: 1, 2 and 4 complete, and 3 closed by measurement
rather than left blocked — Apple GPUs have no float64, and the Amdahl ceiling
plus dispatch overhead say a GPU would not have paid even with one. Parity now
holds across three platforms, three compilers and two LAPACK backends, with 12
CI-gated wheels.

The C++ package is live on PyPI. Its shared fixture, exact public-binding gate,
and machine-readable synchronization evidence are complete. Its next work is a
release compatibility matrix and deliberate toolchain maintenance, not
independent tracker research.

The local-first Reliability Lab technical alpha is now built and the versioned
Python/C++ synchronization boundary is executable and provenance-backed. The
frozen VisionTrack `0.3.0` scope, current SPDX package metadata, strict
documentation-link gate, synchronized `0.3.0` package declarations, full
candidate verification, release tag, GitHub Release, and public PyPI artifacts
are complete. The CI and release harness use current Node 24-compatible official
action majors. Next: validate the Reliability Lab with practitioners before
choosing a product vertical or expanding the platform surface.
Practitioner validation and selective anonymous identity-continuity research
remain post-candidate work in Python before any new C++ behavior is ported.
The next human-research step now has a fixed screener, interview guide,
evidence-rights intake, case template, scoring rubric, and Stage 0 decision gate
in `docs/PRACTITIONER_DISCOVERY.md`; no interview or design-partner result is
claimed until that process is actually completed.
