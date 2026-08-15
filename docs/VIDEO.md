# H2.1 — Run the tracker on your own video

Point VisionTrack at any video file and get an annotated one back, with
per-object coloured boxes and stable ids drawn on every frame.

```bash
pip install 'visiontrack-mot[video]'          # imageio + ffmpeg, lazily imported
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
consumes a YOLOX ONNX export with `(1, N, 5+nc)` output. YOLOX is the detector the
ByteTrack / OC-SORT papers use, so it keeps the tracking lineage consistent. It
handles **both** export flavours automatically:

- **Raw grid output** — the *default* export, and what the official
  [Megvii-BaseDetection/YOLOX](https://github.com/Megvii-BaseDetection/YOLOX)
  release ONNX files ship: box columns are per-cell offsets + log-scale, decoded
  with the standard grid/stride math inside the detector.
- **Decode baked in** (`--decode_in_inference`) — box columns already in pixel
  space; used directly.

So you can just grab a pre-exported ONNX and go — no re-export needed:

```bash
mkdir -p models
curl -L -o models/yolox_nano.onnx \
  https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx
```

(Or export from weights: `python tools/export_onnx.py -n yolox-nano -c yolox_nano.pth
--output-name yolox_nano.onnx`.) Models are gitignored (like the re-ID weights) —
VisionTrack stays weight-clean. `--input-size` must match the export (nano/tiny use
416; s/m/l use 640).

## Reproduce the annotated demo

[`scripts/render_video_demo.py`](../scripts/render_video_demo.py) runs the whole
pipeline over any clip and keeps the common street classes (person + vehicles) by
default, with tracker gates relaxed for a COCO YOLOX-nano (whose scores run lower
than a MOT-tuned detector):

```bash
# 1. model (above) + 2. any license-clean clip, e.g. a public-domain street video
curl -L -o clip.webm \
  'https://upload.wikimedia.org/wikipedia/commons/a/a9/Bangkok_Traffic_During_Enduring_Partners_26_%281009429%29.webm'
# 3. render (optionally trim/downscale the source first with ffmpeg)
python scripts/render_video_demo.py clip.webm tracked.mp4 --model models/yolox_nano.onnx --max-frames 360
```

The sample above is *Bangkok Traffic During Enduring Partners 26* by SSgt James
Bunn, U.S. Army National Guard — **public domain** (a U.S. federal work), so the
annotated result is freely redistributable. Nothing here is committed as imagery:
the model, source, and output all stay local/gitignored, keeping the repo
imagery-clean; the script + tests are what live in git.

## H2.2 — Run the tracker on a live camera

The same detect→track→draw pipeline runs in real time on a webcam, with an
optional live preview window:

```bash
visiontrack webcam --model models/yolox_nano.onnx --mirror
#   press q or Esc to quit; prints achieved FPS on exit
```

The preview window uses OpenCV, imported lazily so it is **never a hard
dependency** — install it only if you want the window (`pip install
opencv-python`), or run headless with `--no-window`.

```python
from visiontrack.video import track_webcam
from visiontrack.detection.yolox_onnx import YoloxDetector

det = YoloxDetector("models/yolox_nano.onnx", class_filter={0})
# on_frame gets (annotated_rgb, observations); reader injects any frame source.
summary = track_webcam(det, on_frame=my_sink, mirror=True)
print(summary.fps)   # measured real-time throughput
```

The frame source is decoupled from the hardware: pass any iterable of RGB frames
as `reader=` and the whole loop runs headlessly — which is exactly how the tests
exercise it, with no camera and no window. Only opening a real camera and drawing
the OpenCV window need physical hardware.

## Notes

- Default tracks **person** only (COCO class 0); pass `--all-classes` for all.
- `--conf` sets the detector confidence gate; `--max-frames N` limits a quick test.
- Output is H.264 mp4 via imageio-ffmpeg; fps is copied from the source.
- This is the first Horizon-2 piece (study → tool); see
  [`HORIZONS.md`](HORIZONS.md).
