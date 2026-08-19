# VisionTrack — Technical Project Document

> Online multi-object tracking, built from first principles on NumPy.
> Kalman filtering, Hungarian assignment, and ByteTrack-style association
> implemented from scratch — not delegated to a library — and validated
> end-to-end with from-scratch CLEAR-MOT metrics and a 182-test suite.

- **Repository:** `github.com/hulagerushikesh/visiontrack`
- **Language / stack:** Python 3.10+, NumPy (core). Optional: matplotlib + Pillow (viz), onnxruntime (real detector), pytest + SciPy (tests).
- **Status:** complete, CI-green (Python 3.10 / 3.11 / 3.12 + ruff lint).
- **Lines of substance:** ~1.5k src, ~180 tests.

---

## 1. Overview

A detector (e.g. YOLO) tells you *what is in a single frame*, but has **no
memory** across frames. **Multi-object tracking (MOT)** adds that memory: it
assigns every object a **stable identity** that persists across an entire
video, surviving detector noise, missed detections, false positives, and
objects crossing paths.

VisionTrack is a **tracking-by-detection** system — the tracking stage only.
It is deliberately decoupled from the detector, so any source of per-frame
boxes plugs in behind a small interface. The emphasis of the project is that
the three hard algorithms are **owned and tested**, not imported:

| Discipline | Realized as |
|---|---|
| Probabilistic state estimation | An 8-state constant-velocity **Kalman filter** with height-scaled noise, Joseph-form updates, and Mahalanobis gating |
| Combinatorial optimization | A rectangular **O(n³) Hungarian** (Kuhn–Munkres, dual-potential) solver, validated against SciPy |
| Robust data association | **ByteTrack** two-stage matching that recovers occluded objects from low-confidence detections |
| Software architecture | Clean layering, typed configs, a structural `Detector` protocol, zero ML-framework deps in the core |
| Evaluation rigor | From-scratch **CLEAR-MOT** metrics (MOTA / MOTP / IDSW / MT / ML) and an ablation harness |

---

## 2. Problem statement

Given a stream of frames, each yielding a set of detection boxes with
confidence scores, produce for every frame a set of **(track_id, box)** pairs
such that:

1. Each real-world object receives exactly one `track_id` for its whole life.
2. That id does not change (no **identity switches**), even when the object is
   briefly undetected or passes close to another object.
3. Spurious detections do not spawn lasting identities.
4. The output is produced **online** (causally, one frame at a time) and in
   **real time**.

Failure is measured, not asserted — see §7 (Evaluation).

---

## 3. System architecture

Strict layering; each layer depends only on the ones below it.

```
┌─────────────────────────────────────────────────────────────┐
│ cli.py           demo · eval · ablate   (argparse entrypoint)│
├─────────────────────────────────────────────────────────────┤
│ viz/       draw.py         trajectory plot + GIF (matplotlib)│  optional
├─────────────────────────────────────────────────────────────┤
│ eval/      mot.py          CLEAR-MOT accumulator + metrics   │
├─────────────────────────────────────────────────────────────┤
│ tracking/  tracker.py      ByteTracker (predict→assoc→update)│
│            track.py        Track lifecycle FSM               │
│            config.py       TrackerConfig (typed, validated)  │
├─────────────────────────────────────────────────────────────┤
│ detection/ base.py         Detection + Detector protocol     │
│            synthetic.py     scene simulator / eval oracle    │
│            onnx_yolo.py     optional real YOLO backend       │
├─────────────────────────────────────────────────────────────┤
│ core/      geometry.py     box formats, IoU, GIoU           │
│            kalman.py        8-state constant-velocity filter  │
│            assignment.py    Hungarian solver + gated associate│
└─────────────────────────────────────────────────────────────┘
        core depends only on NumPy — no ML framework anywhere
```

**Per-frame data flow:**

```
                 ┌─────────────┐   detections (this frame)
   tracks ──────►│   PREDICT   │        │
   (Kalman       │  advance KF │        ▼
    state)       └─────┬───────┘   split by confidence
                       │            ┌──────────┴──────────┐
                       ▼          high-score          low-score
              ┌──────────────────┐   │                    │
              │  STAGE 1 assoc.  │◄──┘  IoU cost + Mahalanobis gate
              │  (confirmed ×    │
              │   high-score)    │──unmatched tracks──┐
              └────────┬─────────┘                    ▼
                       │                    ┌──────────────────┐
                 matched updates            │  STAGE 2 assoc.  │
                       │                    │  recover with    │
                       ▼                    │  low-score dets  │
              ┌──────────────────┐          └────────┬─────────┘
              │ create / delete  │◄──unmatched high───┘
              │  (lifecycle FSM) │
              └──────────────────┘
```

