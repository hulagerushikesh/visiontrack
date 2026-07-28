# H2.1 — Run the tracker on your own video

Point VisionTrack at any video file and get an annotated one back, with
per-object coloured boxes and stable ids drawn on every frame.

```bash
pip install 'visiontrack[video]'          # imageio + ffmpeg, lazily imported
visiontrack track input.mp4 out.mp4 --model models/yolox_nano.onnx
```

Library use:

```python
from visiontrack.video import track_video
from visiontrack.detection.yolox_onnx import YoloxDetector

det = YoloxDetector("models/yolox_nano.onnx", class_filter={0})  # person only
summary = track_video("input.mp4", "out.mp4", det)
print(summary)   # VideoSummary(frames=..., unique_tracks=..., fps=..., output_path=...)
```

The pipeline ([`src/visiontrack/video.py`](../src/visiontrack/video.py)) is
**detector-agnostic**: it accepts anything with `detect(frame_rgb) ->
list[Detection]`, so it is exercised end-to-end in tests with a stub detector
over a real (tiny) mp4 — no model needed for CI.

## Getting a YOLOX model

The detector ([`detection/yolox_onnx.py`](../src/visiontrack/detection/yolox_onnx.py))
expects a YOLOX ONNX export (`(1, N, 5+nc)` output, decode baked in). YOLOX is the
detector the ByteTrack / OC-SORT papers use, so it keeps the tracking lineage
consistent. Two ways to obtain `yolox_nano.onnx` (or `yolox_tiny.onnx`):

1. **Download a pre-exported ONNX** from the official
   [Megvii-BaseDetection/YOLOX](https://github.com/Megvii-BaseDetection/YOLOX)
   release assets / model zoo, into `models/`.
2. **Export from weights** with the YOLOX repo:
   `python tools/export_onnx.py -n yolox-nano -c yolox_nano.pth --output-name yolox_nano.onnx --decode_in_inference`

Models are gitignored (like the re-ID weights) — VisionTrack stays weight-clean.
`--input-size` must match the export (nano/tiny use 416; s/m/l use 640).

## Notes

- Default tracks **person** only (COCO class 0); pass `--all-classes` for all.
- `--conf` sets the detector confidence gate; `--max-frames N` limits a quick test.
- Output is H.264 mp4 via imageio-ffmpeg; fps is copied from the source.
- This is the first Horizon-2 piece (study → tool); see
  [`HORIZONS.md`](HORIZONS.md).
