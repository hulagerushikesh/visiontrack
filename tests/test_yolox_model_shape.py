"""Static ONNX input dimensions are part of a detector configuration."""

from types import SimpleNamespace

import pytest

from visiontrack.detection.yolox_onnx import YoloxDetector


class _Session:
    def __init__(self, shape):
        self.shape = shape

    def get_inputs(self):
        return [SimpleNamespace(name="images", shape=self.shape)]


def test_static_export_rejects_wrong_input_size_before_inference():
    with pytest.raises(ValueError, match="input is 416x416, but input_size=640"):
        YoloxDetector("unused.onnx", input_size=640, session=_Session([1, 3, 416, 416]))
    with pytest.raises(ValueError, match="input is 640x640, but input_size=416"):
        YoloxDetector("unused.onnx", input_size=416, session=_Session([1, 3, 640, 640]))


def test_matching_and_dynamic_exports_keep_existing_setup():
    assert YoloxDetector("unused.onnx", input_size=416,
                         session=_Session([1, 3, 416, 416])).input_size == 416
    assert YoloxDetector("unused.onnx", input_size=640,
                         session=_Session([1, 3, "height", "width"])).input_size == 640