---

## 4. Core algorithms

### 4.1 Bounding-box geometry (`core/geometry.py`)

Four interchangeable box representations, with vectorized conversions:

| Format | Meaning | Primary use |
|---|---|---|
| `xyxy` | (x1, y1, x2, y2) corners | detectors, IoU, drawing |
| `xywh` | corner + size | COCO-style detectors |
| `cxcywh` | centre + size | general |
| `xyah` | centre + **aspect ratio** `w/h` + height | Kalman measurement space |

`xyah` is the Kalman measurement space because **aspect ratio is more stable
than width** under scale change. `iou_matrix` and `giou_matrix` compute all
`(N, M)` pairwise overlaps with NumPy broadcasting (no Python loops). GIoU is
distance-aware — it keeps a useful gradient even for disjoint boxes.

### 4.2 Kalman filter (`core/kalman.py`)

An optimal recursive Bayesian estimator for a linear-Gaussian system. It
tracks a **distribution** (mean + covariance), not just a point.

**State (8-dim), constant-velocity model:**
```
x = [cx, cy, a, h, ċx, ċy, ȧ, ḣ]        P = 8×8 covariance (uncertainty)
     └─ position (4) ─┘└ velocity (4) ┘
```

**Predict** (advance one frame — uncertainty grows):
```
x' = F·x
P' = F·P·Fᵀ + Q          F: position += velocity;  Q: process noise
```

**Update** (correct with matched detection z — uncertainty shrinks):
```
S = H·P·Hᵀ + R           innovation covariance  (H: state → measurement)
K = P·Hᵀ·S⁻¹             Kalman gain  (balances prediction vs measurement)
y = z − H·x              innovation
x ← x + K·y
P ← (I−KH)·P·(I−KH)ᵀ + K·R·Kᵀ     Joseph form
```

Three deliberate engineering choices:

1. **Height-scaled noise** — process/measurement std devs are proportional to
   object height, making the filter effectively scale-invariant (near vs far
   objects move different pixel amounts per frame).
2. **Joseph-form covariance update** (+ forced symmetry) — keeps `P` symmetric
   positive-definite under floating-point error, where the naive `(I−KH)P`
   form can diverge.
3. **Mahalanobis gating** — association distance is
   `d² = yᵀ·S⁻¹·y` (via Cholesky), weighted by the filter's own uncertainty,
   and rejected above the **95% chi-square** threshold (9.49 for dof=4). New /
   long-occluded tracks (large `S`) automatically get a wider search radius.

The filter is **stateless and batched**: one shared instance advances all N
tracks with `(N,8)` / `(N,8,8)` matrix ops.

### 4.3 Hungarian assignment (`core/assignment.py`)

Data association is a **minimum-cost bipartite matching**: given
`cost[i][j] = 1 − IoU(track_i, det_j)`, find the one-to-one assignment with
minimum total cost. Greedy matching is provably sub-optimal; the Hungarian
algorithm is optimal.

- **`linear_assignment(cost)`** — O(n³) Kuhn–Munkres / shortest-augmenting-path
  variant with **dual potentials** `u, v` maintaining reduced costs ≥ 0. Handles
  **rectangular** matrices directly (transpose tall ones; no big-M padding).
- **`associate(cost, max_cost)`** — wraps the solver with **gating**: rejects
  matched pairs above `max_cost`, returns `(matches, unmatched_rows,
  unmatched_cols)`.

Correctness is guaranteed by test, not by trust: the solver is checked against
`scipy.optimize.linear_sum_assignment` on **150 random matrices** (varied
shapes, negative costs) for identical optimal cost.

### 4.4 ByteTrack two-stage association (`tracking/tracker.py`)

Objects under partial occlusion often survive only as **low-confidence**
detections. Discarding them (as plain SORT does) is exactly when identities are
lost. ByteTrack keeps them for a second pass:

