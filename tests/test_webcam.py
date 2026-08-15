"""Tests for the real-time webcam path (``track_webcam``) and its CLI sink.

The camera itself is never opened: the frame source is injected as a plain list
of RGB frames, so the whole detect→track→draw→sink loop runs headlessly with no
hardware, no ``[video]`` extra, and no OpenCV window. Only the two hardware
branches (opening a real camera; the OpenCV preview) are left uncovered — by
design, since they can't run in CI.
"""
from __future__ import annotations

import numpy as np
import pytest

from visiontrack.detection.base import Detection
from visiontrack.video import track_webcam


class _StubDetector:
    """Emits one box per frame moving steadily right (a trackable object).

    Also records every frame it was handed, so tests can assert on the exact
    pixels the pipeline fed the detector (e.g. after mirroring).
    """

    def __init__(self):
        self.t = 0
        self.seen: list[np.ndarray] = []

    def detect(self, frame):
        self.seen.append(np.asarray(frame).copy())
        x = 20 + self.t * 6
        self.t += 1
        return [Detection(xyxy=np.array([x, 40.0, x + 30, 100.0]),
                          score=0.9, class_id=0)]


def _frames(n=24, h=128, w=160):
    rng = np.random.default_rng(0)
    return [rng.integers(0, 255, (h, w, 3), dtype=np.uint8) for _ in range(n)]


def test_track_webcam_processes_injected_frames():
    captured: list[tuple] = []

    def sink(annotated, obs):
        captured.append((annotated, obs))

    frames = _frames(24)
    summary = track_webcam(_StubDetector(), on_frame=sink, reader=frames)

    assert summary.frames == 24
    assert summary.unique_tracks >= 1            # the moving box became a track
    assert summary.fps > 0                       # achieved throughput was measured
    assert summary.output_path == "<webcam>"
    assert len(captured) == 24                   # on_frame fired once per frame
    annotated, _ = captured[0]
    assert annotated.shape == frames[0].shape    # annotated frame keeps geometry


def test_track_webcam_respects_max_frames():
    seen = 0

    def sink(annotated, obs):
        nonlocal seen
        seen += 1

    summary = track_webcam(_StubDetector(), on_frame=sink,
                           reader=_frames(50), max_frames=10)
    assert summary.frames == 10
    assert seen == 10


def test_track_webcam_works_without_a_sink():
    # on_frame=None is a valid headless smoke/latency run.
    summary = track_webcam(_StubDetector(), reader=_frames(8))
    assert summary.frames == 8


def test_track_webcam_mirror_flips_frames_before_detection():
    # Left half white, right half black; after mirroring the detector sees it flipped.
    frame = np.zeros((64, 80, 3), dtype=np.uint8)
    frame[:, :40] = 255

    det_plain = _StubDetector()
    track_webcam(det_plain, reader=[frame.copy()])
    assert det_plain.seen[0][:, :40].mean() > 200      # left stayed bright

    det_mirror = _StubDetector()
    track_webcam(det_mirror, reader=[frame.copy()], mirror=True)
    assert det_mirror.seen[0][:, :40].mean() < 55       # left is now dark (flipped)
    assert det_mirror.seen[0][:, 40:].mean() > 200


def test_track_webcam_respects_class_filter():
    class _TwoClassDetector:
        def detect(self, frame):
            return [
                Detection(xyxy=np.array([10.0, 10, 40, 60]), score=0.9, class_id=0),
                Detection(xyxy=np.array([90.0, 10, 120, 60]), score=0.9, class_id=7),
            ]

    boxes_per_frame: list[int] = []

    def sink(annotated, obs):
        boxes_per_frame.append(len(obs))

    # Keep only class 0 — the class-7 box must be dropped before tracking.
    track_webcam(_TwoClassDetector(), on_frame=sink,
                 reader=_frames(6), class_filter={0})
    assert max(boxes_per_frame) <= 1


def test_track_webcam_record_writes_annotated_mp4(tmp_path):
    # Recording reuses the same imageio writer as track_video; skip if [video] absent.
    pytest.importorskip("imageio")
    out = tmp_path / "session.mp4"
    summary = track_webcam(_StubDetector(), reader=_frames(20),
                           record=str(out), record_fps=10.0)
    assert summary.frames == 20
    assert summary.output_path == str(out)
    assert out.exists() and out.stat().st_size > 0
    import imageio.v2 as iio
    r = iio.get_reader(str(out))
    assert r.count_frames() >= 16          # codecs may pad/trim a few frames
    r.close()


def test_build_webcam_sink_headless_is_a_noop():
    from argparse import Namespace

    from visiontrack.cli import _build_webcam_sink

    on_frame, close = _build_webcam_sink(Namespace(no_window=True))
    assert on_frame(np.zeros((8, 8, 3), dtype=np.uint8), []) is None
    assert close() is None                       # no window to tear down
