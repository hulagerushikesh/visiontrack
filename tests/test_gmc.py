"""Tests for global motion compensation (RQ4): phase correlation + wiring."""
from __future__ import annotations

import numpy as np

from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.motion.gmc import estimate_translation, hann_window
from visiontrack.tracking.tracker import ByteTracker


def _texture(h=128, w=128, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(h, w))


def test_phase_correlation_recovers_known_shift():
    img = _texture()
    dx, dy = 7, -5
    shifted = np.roll(np.roll(img, dy, axis=0), dx, axis=1)  # roll y then x
    sx, sy = estimate_translation(img, shifted)
    assert abs(sx - dx) <= 1
    assert abs(sy - dy) <= 1


def test_phase_correlation_zero_shift():
    img = _texture(seed=3)
    sx, sy = estimate_translation(img, img.copy())
    assert (sx, sy) == (0.0, 0.0)


def test_hann_window_shape_and_taper():
    win = hann_window((16, 24))
    assert win.shape == (16, 24)
    assert win[0, 0] == 0.0  # edges tapered to zero
    assert win[8, 12] > 0.5  # centre near one


def test_estimate_translation_validates_shape():
    import pytest
    with pytest.raises(ValueError):
        estimate_translation(np.zeros((4, 4)), np.zeros((4, 5)))


def test_gmc_off_by_default_and_shift_ignored():
    # With use_gmc False (default), passing a camera_shift must not change output.
    cfg = TrackerConfig()
    assert cfg.use_gmc is False
    dets = [Detection(xyxy=np.array([10.0, 10, 30, 50]), score=0.9, class_id=0)]

    a = ByteTracker(cfg)
    b = ByteTracker(cfg)
    for _ in range(4):
        oa = a.update(dets, camera_shift=(50.0, 50.0))  # large bogus shift
        ob = b.update(dets, camera_shift=None)
        assert [o.track_id for o in oa] == [o.track_id for o in ob]
        for x, y in zip(oa, ob, strict=False):
            assert np.allclose(x.xyxy, y.xyxy)


def test_gmc_shifts_prediction_when_enabled():
    # A track's predicted centre should move by the camera shift when use_gmc is on.
    cfg = TrackerConfig(use_gmc=True, n_init=1)
    tracker = ByteTracker(cfg)
    det = [Detection(xyxy=np.array([100.0, 100, 120, 160]), score=0.9, class_id=0)]
    tracker.update(det)   # spawn (tentative)
    tracker.update(det)   # match -> confirmed, survives future misses
    # Next frame: no detection, but a big camera pan -> the coasting confirmed
    # track's predicted centre must shift by ~ the camera translation.
    cx_before = tracker.tracks[0].mean[0]
    tracker.update([], camera_shift=(20.0, 0.0))
    cx_after = tracker.tracks[0].mean[0]
    assert cx_after - cx_before > 15.0  # moved with the camera (+ small KF drift)
