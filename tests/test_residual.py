"""Tests for the from-scratch learned motion residual (RQ2).

Pure NumPy — no Torch, no dataset — so these run in CI. Cover the feature
builder, the MLP's training/serialization, the no-op inference guard, and the
end-to-end claim that the residual can learn a systematic maneuver that constant
velocity misses.
"""
import numpy as np

from visiontrack.tracking.motion.residual import (
    WINDOW,
    MLPResidual,
    MotionResidual,
    residual_features,
)


def test_features_shape_and_scale():
    c = np.cumsum(np.ones((WINDOW + 3, 2)), axis=0)  # constant velocity (1,1)
    f = residual_features(c, scale=2.0)
    assert f.shape == (2 * WINDOW,)
    # constant velocity 1 / scale 2 -> every entry 0.5
    np.testing.assert_allclose(f, 0.5, atol=1e-9)


def test_features_zero_pads_short_track():
    c = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])  # only 2 velocities
    f = residual_features(c, scale=1.0).reshape(WINDOW, 2)
    assert np.all(f[: WINDOW - 2] == 0.0)  # earlier slots padded
    np.testing.assert_allclose(f[-2:, 0], 1.0)


def test_mlp_overfits_a_learnable_target():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 2 * WINDOW))
    W = rng.normal(size=(2 * WINDOW, 2))
    Y = np.tanh(X @ W)  # a smooth learnable map
    m = MLPResidual(seed=0)
    losses = m.fit(X, Y, epochs=120, lr=5e-3, seed=0)
    assert losses[-1] < losses[0] * 0.5  # training error at least halves


def test_save_load_roundtrip(tmp_path):
    m = MLPResidual(seed=1)
    X = np.random.default_rng(1).normal(size=(5, 2 * WINDOW))
    before = m.predict(X)
    p = tmp_path / "resid.npz"
    m.save(str(p))
    after = MLPResidual.load(str(p)).predict(X)
    np.testing.assert_allclose(before, after)


def test_motion_residual_is_noop_without_model():
    mr = MotionResidual(None)
    corr = mr.correct(np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]), scale=1.0)
    np.testing.assert_array_equal(corr, [0.0, 0.0])
    assert MotionResidual.from_path(None).model is None


def test_residual_reduces_error_on_a_systematic_maneuver():
    # Constant-acceleration motion: CV (which assumes constant velocity) lags by a
    # predictable amount each step. The residual should learn to cancel that lag.
    def traj(x0, a, n=WINDOW + 6):
        t = np.arange(n)[:, None]
        return x0 + 2.0 * t + 0.5 * a * t ** 2  # position with acceleration a (2-D)

    rng = np.random.default_rng(0)
    X, Y = [], []
    for _ in range(300):
        a = rng.uniform(-0.6, 0.6, size=2)
        c = traj(rng.uniform(0, 50, size=2), a)
        for t in range(WINDOW, len(c) - 1):
            cv = c[t] + (c[t] - c[t - 1])
            X.append(residual_features(c[: t + 1], 1.0))
            Y.append(c[t + 1] - cv)
    m = MLPResidual(seed=0)
    m.fit(np.array(X), np.array(Y), epochs=150, lr=5e-3, seed=0)

    # Held-out maneuvers: residual-corrected error must beat pure CV.
    cv_err, res_err = [], []
    for _ in range(60):
        a = rng.uniform(-0.6, 0.6, size=2)
        c = traj(rng.uniform(0, 50, size=2), a)
        for t in range(WINDOW, len(c) - 1):
            cv = c[t] + (c[t] - c[t - 1])
            corr = m.predict(residual_features(c[: t + 1], 1.0))[0]
            cv_err.append(np.linalg.norm(c[t + 1] - cv))
            res_err.append(np.linalg.norm(c[t + 1] - (cv + corr)))
    assert np.mean(res_err) < 0.5 * np.mean(cv_err)  # clearly better on maneuvers


def test_tracker_runs_with_residual(tmp_path):
    # Integration smoke: a tracker with a residual model still tracks a scene.
    from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    MLPResidual(seed=0).save(str(tmp_path / "r.npz"))
    tracker = ByteTracker(TrackerConfig(motion_residual_path=str(tmp_path / "r.npz")))
    scene = SyntheticScene(SyntheticSceneConfig(seed=0, num_frames=20, num_objects=4))
    seen = set()
    for f in scene:
        for o in tracker.update(f.detections):
            seen.add(o.track_id)
    assert len(seen) >= 1
