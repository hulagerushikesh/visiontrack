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
```
