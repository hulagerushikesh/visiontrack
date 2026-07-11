import numpy as np
import pytest

from visiontrack.core.kalman import KalmanBoxTracker, chi2_gating_threshold


@pytest.fixture
def kf():
    return KalmanBoxTracker()


def test_initiate_zero_velocity(kf):
    mean, cov = kf.initiate(np.array([100.0, 100.0, 0.5, 80.0]))
    assert mean.shape == (8,)
    np.testing.assert_allclose(mean[:4], [100, 100, 0.5, 80])
    np.testing.assert_allclose(mean[4:], 0.0)  # velocity starts at rest
    # Covariance is symmetric positive-definite.
    assert np.allclose(cov, cov.T)
    assert np.all(np.linalg.eigvalsh(cov) > 0)


def test_predict_grows_uncertainty(kf):
    mean, cov = kf.initiate(np.array([100.0, 100.0, 0.5, 80.0]))
    trace0 = np.trace(cov)
    _, cov1 = kf.predict(mean, cov)
    assert np.trace(cov1) > trace0  # prediction adds process noise


def test_update_shrinks_uncertainty(kf):
    mean, cov = kf.initiate(np.array([100.0, 100.0, 0.5, 80.0]))
    mean, cov = kf.predict(mean, cov)
    trace_before = np.trace(cov)
    mean2, cov2 = kf.update(mean, cov, np.array([101.0, 99.0, 0.5, 80.0]))
    assert np.trace(cov2) < trace_before  # measurement reduces uncertainty
    assert np.allclose(cov2, cov2.T)      # stays symmetric (Joseph form)


def test_tracks_constant_velocity_object(kf):
    """Feeding noise-free constant-velocity measurements, the filter should
    converge and estimate the true velocity."""
    vx, vy = 4.0, -2.0
    pos = np.array([50.0, 200.0])
    mean, cov = kf.initiate(np.array([pos[0], pos[1], 0.5, 80.0]))
    for step in range(1, 40):
        mean, cov = kf.predict(mean, cov)
        pos_t = pos + np.array([vx, vy]) * step
        mean, cov = kf.update(mean, cov, np.array([pos_t[0], pos_t[1], 0.5, 80.0]))
    # Estimated velocity converges to truth.
    np.testing.assert_allclose(mean[4], vx, atol=0.2)
    np.testing.assert_allclose(mean[5], vy, atol=0.2)


def test_batched_predict_matches_single(kf):
    m0, c0 = kf.initiate(np.array([10.0, 10.0, 0.5, 40.0]))
    m1, c1 = kf.initiate(np.array([90.0, 30.0, 0.7, 90.0]))
    means = np.stack([m0, m1])
    covs = np.stack([c0, c1])

    bm, bc = kf.predict(means, covs)
    sm0, sc0 = kf.predict(m0, c0)
    sm1, sc1 = kf.predict(m1, c1)
    np.testing.assert_allclose(bm[0], sm0)
    np.testing.assert_allclose(bm[1], sm1)
    np.testing.assert_allclose(bc[0], sc0)
    np.testing.assert_allclose(bc[1], sc1)


def test_gating_distance_orders_by_proximity(kf):
    mean, cov = kf.initiate(np.array([100.0, 100.0, 0.5, 80.0]))
    mean, cov = kf.predict(mean, cov)
    measurements = np.array(
        [
            [100.0, 100.0, 0.5, 80.0],  # on top of the prediction
            [130.0, 100.0, 0.5, 80.0],  # a bit off
            [400.0, 400.0, 0.5, 80.0],  # far away
        ]
    )
    d2 = kf.gating_distance(mean, cov, measurements)
    assert d2[0] < d2[1] < d2[2]
    # The far measurement is outside the 95% chi-square gate.
    assert d2[2] > chi2_gating_threshold(4)
    assert d2[0] < chi2_gating_threshold(4)
