"""Run the tracker on a real video file — the "make it usable" entry point.

``track_video`` ties a detector to the from-scratch tracker and writes an
annotated video: each frame is detected, associated, and drawn with per-track
coloured boxes and ids. It is deliberately **detector-agnostic** — it accepts any
object with ``detect(frame_rgb) -> list[Detection]`` (e.g.
:class:`~visiontrack.detection.yolox_onnx.YoloxDetector`, or a stub in tests) —
so the pipeline is testable without shipping a heavy model.

Video I/O uses ``imageio`` (+ ffmpeg), imported lazily; drawing uses Pillow.
Both live in the ``[video]`` extra and are never imported by the core.

    from visiontrack.video import track_video
    from visiontrack.detection.yolox_onnx import YoloxDetector
    track_video("in.mp4", "out.mp4", YoloxDetector("models/yolox_nano.onnx"))
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass

import numpy as np

from .tracking.config import TrackerConfig
from .tracking.tracker import ByteTracker, TrackObservation

__all__ = [
    "track_video",
    "track_webcam",
    "VideoSummary",
    "color_for_id",
    "draw_observations",
]


@dataclass(slots=True)
class VideoSummary:
    """What ``track_video`` did — returned for logging/tests."""

    frames: int
    unique_tracks: int
    fps: float
    output_path: str


def color_for_id(track_id: int) -> tuple[int, int, int]:
    """Deterministic, well-spread RGB colour for a track id (golden-ratio hue)."""
    hue = (track_id * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.72, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def draw_observations(
    frame_rgb: np.ndarray, observations: list[TrackObservation]
) -> np.ndarray:
    """Return a copy of ``frame_rgb`` with each observation's box + id drawn."""
    from PIL import Image, ImageDraw

    img = Image.fromarray(np.ascontiguousarray(frame_rgb))
    draw = ImageDraw.Draw(img)
    h = img.height
    for o in observations:
        x1, y1, x2, y2 = (float(v) for v in o.xyxy)
        color = color_for_id(o.track_id)
        width = max(2, round(h / 300))
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
        label = f"#{o.track_id}"
        ty = max(0.0, y1 - 12)
        draw.rectangle([x1, ty, x1 + 8 * len(label) + 4, ty + 12], fill=color)
        draw.text((x1 + 2, ty), label, fill=(0, 0, 0))
    return np.asarray(img)


def track_video(
    source: str,
    output_path: str,
    detector,
    config: TrackerConfig | None = None,
    *,
    class_filter: set[int] | None = None,
    max_frames: int | None = None,
    progress: bool = False,
) -> VideoSummary:
    """Track every frame of ``source`` and write an annotated video to ``output_path``.

    ``detector`` is any object exposing ``detect(frame_rgb) -> list[Detection]``.
    ``class_filter`` optionally keeps only these class ids (e.g. ``{0}`` = person).
    Returns a :class:`VideoSummary`.
    """
    try:
        import imageio.v2 as imageio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "track_video needs the [video] extra: pip install 'visiontrack[video]'"
        ) from exc

    reader = imageio.get_reader(source)  # imageio-ffmpeg backend
    try:
        fps = float(reader.get_meta_data().get("fps", 30.0))
    except Exception:  # pragma: no cover - metadata is best-effort
        fps = 30.0

    tracker = ByteTracker(config or TrackerConfig())
    seen_ids: set[int] = set()
    writer = imageio.get_writer(output_path, fps=fps, macro_block_size=None)
    n = 0
    try:
        for frame in reader:
            frame = np.asarray(frame)[:, :, :3]  # drop alpha if present
            dets = detector.detect(frame)
            if class_filter is not None:
                dets = [d for d in dets if d.class_id in class_filter]
            obs = tracker.update(dets)
            for o in obs:
                seen_ids.add(o.track_id)
            writer.append_data(draw_observations(frame, obs))
            n += 1
            if progress and n % 25 == 0:
                print(f"  frame {n}: {len(obs)} tracks")
            if max_frames is not None and n >= max_frames:
                break
    finally:
        reader.close()
        writer.close()

    return VideoSummary(frames=n, unique_tracks=len(seen_ids), fps=fps,
                        output_path=output_path)


def track_webcam(
    detector,
    config: TrackerConfig | None = None,
    *,
    on_frame=None,
    class_filter: set[int] | None = None,
    device: str = "<video0>",
    max_frames: int | None = None,
) -> VideoSummary:
    """Track a live webcam stream in real time, invoking ``on_frame`` per frame.

    Reuses the same detect→track→draw path as :func:`track_video`, but pulls
    frames from the camera and hands each annotated frame to ``on_frame`` (for a
    GUI/window, or a headless sink) instead of encoding a file. ``on_frame`` is
    called as ``on_frame(annotated_rgb, observations)``; if ``None``, frames are
    simply processed (useful for a smoke/latency test).

    ``device`` is the imageio-ffmpeg camera spec (``"<video0>"`` on Linux/macOS).
    Real cameras aren't available in CI, so this is thin and untested there; the
    frame-processing core it shares with ``track_video`` is what the tests cover.
    """
    try:  # pragma: no cover - needs a camera + the [video] extra
        import imageio.v2 as imageio
    except ImportError as exc:
        raise ImportError(
            "track_webcam needs the [video] extra: pip install 'visiontrack[video]'"
        ) from exc

    reader = imageio.get_reader(device)  # pragma: no cover - hardware-dependent
    tracker = ByteTracker(config or TrackerConfig())
    seen_ids: set[int] = set()
    n = 0
    try:  # pragma: no cover - hardware-dependent
        for frame in reader:
            frame = np.asarray(frame)[:, :, :3]
            dets = detector.detect(frame)
            if class_filter is not None:
                dets = [d for d in dets if d.class_id in class_filter]
            obs = tracker.update(dets)
            for o in obs:
                seen_ids.add(o.track_id)
            annotated = draw_observations(frame, obs)
            if on_frame is not None:
                on_frame(annotated, obs)
            n += 1
            if max_frames is not None and n >= max_frames:
                break
    finally:  # pragma: no cover
        reader.close()
    return VideoSummary(frames=n, unique_tracks=len(seen_ids), fps=0.0,
                        output_path="<webcam>")
