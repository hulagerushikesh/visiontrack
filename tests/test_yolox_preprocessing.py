"""The opt-in model input must match the preprocessing used in the pilot."""

from types import SimpleNamespace

import numpy as np
import pytest

from visiontrack.detection.yolox_onnx import YoloxDetector


class _RecordingSession:
    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def run(self, outputs, feed):
        self.blob = feed["images"]
        return [np.array([[[2, 2, 2, 2, 0.9, 0.8]]])]


def test_default_preserves_input_order_and_rounded_nearest_samples():
    session = _RecordingSession()
    detector = YoloxDetector("unused", input_size=4, session=session)
    rgb = np.arange(30, dtype=np.uint8).reshape(2, 5, 3)
    detector.detect(rgb)
    expected = np.full((4, 4, 3), 114, dtype=np.uint8)
    expected[:2] = rgb[:, [0, 1, 2, 4]]
    np.testing.assert_array_equal(session.blob, expected.transpose(2, 0, 1)[None])
    assert session.blob.dtype == np.float32


@pytest.mark.parametrize("shape", [(2, 5), (5, 2)])
def test_upstream_uses_truncated_bilinear_bgr_for_both_detection_apis(shape):
    cv2 = pytest.importorskip("cv2")
    session = _RecordingSession()
    detector = YoloxDetector("unused", input_size=4, session=session, preprocessing="upstream")
    rgb = np.arange(30, dtype=np.uint8).reshape(*shape, 3)
    expected = np.full((4, 4, 3), 114, dtype=np.uint8)
    h, w = shape
    nh, nw = int(h * 0.8), int(w * 0.8)
    expected[:nh, :nw] = cv2.resize(rgb[..., ::-1], (nw, nh), interpolation=cv2.INTER_LINEAR)
    expected = expected.transpose(2, 0, 1)[None]

    normal = detector.detect(rgb)
    np.testing.assert_array_equal(session.blob, expected)
    traced, capture = detector.detect_with_proposals(rgb)
    np.testing.assert_array_equal(session.blob, expected)
    np.testing.assert_array_equal(traced[0].xyxy, normal[0].xyxy)
    assert capture.scale == 0.8


def test_invalid_preprocessing_fails_before_session_setup():
    with pytest.raises(ValueError, match="preprocessing"):
        YoloxDetector("unused", preprocessing="unknown")
