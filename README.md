# VisionTrack

[![CI](https://github.com/hulagerushikesh/visiontrack/actions/workflows/ci.yml/badge.svg)](https://github.com/hulagerushikesh/visiontrack/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Online multi-object tracking, built from first principles.**

A tracking-by-detection system that follows many objects across a video and
assigns each a stable identity. The hard parts — the **Kalman filter**, the
**Hungarian assignment algorithm**, and the **ByteTrack two-stage association**
— are implemented from scratch on NumPy, not delegated to a library. The
result runs in real time (200–2300 FPS on CPU) and is validated end-to-end
against CLEAR-MOT metrics.

![tracked trajectories](assets/trajectories.png)

*Seven simulated objects tracked over 120 frames. Note tracks **#3** and **#7**
cross in the centre and keep their identities — the job of the motion model +
gated assignment.*

---

## Why this project

Most tracking repos are a thin wrapper over `ultralytics` + a vendored
tracker. This one is the opposite: the detector is pluggable and optional,
while the estimation and association math is the deliverable and is
**independently tested** (the Hungarian solver is checked against SciPy on
hundreds of random matrices; the Kalman filter is checked for convergence and
covariance behaviour).

It demonstrates, concretely:

| Area | What's shown |
|------|--------------|
| Probabilistic state estimation | An 8-state constant-velocity Kalman filter with height-scaled, Joseph-form updates and Mahalanobis gating |
| Combinatorial optimization | An O(n³) Kuhn–Munkres / shortest-augmenting-path linear-assignment solver for rectangular cost matrices |
| Algorithm design | ByteTrack-style two-stage association that recovers occluded objects from *low-confidence* detections |
| Software architecture | Clean layering (core → detection → tracking → eval → viz), typed configs, a structural `Detector` interface, zero framework dependencies in the core |
| Evaluation rigor | A from-scratch CLEAR-MOT implementation (MOTA/MOTP/IDSW/MT/ML) and an ablation harness that quantifies each component's contribution |

## Install

```bash
cd visiontrack
pip install -e ".[dev]"          # core + tests + viz
# core only needs numpy; extras: [viz] (matplotlib+pillow), [onnx] (onnxruntime)
```

## Quickstart

```python
from visiontrack import ByteTracker, TrackerConfig, Detection

tracker = ByteTracker(TrackerConfig())
for frame_detections in stream:            # list[Detection] per frame
    for obs in tracker.update(frame_detections):
        print(obs.track_id, obs.xyxy, obs.score)
```

Everything runs on a built-in **synthetic scene generator**, so there is
nothing to download:

```bash
visiontrack demo  --plot traj.png --gif out.gif   # simulate + track + render
visiontrack eval  --json                          # print CLEAR-MOT metrics
visiontrack ablate                                # component contribution table
```

## How it works

Each frame runs the classic predict → associate → update loop:

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

- **Kalman filter** (`core/kalman.py`) — state `[cx, cy, aspect, h, ẋ]`,
  constant-velocity model, noise scaled by object height for scale-invariance.
  Association uses the **Mahalanobis distance** in innovation space, so the
  gate widens automatically for uncertain (new or long-occluded) tracks.
- **Assignment** (`core/assignment.py`) — a rectangular O(n³) Hungarian solver
  with dual potentials, wrapped by a gated `associate()` that returns matched
  pairs plus the leftover rows/columns.
- **Two-stage association** (`tracking/tracker.py`) — the ByteTrack insight:
  don't discard weak detections. Confident boxes match first; tracks left
  unmatched get a second chance against the low-confidence boxes, which is how
  partially-occluded objects keep their IDs.
- **Lifecycle** (`tracking/track.py`) — a `Tentative → Confirmed → Deleted`
  state machine: new tracks must survive `n_init` frames to confirm (rejects
  false positives), and confirmed tracks coast up to `max_age` frames through
  occlusion before deletion.

## Results

CLEAR-MOT on the synthetic benchmark (`visiontrack eval`, 6 objects, 120
frames, with detector miss/false-positive/occlusion noise):

```
MOTA=0.902  MOTP=0.919  IDSW=0  FP=0  FN=54  precision=1.000  recall=0.902  MT=6 ML=0
```

**Throughput** (`benchmarks/bench_tracker.py`, CPU, single-threaded):

| objects | avg dets/frame | mean ms | p95 ms | FPS | MOTA | IDSW |
|--------:|---------------:|--------:|-------:|----:|-----:|-----:|
| 4  | 3.1  | 0.43 | 0.55 | 2334 | 0.892 | 0 |
| 8  | 4.9  | 0.65 | 0.96 | 1541 | 0.902 | 0 |
| 16 | 7.9  | 1.11 | 1.87 |  903 | 0.900 | 0 |
| 32 | 13.5 | 2.02 | 3.76 |  494 | 0.893 | 0 |
| 64 | 27.9 | 4.68 | 8.59 |  214 | 0.889 | 0 |

Comfortably real-time (≥30 FPS) up to 64 concurrent objects.

**Ablation** (`visiontrack ablate`, crowded 16-object stress scene) — each
component earns its place:

```
variant                         MOTA    MOTP   IDSW     FP     FN
----------------------------------------------------------------
full (bytetrack + gating)      0.865   0.917      0      0    153
no low-score recovery          0.860   0.918      0      0    159   ← +6 misses
no Mahalanobis gating          0.865   0.916      1      0    152   ← +1 ID switch
class-agnostic                 0.865   0.917      0      0    153
```

The low-score recovery stage reduces missed detections; the Mahalanobis gate
prevents an identity switch in the crowd. (On easy scenes these effects
shrink — the harness reports the honest, scene-dependent contribution rather
than a cherry-picked number.)

## Using a real detector

The tracker consumes anything satisfying the `Detector` protocol. A YOLOv8-style
ONNX backend is included (optional `onnxruntime`):

```python
from visiontrack.detection.onnx_yolo import OnnxYoloDetector
from visiontrack import ByteTracker

detector = OnnxYoloDetector("yolov8n.onnx", class_filter={0})  # persons only
tracker = ByteTracker()
for frame in video:                       # H×W×3 uint8
    tracker.update(detector.detect(frame))
```

## Project layout

```
src/visiontrack/
  core/          geometry.py · kalman.py · assignment.py   ← the from-scratch math
  detection/     base.py (Detection + Detector protocol)
                 synthetic.py (scene simulator / eval oracle)
                 onnx_yolo.py (optional real detector)
  tracking/      track.py (lifecycle FSM) · tracker.py (ByteTrack) · config.py
  eval/          mot.py (CLEAR-MOT metrics)
  viz/           draw.py (matplotlib rendering, optional)
  cli.py         demo / eval / ablate subcommands
tests/           geometry · kalman · assignment (vs SciPy) · tracker · MOT
benchmarks/      bench_tracker.py
examples/        demo_synthetic.py
```

## Testing

```bash
pytest            # ~180 checks: unit + property + integration
```

The suite includes property tests (the custom Hungarian solver must reach
SciPy's optimal cost on 150 random matrices), Kalman convergence tests, and an
end-to-end integration test that asserts a MOTA / ID-switch floor on the
synthetic scene — a genuine regression gate.

## Design notes & limitations

- **Motion-only association.** Identity is maintained purely from motion +
  geometry (no appearance embeddings). This is fast and robust for typical
  frame rates; the `Detection.feature` field and the `_match` cost hook are the
  intended extension points for adding a re-ID model (DeepSORT-style).
- **Linear motion model.** Constant-velocity is the right default for short
  horizons; abrupt manoeuvres over long occlusions are the known failure mode,
  which is exactly what `max_age` bounds.
- **Synthetic evaluation.** The included benchmark is simulated for
  reproducibility. The metrics code is dataset-agnostic — point it at MOT17
  ground truth and it works unchanged.

## License

MIT