- **Stage 1** — confirmed tracks × **high-score** detections (IoU + Mahalanobis
  gate). The easy, high-quality matches.
- **Stage 2** — tracks unmatched in stage 1 × **low-score** detections. The
  recovery mechanism; the single biggest win over SORT.
- **Stage 3** — tentative (unconfirmed) tracks × leftover high-score detections
  only, so noise cannot bootstrap a stable identity.

Leftover high-score detections above `new_track_thresh` spawn new tracks;
tracks unmatched everywhere are marked missed.

### 4.5 Track lifecycle FSM (`tracking/track.py`)

```
   new detection
        │
        ▼
   ┌─────────┐  matched n_init (=3) times   ┌───────────┐
   │TENTATIVE│ ───────────────────────────► │ CONFIRMED │
   └────┬────┘                              └─────┬─────┘
        │ missed once                             │ missed > max_age (=30)
        ▼                                         ▼
   ┌─────────┐                              ┌─────────┐
   │ DELETED │                              │ DELETED │
   └─────────┘                              └─────────┘
```

- **Confirmation delay (`n_init`)** rejects one-frame false positives.
- **Coasting (`max_age`)** lets a confirmed track survive occlusion on the
  Kalman prediction and reclaim its id on reappearance.
- Only confirmed tracks matched *this* frame are emitted — no flicker, no ghosts.

---

## 5. Detection layer

The tracker consumes anything satisfying the `Detector` **protocol**:

```python
class Detector(Protocol):
    def detect(self, frame) -> list[Detection]: ...
```

- **`OnnxYoloDetector`** — optional YOLOv8-family ONNX backend: letterbox
  preprocessing, output-layout auto-detection, coordinate un-mapping,
  from-scratch NMS, class filtering. `onnxruntime` imported lazily.
- **`SyntheticScene`** — a deterministic scene simulator that is also the
  **evaluation oracle**. Objects move on smooth trajectories; a virtual
  detector observes them through a configurable noise model (localization
  jitter, misses, Poisson false positives, and **occlusion that degrades a box
  to low confidence** rather than dropping it — the regime where stage-2
  recovery matters). Emits both detections and ground truth; seeded → fully
  reproducible; needs no downloads.

---

## 6. Evaluation (`eval/mot.py`)

From-scratch **CLEAR-MOT** metrics:

| Metric | Definition |
|---|---|
| **MOTA** | `1 − (FN + FP + IDSW) / GT` — overall accuracy |
| **MOTP** | mean IoU of true-positive matches — localization quality |
| **IDSW** | identity switches |
| **MT / PT / ML** | trajectories tracked >80% / in-between / <20% of their life |

