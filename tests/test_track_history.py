"""Storage policy must preserve actual solver/filter/lifecycle behavior."""
from dataclasses import replace

import numpy as np
import pytest

from visiontrack import ByteTracker, Detection, TrackerConfig
from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.tracking.motion.residual import WINDOW, MLPResidual
from visiontrack.tracking.presets import PRESET_NAMES, preset


class FullHistoryReference(ByteTracker):
    """Keep the pre-optimization residual calculation as a numerical oracle."""

    def _apply_residual(self, track):
        if self._residual.model is None or len(track.history) < 2:
            return
        centers = np.array([[(b[0] + b[2]) / 2., (b[1] + b[3]) / 2.]
                            for b in track.history])
        corr = self._residual.correct(centers, float(track.mean[3]))
        track.mean[0] += corr[0]
        track.mean[1] += corr[1]


def assert_same_step(full, bounded, detections, camera_shift=None):
    before = [(d.xyxy.tobytes(), None if d.feature is None else d.feature.tobytes())
              for d in detections]
    left = full.update(detections, camera_shift=camera_shift)
    right = bounded.update(detections, camera_shift=camera_shift)
    assert len(left) == len(right)
    for a, b in zip(left, right, strict=True):
        assert (a.frame, a.track_id, a.score, a.class_id) == (
            b.frame, b.track_id, b.score, b.class_id,
        )
        assert a.xyxy.tobytes() == b.xyxy.tobytes()
    assert before == [(d.xyxy.tobytes(), None if d.feature is None else d.feature.tobytes())
                      for d in detections]
    assert len(full.tracks) == len(bounded.tracks)
    for a, b in zip(full.tracks, bounded.tracks, strict=True):
        assert (a.track_id, a.state, a.hits, a.age, a.time_since_update) == (
            b.track_id, b.state, b.hits, b.age, b.time_since_update,
        )
        for name in ("mean", "covariance", "last_observation"):
            assert getattr(a, name).tobytes() == getattr(b, name).tobytes()
        for av, bv in zip(a.last_obs_state, b.last_obs_state, strict=True):
            assert av.tobytes() == bv.tobytes()
        assert (None if a.feature is None else a.feature.tobytes()) == (
            None if b.feature is None else b.feature.tobytes()
        )
        assert isinstance(b.history, list)
        assert len(b.history) <= bounded.history_limit
        assert [box.tobytes() for box in b.history] == [
            box.tobytes() for box in a.history[-bounded.history_limit:]
        ]
    return left


@pytest.mark.parametrize("name", [*PRESET_NAMES, "combined"])
def test_bounded_history_exact_across_motion_appearance_and_lifecycle(name, tmp_path):
    cfg = preset(name) if name != "combined" else TrackerConfig(
        w_app=.3, w_unc=.2, w_ocm=.2, ocm_delta_t=9, use_oru=True, use_gmc=True,
    )
    if name == "combined":
        model = MLPResidual(seed=7)
        model.W2 *= .01
        model.save(str(tmp_path / "residual.npz"))
        cfg.motion_residual_path = str(tmp_path / "residual.npz")
    limit = max(WINDOW + 1, cfg.ocm_delta_t + 1)
    full = FullHistoryReference(replace(cfg))
    bounded = ByteTracker(replace(cfg), history_limit=limit)
    scene = SyntheticScene(SyntheticSceneConfig(
        num_frames=180, num_objects=6, appearance_dim=8, seed=19,
    ))
    for frame in scene:
        shift = (.1, -.05) if cfg.use_gmc else None
        assert_same_step(full, bounded, frame.detections, shift)
    for _ in range(cfg.max_age + 2):
        assert_same_step(full, bounded, [])
    assert full.tracks == bounded.tracks == []


@pytest.mark.parametrize("n_init", [1, 3, 20])
def test_default_history_is_complete_bounded_tail_survives_gaps_and_reset(n_init):
    cfg = TrackerConfig(n_init=n_init, max_age=4, use_oru=True, w_ocm=.2)
    full = ByteTracker(replace(cfg))
    bounded = ByteTracker(replace(cfg), history_limit=6)
    for _ in range(2):
        for frame in range(90):
            detections = [] if frame in (30, 31) else [
                Detection([10., 20., 30., 60.], .9, 1),
            ]
            assert_same_step(full, bounded, detections)
        assert len(full.tracks) == len(bounded.tracks) == 1
        assert isinstance(full.tracks[0].history, list)
        assert len(full.tracks[0].history) == 88  # matched boxes, not elapsed frames
        assert len(bounded.tracks[0].history) == 6
        full.reset()
        bounded.reset()
        assert full.frame_index == bounded.frame_index == -1
        assert not bounded.tracks
        assert bounded.history_limit == 6


def test_residual_tail_optimization_matches_full_history_without_retention_limit(tmp_path):
    model = MLPResidual(seed=11)
    model.W2 *= .01
    model.save(str(tmp_path / "residual.npz"))
    cfg = TrackerConfig(motion_residual_path=str(tmp_path / "residual.npz"))
    full = FullHistoryReference(replace(cfg))
    optimized = ByteTracker(replace(cfg))
    for frame in range(100):
        dets = [Detection([10. + .1 * frame, 20., 30. + .1 * frame, 60.], .9, 1)]
        left, right = full.update(dets), optimized.update(dets)
        assert [o.xyxy.tobytes() for o in left] == [o.xyxy.tobytes() for o in right]
        assert full.tracks[0].mean.tobytes() == optimized.tracks[0].mean.tobytes()
    assert len(optimized.tracks[0].history) == 100


@pytest.mark.parametrize("limit", [True, False, 6., "6", 0, -1, 5])
def test_invalid_or_insufficient_limit_is_refused(limit):
    with pytest.raises(ValueError, match="history_limit"):
        ByteTracker(history_limit=limit)


def test_larger_ocm_window_requires_more_history_even_when_currently_disabled():
    cfg = TrackerConfig(ocm_delta_t=8)
    with pytest.raises(ValueError, match=">= 9"):
        ByteTracker(cfg, history_limit=6)


def test_mutated_config_is_refused_before_advancing_any_tracker_state():
    cfg = TrackerConfig()
    tracker = ByteTracker(cfg, history_limit=6)
    tracker.update([Detection([10., 20., 30., 60.], .9, 1)])
    before = tracker.tracks[0].mean.tobytes()
    cfg.ocm_delta_t = 6
    with pytest.raises(ValueError, match=">= 7"):
        tracker.update([])
    assert tracker.frame_index == 0
    assert tracker.tracks[0].age == 1
    assert tracker.tracks[0].mean.tobytes() == before
