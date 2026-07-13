"""Tests for RQ3: Kalman calibration and detector-noise injection."""
import numpy as np
import pytest

from visiontrack.detection.base import Detection
from visiontrack.detection.mot_loader import FrameData
from visiontrack.detection.noise import NoiseConfig, PerturbedSequence, perturb_detections
from visiontrack.eval.calibration import innovation_chi2_samples, reliability_curve
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


class _FakeGTReader:
    """One pedestrian moving linearly; no detections."""

    def __init__(self, n=20):
        self.n = n
        self.name = "fake"
        self.width = 1000
        self.height = 1000

    def __len__(self):
        return self.n

    def frame(self, idx):
        cx = 100 + 5 * idx
        box = np.array([[cx - 20, 100 - 40, cx + 20, 100 + 40]], dtype=float)
        return FrameData(
            frame=idx, det_xyxy=np.empty((0, 4)), det_scores=np.empty((0,)),
            gt_xyxy=box, gt_ids=np.array([1]), gt_classes=np.array([1]),
            gt_conf=np.array([1.0]), gt_vis=np.array([1.0]),
        )


# -- calibration --------------------------------------------------------------
def test_innovation_samples_shape_and_nonneg():
    reader = _FakeGTReader(20)
    d2 = innovation_chi2_samples(reader, 1, 20)
    assert d2.size == 19          # one per consecutive-frame prediction
    assert np.all(d2 >= 0) and np.all(np.isfinite(d2))


def test_smaller_scale_increases_chi2():
    """Shrinking the filter noise (more confident) raises innovation χ²."""
    reader = _FakeGTReader(30)
    big = innovation_chi2_samples(reader, 1, 30, noise_scale=1.0)
    small = innovation_chi2_samples(reader, 1, 30, noise_scale=0.2)
    assert small.mean() > big.mean()


def test_reliability_curve_fields():
    reader = _FakeGTReader(40)
    d2 = innovation_chi2_samples(reader, 1, 40)
    res = reliability_curve(d2, dof=4)
    assert res.n == d2.size
    assert res.calibration_factor == pytest.approx(d2.mean() / 4)
    assert np.all(np.diff(res.theoretical) >= 0)  # theoretical quantiles sorted


# -- noise injection ----------------------------------------------------------
def _dets():
    return [
        Detection(xyxy=[10, 10, 50, 90], score=0.9, class_id=0),
        Detection(xyxy=[100, 100, 140, 180], score=0.8, class_id=0),
    ]


def test_perturb_no_drop_no_fp_keeps_count():
    cfg = NoiseConfig(drop_prob=0.0, fp_rate=0.0, jitter_std=5.0)
    out = perturb_detections(_dets(), np.random.default_rng(0), cfg, 1000, 1000)
    assert len(out) == 2
    for d in out:  # boxes stay valid (non-degenerate)
        assert d.xyxy[2] > d.xyxy[0] and d.xyxy[3] > d.xyxy[1]


def test_perturb_drop_removes_and_fp_adds():
    dropped = perturb_detections(
        _dets(), np.random.default_rng(1), NoiseConfig(drop_prob=1.0, fp_rate=0.0), 1000, 1000
    )
    assert dropped == []  # everything dropped
    fps = perturb_detections(
        [], np.random.default_rng(2), NoiseConfig(fp_rate=5.0), 1000, 1000
    )
    assert len(fps) > 0  # spurious detections created


def test_perturb_is_deterministic():
    a = perturb_detections(_dets(), np.random.default_rng([0, 3]), NoiseConfig(), 1000, 1000)
    b = perturb_detections(_dets(), np.random.default_rng([0, 3]), NoiseConfig(), 1000, 1000)
    assert len(a) == len(b)
    for da, db in zip(a, b, strict=False):
        np.testing.assert_array_equal(da.xyxy, db.xyxy)


def test_perturbed_sequence_passthrough_gt_and_determinism():
    base = _FakeGTReader(10)
    seq = PerturbedSequence(base, NoiseConfig(), seed=7)
    f1 = seq.frame(4)
    f2 = seq.frame(4)
    # ground truth untouched; detections deterministic per (seed, frame)
    np.testing.assert_array_equal(f1.gt_xyxy, base.frame(4).gt_xyxy)
    np.testing.assert_array_equal(f1.det_xyxy, f2.det_xyxy)


# -- calibration knob is wired and behavior-preserving at scale 1 -------------
def test_kf_noise_scale_default_is_unchanged():
    a = ByteTracker(TrackerConfig())
    b = ByteTracker(TrackerConfig(kf_noise_scale=1.0))
    # both build the same default filter
    assert a.kf._std_weight_position == b.kf._std_weight_position


def test_calibrated_tracker_runs():
    tracker = ByteTracker(TrackerConfig(kf_noise_scale=0.19, w_unc=0.5))
    ids = set()
    for t in range(12):
        cx = 100 + 5 * t
        det = Detection(xyxy=[cx - 20, 60, cx + 20, 140], score=0.9, class_id=0)
        for o in tracker.update([det]):
            ids.add(o.track_id)
    assert len(ids) == 1
