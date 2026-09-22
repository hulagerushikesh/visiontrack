# Public API

Everything below is importable straight from the top-level package —
`from visiontrack import …` — and is what `__all__` guarantees is stable.

```bash
pip install visiontrack-mot            # core: NumPy only
pip install 'visiontrack-mot[video]'   # + run on real video files
```

## Core tracking

```python
from visiontrack import ByteTracker, TrackerConfig, Detection

tracker = ByteTracker(TrackerConfig(w_app=0.0))   # motion-only ByteTrack
for frame_detections in stream:                    # list[Detection]
    observations = tracker.update(frame_detections)  # list[TrackObservation]
    for o in observations:
        print(o.track_id, o.xyxy, o.score)
```

- **`ByteTracker(config=None)`** — the online tracker. `.update(detections,
  camera_shift=None) -> list[TrackObservation]`; `.reset()`.
- **`TrackerConfig`** — every knob in one typed dataclass: association thresholds,
  lifecycle (`n_init`, `max_age`), the cost weights `w_iou/w_app/w_unc/w_ocm`,
  `use_giou`, `use_oru`, `use_gmc`, `kf_noise_scale`, `motion_residual_path`.
- **`TrackObservation`** — one confirmed box: `frame, track_id, xyxy, score, class_id`.
- **`Detection`** — one input box: `xyxy, score, class_id, feature=None`.

### Tracker presets

```python
from visiontrack import preset, PRESET_NAMES, ByteTracker

ByteTracker(preset("sort"))          # single-stage IoU
ByteTracker(preset("bytetrack_reid"))# two-stage + appearance
# PRESET_NAMES: sort, deepsort, bytetrack, bytetrack_reid, bytetrack_giou, oc_sort
```

## Run on real video (needs the `[video]` extra)

```python
from visiontrack import track_video
from visiontrack.detection.yolox_onnx import YoloxDetector

det = YoloxDetector("models/yolox_nano.onnx", class_filter={0})  # person only
summary = track_video("in.mp4", "out.mp4", det)   # -> VideoSummary
```

- **`track_video(source, output_path, detector, config=None, *, class_filter=None,
  max_frames=None, progress=False) -> VideoSummary`** — detector-agnostic
  (any `detect(frame_rgb) -> list[Detection]`).
- **`track_webcam(detector, config=None, *, on_frame=None, class_filter=None,
  device="<video0>", reader=None, mirror=False, record=None, record_fps=30.0,
  max_frames=None) -> VideoSummary`** — live-stream variant.
  `on_frame(annotated_rgb, observations)` is the per-frame sink; `reader` injects
  any iterable of RGB frames (defaults to the camera), so the loop runs headlessly;
  `mirror` flips for a selfie view; `record` also encodes the annotated session to
  an MP4. CLI: `visiontrack webcam`.
- **`VideoSummary`** — `frames, unique_tracks, fps, output_path`.

## Evaluation

```python
from visiontrack import MotAccumulator, evaluate_sequence
```

- **`MotAccumulator(iou_threshold=0.5, on_switch=None)`** — streaming CLEAR-MOT;
  `.update(gt_ids, gt_boxes, hyp_ids, hyp_boxes)`, `.result() -> MotMetrics`.
- **`evaluate_sequence(...)`** — one-shot metrics for a whole sequence.
- HOTA / IDF1 live in `visiontrack.eval.hota` (cross-checked vs trackeval to 1e-3).

## CLI

```bash
visiontrack demo      # synthetic demo (+ optional PNG/GIF)
visiontrack eval      # metrics on synthetic or MOT17
visiontrack ablate    # compare component variants
visiontrack track in.mp4 out.mp4 --model yolox_nano.onnx   # [video] extra
visiontrack lab-evidence BUNDLE VARIANT EVENT_ID \
  --frame 42=frame.png --crop 120,80,420,520      # preview only
visiontrack lab-decision BUNDLE --status accepted --variant baseline \
  --rationale "Meets the registered criteria." --author local-reviewer \
  --decided-at 2026-09-21T08:30:00Z               # preview only
```

`lab-evidence` accepts only explicit `FRAME=PNG_PATH` inputs and prints the
resolved crop, output dimensions, privacy class, and limits without reading the
PNGs or writing evidence. Add `--write` to execute the previewed operation.
Unredacted full-frame non-synthetic pixels additionally require
`--allow-full-frame-source-pixels`. Install the `[lab]` extra for writing.

`lab-decision` rebuilds and verifies the sealed report, then prints the exact
choice, decision fingerprint, and experiment/source/comparison/report lineage
without mutating the bundle. Use `--status accepted --variant NAME` to accept
one verified variant, or `--status rejected_all` without `--variant`. Add
`--write` only after reviewing the preview; the resulting root-level
`decision.json` is immutable, identical writes are idempotent, and conflicting
second decisions are refused.

The React Reliability Lab can also inspect one explicitly selected local
`decision.json`. The browser validates its exact schema, recomputes the decision
fingerprint, and checks experiment/source/comparison/report lineage against the
active validated report. Files stay in browser memory; an imported audit record
remains read-only and is never uploaded.

When the active report was explicitly imported rather than loaded as the
illustrative sample, the same panel can draft a new record. It starts without
an outcome or variant, requires rationale, author, and a visible UTC timestamp,
and displays the exact content fingerprint before enabling an explicit
`decision.json` download. This is a browser download only: it does not mutate
the bundle, overwrite an imported decision, or contact a server.

## Reliability Lab decisions

```python
from visiontrack.lab import plan_human_decision, read_human_decision, record_human_decision

preview = plan_human_decision(
    bundle,
    status="accepted",
    accepted_variant="baseline",
    rationale="Meets the registered acceptance criteria.",
    author="local-reviewer",
    decided_at="2026-09-21T08:30:00Z",
)

path = record_human_decision(
    bundle,
    status="accepted",              # or "rejected_all"
    accepted_variant="baseline",    # None when rejecting all variants
    rationale="Meets the registered acceptance criteria.",
    author="local-reviewer",
    decided_at="2026-09-21T08:30:00Z",
)
decision = read_human_decision(bundle)
```

Both functions revalidate the sealed comparison and canonical local report.
The decision is content-addressed and immutable; repeating the same write is
safe, while a conflicting second decision is refused. Metrics never select a
variant automatically.