The per-frame matcher follows CLEAR-MOT precisely: it **preserves valid
existing correspondences** before Hungarian-matching the remainder — the step
that makes IDSW meaningful (crossings don't register false switches). The code
is dataset-agnostic (works unchanged on MOT17 ground truth).

---

## 7. Results

**Accuracy** (`visiontrack eval`, 6 objects, 120 frames, with noise):

```
MOTA=0.902  MOTP=0.919  IDSW=0  FP=0  FN=54  precision=1.000  recall=0.902  MT=6 ML=0
```

**Throughput** (`benchmarks/bench_tracker.py`, CPU, single-threaded):

| objects | avg dets/frame | mean ms | p95 ms | FPS | MOTA | IDSW |
|--------:|---------------:|--------:|-------:|----:|-----:|-----:|
| 4  | 3.1  | 0.35 | 0.49 | 2841 | 0.892 | 0 |
| 8  | 4.9  | 0.55 | 0.93 | 1804 | 0.902 | 0 |
| 16 | 7.9  | 0.87 | 1.51 | 1145 | 0.900 | 0 |
| 32 | 13.5 | 1.34 | 2.72 |  748 | 0.893 | 0 |
| 64 | 27.9 | 3.40 | 7.34 |  294 | 0.889 | 0 |

Real-time (≥30 FPS) up to 64 concurrent objects. The per-frame Kalman predict and
Mahalanobis gating run as batched `(N, 8)` NumPy calls over the whole track set
(~1.4–1.5× faster than the per-track loop, bit-for-bit identical — MOTA/IDSW
unchanged above).

**Ablation** (`visiontrack ablate`, crowded 16-object stress scene):

```
variant                         MOTA    MOTP   IDSW     FP     FN
----------------------------------------------------------------
full (bytetrack + gating)      0.865   0.917      0      0    153
no low-score recovery          0.860   0.918      0      0    159   ← +6 misses
no Mahalanobis gating          0.865   0.916      1      0    152   ← +1 ID switch
class-agnostic                 0.865   0.917      0      0    153
```

The harness reports the honest, scene-dependent contribution of each component
rather than a cherry-picked number; on easy scenes these effects shrink.

---

## 8. Testing & CI

~180 checks across four kinds:

- **Unit** — geometry conversions, IoU edge cases, MOT counters.
- **Property** — the custom Hungarian must reach SciPy's optimal cost on 150
  random matrices.
- **Convergence** — the Kalman filter recovers true velocity from noisy
  constant-velocity measurements; covariance grows on predict, shrinks on
  update, stays symmetric.
- **Integration** — end-to-end on the synthetic scene, asserting a MOTA floor
  and an ID-switch ceiling (a genuine regression gate).

**CI** (`.github/workflows/ci.yml`) runs the suite on Python 3.10 / 3.11 / 3.12
plus CLI smoke tests, with a separate ruff lint job.

---

## 9. How to use it

```bash
pip install -e ".[dev]"                     # core + tests + viz

# programmatic
from visiontrack import ByteTracker, TrackerConfig, Detection
tracker = ByteTracker(TrackerConfig())
for frame_dets in stream:                    # list[Detection]
    for obs in tracker.update(frame_dets):
        print(obs.track_id, obs.xyxy, obs.score)

# CLI (runs on the built-in synthetic scene — nothing to download)
visiontrack demo  --plot traj.png --gif out.gif
visiontrack eval  --json
visiontrack ablate
```

Real video: swap in `OnnxYoloDetector("yolov8n.onnx", class_filter={0})` and
feed `detector.detect(frame)` into `tracker.update(...)`.

---

## 10. Design decisions & trade-offs

| Decision | Rationale | Trade-off |
|---|---|---|
| Own the Kalman/Hungarian/association math | Demonstrates depth; fully testable; no black boxes | More code than importing a tracker |
| Motion-only association (no appearance) | Fast, robust at normal frame rates | Long same-class occlusions can swap ids |
| Constant-velocity model | Correct for short horizons; simple, stable | Abrupt maneuvers over long gaps fail (bounded by `max_age`) |
| NumPy-only core | Trivial install, portable, fast enough for real time | No GPU acceleration of the tracker itself |
| Synthetic benchmark | Reproducible, zero-download, doubles as oracle | Not a substitute for real-data numbers |

---

## 11. Limitations & roadmap

**Current limitations**
- No appearance re-identification — the `Detection.feature` field and the
  `_match` cost hook are the intended extension points (DeepSORT-style).
- Linear motion only; abrupt maneuvers during long occlusions are the known
  failure mode.
- Evaluation is synthetic (though the metrics code is dataset-agnostic).

**Roadmap**
1. **Appearance embedding branch** — fuse a re-ID cosine cost with the IoU cost
   in `_match` to harden ids through long occlusions.
2. **Real-data harness** — a thin loader to run and score on MOT17.
3. **Camera-motion compensation** — warp track predictions by frame-to-frame
   homography for moving-camera footage (as in BoT-SORT).

---

## 12. File map

```
src/visiontrack/
  core/          geometry.py · kalman.py · assignment.py   ← from-scratch math
  detection/     base.py (Detection + Detector) · synthetic.py · onnx_yolo.py
  tracking/      track.py (FSM) · tracker.py (ByteTrack) · config.py
  eval/          mot.py (CLEAR-MOT)
  viz/           draw.py (matplotlib, optional)
  cli.py         demo / eval / ablate
tests/           geometry · kalman · assignment (vs SciPy) · tracker · mot
benchmarks/      bench_tracker.py
examples/        demo_synthetic.py
assets/          trajectories.png · tracking.gif
.github/workflows/ci.yml
```

---

*One-line summary:* a real-time multi-object tracker where optimal Bayesian
state estimation (Kalman), optimal combinatorial assignment (Hungarian), and
robust two-stage data association (ByteTrack) are implemented from first
principles on NumPy, wired together with a lifecycle state machine, and
validated end-to-end with from-scratch CLEAR-MOT metrics and a 182-test suite.
