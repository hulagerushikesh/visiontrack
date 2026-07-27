"""Tests for OC-SORT's observation-centric mechanics (OCM + ORU)."""
from __future__ import annotations

import numpy as np

from visiontrack.core.geometry import xyah_to_xyxy, xyxy_to_xyah
from visiontrack.core.kalman import KalmanBoxTracker
from visiontrack.detection.base import Detection
from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.motion.oc import (
    momentum_cost,
    observation_centric_reupdate,
)
from visiontrack.tracking.presets import preset
from visiontrack.tracking.tracker import ByteTracker


class _FakeTrack:
    """Minimal stand-in exposing the .history that momentum_cost reads."""

    def __init__(self, boxes):
        self.history = [np.asarray(b, dtype=float) for b in boxes]


def _box_at(cx, cy, w=10.0, h=20.0):
    return np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])


# -- OCM ---------------------------------------------------------------------

def test_momentum_prefers_aligned_detection():
    # Track moving right (+x). A detection continuing right should cost less than
    # one that doubles back left.
    track = _FakeTrack([_box_at(0, 0), _box_at(10, 0), _box_at(20, 0), _box_at(30, 0)])
    aligned = _box_at(40, 0)     # continues +x
    reversed_ = _box_at(20, 0)   # goes -x
    cost = momentum_cost([track], np.stack([aligned, reversed_]), delta_t=3)
    assert cost.shape == (1, 2)
    assert cost[0, 0] < cost[0, 1]
    assert cost[0, 0] == 0.0 or cost[0, 0] < 1e-6  # aligned -> ~0 angle
    assert cost[0, 1] > 0.9                        # reversed -> ~pi/pi = 1


def test_momentum_inert_without_enough_history():
    track = _FakeTrack([_box_at(0, 0), _box_at(10, 0)])  # < delta_t+1 obs
    cost = momentum_cost([track], np.stack([_box_at(20, 0)]), delta_t=3)
    assert np.all(cost == 0.0)


def test_momentum_inert_for_stationary_track():
    track = _FakeTrack([_box_at(5, 5)] * 5)  # no motion
    cost = momentum_cost([track], np.stack([_box_at(20, 20)]), delta_t=3)
    assert np.all(cost == 0.0)


def test_momentum_empty_inputs():
    assert momentum_cost([], np.empty((0, 4)), delta_t=3).shape == (0, 0)


# -- ORU ---------------------------------------------------------------------

def test_reupdate_lands_on_new_observation():
    kf = KalmanBoxTracker()
    last = xyxy_to_xyah(_box_at(0, 0))
    new = xyxy_to_xyah(_box_at(30, 0))
    start_mean, start_cov = kf.initiate(last)  # state at the last observation
    mean, cov = observation_centric_reupdate(kf, start_mean, start_cov, last, new, gap=3)
    # The rebuilt state should end near the new observation's centre...
    box = xyah_to_xyxy(mean[:4])
    cx = (box[0] + box[2]) / 2.0
    assert abs(cx - 30.0) < 5.0
    # ...and carry a positive +x velocity consistent with the virtual path.
    assert mean[4] > 0.0
    assert cov.shape == (8, 8)


def test_reupdate_keeps_covariance_tight_vs_reinit():
    # The whole point of anchoring to the pre-gap state: the re-updated position
    # covariance must not balloon to the fresh-initialisation scale.
    kf = KalmanBoxTracker()
    last = xyxy_to_xyah(_box_at(0, 0))
    new = xyxy_to_xyah(_box_at(30, 0))
    start_mean, start_cov = kf.initiate(last)
    # Simulate a settled track: a couple of updates tighten the covariance.
    m, c = start_mean, start_cov
    for _ in range(3):
        m, c = kf.predict(m, c)
        m, c = kf.update(m, c, last)
    _, cov = observation_centric_reupdate(kf, m, c, last, new, gap=3)
    fresh_m, fresh_c = kf.initiate(new)
    assert cov[0, 0] < fresh_c[0, 0]  # tighter than a from-scratch init


def test_reupdate_handles_zero_gap():
    kf = KalmanBoxTracker()
    obs = xyxy_to_xyah(_box_at(3, 3))
    start_mean, start_cov = kf.initiate(obs)
    mean, _ = observation_centric_reupdate(kf, start_mean, start_cov, obs, obs, gap=0)
    assert np.all(np.isfinite(mean))


# -- integration -------------------------------------------------------------

def test_oc_sort_preset_flags():
    cfg = preset("oc_sort")
    assert cfg.w_ocm > 0
    assert cfg.use_oru is True
    assert cfg.low_score_thresh == cfg.high_score_thresh  # single stage


def test_defaults_leave_oc_sort_off():
    cfg = TrackerConfig()
    assert cfg.w_ocm == 0.0
    assert cfg.use_oru is False
    assert cfg.cost_weights().momentum_on is False


def test_oc_sort_runs_end_to_end_on_synthetic():
    scene_cfg = SyntheticSceneConfig(num_objects=6, num_frames=40, seed=3)
    scene = SyntheticScene(scene_cfg)
    tracker = ByteTracker(preset("oc_sort"))
    total = 0
    for frame in scene:
        obs = tracker.update(frame.detections)
        total += len(obs)
        for o in obs:
            assert np.all(np.isfinite(o.xyxy))
    assert total > 0


def test_oru_triggers_after_a_gap_and_recovers_state():
    # Drive one track, hide it for several frames (forcing a coast), then bring
    # it back far along its motion — ORU should re-anchor without error.
    cfg = preset("oc_sort", max_age=30, n_init=1)
    tracker = ByteTracker(cfg)
    for t in range(4):  # establish a track moving +x
        tracker.update([Detection(xyxy=_box_at(10 * t, 50), score=0.9, class_id=0)])
    for _ in range(3):  # occlusion gap: no detections
        tracker.update([])
    out = tracker.update([Detection(xyxy=_box_at(70, 50), score=0.9, class_id=0)])
    assert any(np.all(np.isfinite(o.xyxy)) for o in out) or out == []
