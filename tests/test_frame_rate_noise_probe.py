import numpy as np
import pytest

from experiments.frame_rate_noise_probe import ScaledProcessNoise, replay
from experiments.frame_spacing_gate_probe import stream
from visiontrack.core.kalman import KalmanBoxTracker


def test_unit_scale_preserves_default_kalman_prediction():
    default = KalmanBoxTracker()
    scaled = ScaledProcessNoise(1.0)
    state = default.initiate(np.array([100.0, 200.0, 0.8, 70.0]))
    original = default.predict(*state)
    candidate = scaled.predict(*state)
    for a, b in zip(original, candidate, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("scale", [0, -1, float("nan"), float("inf")])
def test_invalid_process_scale_rejected(scale):
    with pytest.raises(ValueError):
        ScaledProcessNoise(scale)


def test_fast_low_fps_case_is_recovered_only_at_high_variance():
    rows = stream(300, 10)
    assert replay(rows, 1)["public_ids"] == 0
    assert replay(rows, 3)["public_ids"] == 0
    assert replay(rows, 9)["public_ids"] == 1
