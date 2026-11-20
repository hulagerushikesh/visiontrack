"""The experiment-only aspect-free gate: same filter, aspect left out of gating."""
import numpy as np
import pytest

from experiments.aspect_gate import GATE_3DOF, VARIANTS, AspectFreeGateKalman, make_tracker
from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig


def _state():
    kf = KalmanBoxTracker()
    mean, cov = kf.initiate(np.array([100.0, 80.0, 1.8, 60.0]))
    return kf.predict(mean, cov)


def test_pure_aspect_change_is_free_but_blocked_by_default():
    mean, cov = _state()
    meas = np.array([[100.0, 80.0, 1.3, 60.0]])  # shape change only
    full = KalmanBoxTracker().gating_distance_batch(mean[None], cov[None], meas)[0, 0]
    free = AspectFreeGateKalman().gating_distance_batch(mean[None], cov[None], meas)[0, 0]
    assert full > 9.4877
    assert free == pytest.approx(0.0, abs=1e-12)


def test_equal_aspect_gives_same_distance_as_default():
    mean, cov = _state()
    meas = np.array([[112.0, 71.0, 1.8, 63.0], [90.0, 95.0, 1.8, 58.0]])
    full = KalmanBoxTracker().gating_distance_batch(mean[None], cov[None], meas)
    free = AspectFreeGateKalman().gating_distance_batch(mean[None], cov[None], meas)
    np.testing.assert_allclose(free, full, rtol=1e-12)


def test_variants_build_and_default_is_untouched():
    trackers = {v: make_tracker(v) for v in VARIANTS}
    assert type(trackers["gate_on"].kf) is KalmanBoxTracker
    assert trackers["gate_off"].cfg.use_mahalanobis_gating is False
    assert trackers["aspect_free_gate"]._gate == GATE_3DOF
    assert TrackerConfig().use_mahalanobis_gating is True
    with pytest.raises(ValueError):
        make_tracker("nope")


def test_turning_box_keeps_identity_only_without_aspect_gate():
    def run(variant):
        tracker = make_tracker(variant)
        ids = []
        for k in range(12):
            w = 120.0 if k < 6 else 80.0  # vehicle turns: width drops, height fixed
            box = np.array([200.0 + 3 * k, 300.0, 200.0 + 3 * k + w, 360.0])
            ids.append({o.track_id for o in tracker.update([Detection(box, 0.9, 2)])})
        return set().union(*ids)

    assert len(run("aspect_free_gate")) == 1
    assert len(run("gate_on")) > 1
