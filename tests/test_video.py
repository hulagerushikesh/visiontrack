"""Tests for the H2 video pipeline (track_video) and the YOLOX detector decode.

The pipeline is exercised end-to-end over a real (tiny) mp4 written with imageio,
using a stub detector — so no ML model is needed. YOLOX decoding is tested with a
fake ONNX session. Both skip cleanly if the [video] extra is absent.
"""
from __future__ import annotations

import numpy as np
import pytest

from visiontrack.detection.base import Detection
from visiontrack.detection.yolox_onnx import YoloxDetector
from visiontrack.tracking.tracker import TrackObservation
from visiontrack.video import color_for_id, draw_observations

imageio = pytest.importorskip("imageio")


class _StubDetector:
    """Emits one box per frame moving steadily right — a trackable object."""

    def __init__(self):
        self.t = 0

    def detect(self, frame):
        x = 20 + self.t * 6
        self.t += 1
        return [Detection(xyxy=np.array([x, 40.0, x + 30, 100.0]),
                          score=0.9, class_id=0)]


def _write_test_video(path, n=30, h=128, w=160):
    import imageio.v2 as iio
    writer = iio.get_writer(path, fps=10, macro_block_size=None)
    rng = np.random.default_rng(0)
    for _ in range(n):
        writer.append_data(rng.integers(0, 255, (h, w, 3), dtype=np.uint8))
    writer.close()


# -- drawing -----------------------------------------------------------------

def test_color_for_id_is_deterministic_rgb():
    c = color_for_id(5)
    assert c == color_for_id(5)
    assert len(c) == 3 and all(0 <= v <= 255 for v in c)
    assert color_for_id(5) != color_for_id(6)


def test_draw_observations_preserves_shape_and_marks_pixels():
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    obs = [TrackObservation(frame=0, track_id=1,
                            xyxy=np.array([10.0, 10, 60, 70]), score=0.9, class_id=0)]
    out = draw_observations(frame, obs)
    assert out.shape == frame.shape
    assert out.sum() > 0  # something was drawn


# -- full pipeline -----------------------------------------------------------

def test_track_video_end_to_end(tmp_path):
    from visiontrack.video import track_video
    src = tmp_path / "in.mp4"
    dst = tmp_path / "out.mp4"
    _write_test_video(src, n=24)
    summary = track_video(str(src), str(dst), _StubDetector(), max_frames=24)
    assert summary.frames == 24
    assert summary.unique_tracks >= 1        # the moving box became a track
    assert dst.exists() and dst.stat().st_size > 0
    # The annotated video reads back with the same frame count.
    import imageio.v2 as iio
    r = iio.get_reader(str(dst))
    assert r.count_frames() >= 20            # codecs may pad/trim a few
    r.close()


def test_track_video_respects_class_filter(tmp_path):
    from visiontrack.video import track_video
    src = tmp_path / "in.mp4"
    _write_test_video(src, n=10)
    # Detector emits class 0; filtering to {1} => nothing tracked.
    summary = track_video(str(src), str(tmp_path / "o.mp4"),
                          _StubDetector(), class_filter={1})
    assert summary.unique_tracks == 0


# -- YOLOX decode (fake session, no model) -----------------------------------

class _FakeYoloxSession:
    """Returns one high-confidence YOLOX-format detection per call."""

    def __init__(self, cx=100.0, cy=100.0, w=40.0, h=60.0):
        self._out = np.zeros((1, 2, 85), dtype=np.float32)
        self._out[0, 0, :4] = [cx, cy, w, h]
        self._out[0, 0, 4] = 0.9         # objectness
        self._out[0, 0, 5] = 0.95        # class 0 score
        self._out[0, 1, 4] = 0.01        # a junk row below threshold

    def get_inputs(self):
        class _I:
            name = "images"
        return [_I()]

    def run(self, _outputs, _feed):
        return [self._out]


def test_yolox_decode_from_fake_session():
    det = YoloxDetector("unused.onnx", input_size=416, session=_FakeYoloxSession())
    frame = np.zeros((416, 416, 3), dtype=np.uint8)  # scale = 1
    out = det.detect(frame)
    assert len(out) == 1
    d = out[0]
    assert d.class_id == 0
    assert abs(d.score - 0.9 * 0.95) < 1e-6
    # cxcywh (100,100,40,60) -> xyxy (80,70,120,130)
    assert np.allclose(d.xyxy, [80, 70, 120, 130], atol=1.0)


def test_yolox_conf_threshold_filters():
    det = YoloxDetector("unused.onnx", conf_threshold=0.99, session=_FakeYoloxSession())
    assert det.detect(np.zeros((416, 416, 3), dtype=np.uint8)) == []
