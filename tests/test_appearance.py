"""Tests for the appearance embedders, EMA gallery, and cost-level routing."""
import numpy as np
import pytest

from visiontrack.appearance.embedder import ColorHistogramEmbedder, IdentityEmbedder
from visiontrack.appearance.gallery import normalize, update_gallery
from visiontrack.core.assignment import associate
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.cost import CostWeights, appearance_distance, build_association_cost
from visiontrack.tracking.tracker import ByteTracker


# -- gallery ------------------------------------------------------------------
def test_gallery_first_update_adopts_and_normalizes():
    g = update_gallery(None, np.array([3.0, 4.0]), alpha=0.9)
    np.testing.assert_allclose(g, [0.6, 0.8])  # 3-4-5 triangle, L2-normalized


def test_gallery_ema_moves_toward_new():
    old = normalize(np.array([1.0, 0.0]))
    updated = update_gallery(old, np.array([0.0, 1.0]), alpha=0.9)
    # mostly old (alpha=0.9) but nudged toward new; unit length
    assert updated[0] > updated[1] > 0
    assert np.linalg.norm(updated) == pytest.approx(1.0)


# -- embedders ----------------------------------------------------------------
def test_color_histogram_dim_and_normalization():
    emb = ColorHistogramEmbedder(h_bins=16, s_bins=8, v_bins=8)
    assert emb.dim == 32
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, size=(120, 120, 3), dtype=np.uint8)
    feats = emb.embed(img, np.array([[10, 10, 60, 90]]))
    assert feats.shape == (1, 32)
    assert np.linalg.norm(feats[0]) == pytest.approx(1.0, abs=1e-6)


def test_color_histogram_distinguishes_colors():
    emb = ColorHistogramEmbedder()
    red = np.zeros((50, 50, 3), dtype=np.uint8)
    red[..., 0] = 200
    blue = np.zeros((50, 50, 3), dtype=np.uint8)
    blue[..., 2] = 200
    box = np.array([[0, 0, 50, 50]])
    fr = emb.embed(red, box)[0]
    fb = emb.embed(blue, box)[0]
    # same colour -> identical; different colour -> clearly different
    assert np.allclose(fr, emb.embed(red, box)[0])
    assert 1.0 - float(fr @ fb) > 0.3


def test_identity_embedder_returns_injected_vectors():
    vecs = np.array([[1.0, 0.0], [0.0, 1.0]])
    emb = IdentityEmbedder(vecs)
    out = emb.embed(np.zeros((10, 10, 3)), np.zeros((2, 4)))
    np.testing.assert_allclose(out, vecs)


# -- the key proof: appearance routes an otherwise-ambiguous assignment -------
def test_appearance_breaks_motion_tie():
    """Two tracks and two detections with *symmetric* IoU (motion cannot
    distinguish), but appearance matches track0↔det0 and track1↔det1. With
    w_app>0 the appearance-consistent pairing must win; the cross pairing is
    pushed past max_cost and rejected."""
    fa, fb = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    ious = np.array([[0.6, 0.6], [0.6, 0.6]])  # perfectly symmetric
    appear = appearance_distance(np.stack([fa, fb]), np.stack([fa, fb]))

    cost, max_cost = build_association_cost(
        ious, CostWeights(w_iou=1.0, w_app=1.0), iou_thresh=0.3, appearance=appear
    )
    matches, _, _ = associate(cost, max_cost)
    pairs = {tuple(m) for m in matches.tolist()}
    assert pairs == {(0, 0), (1, 1)}


def test_appearance_off_leaves_symmetric_cost():
    fa, fb = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    ious = np.array([[0.6, 0.6], [0.6, 0.6]])
    appear = appearance_distance(np.stack([fa, fb]), np.stack([fa, fb]))
    cost, _ = build_association_cost(
        ious, CostWeights(w_app=0.0), iou_thresh=0.3, appearance=appear
    )
    # appearance ignored -> cost stays symmetric (all equal)
    assert np.allclose(cost, cost[0, 0])


# -- end-to-end: features propagate into the track gallery --------------------
def _det(cx, feat, w=40, h=80, score=0.9):
    return Detection(
        xyxy=[cx - w / 2, 100 - h / 2, cx + w / 2, 100 + h / 2],
        score=score, class_id=0, feature=np.asarray(feat, dtype=float),
    )


def test_track_feature_updates_via_ema_end_to_end():
    tracker = ByteTracker(TrackerConfig(w_app=0.3, appearance_ema_alpha=0.8))
    for t in range(6):
        tracker.update([_det(100 + 5 * t, [1.0, 0.0])])
    track = tracker.tracks[0]
    assert track.feature is not None
    assert np.linalg.norm(track.feature) == pytest.approx(1.0, abs=1e-6)
    # gallery converged toward the (constant) detection embedding
    assert track.feature[0] > 0.99


def test_appearance_on_keeps_single_object_stable():
    tracker = ByteTracker(TrackerConfig(w_app=0.5))
    ids = set()
    for t in range(15):
        for o in tracker.update([_det(100 + 5 * t, [1.0, 0.0])]):
            ids.add(o.track_id)
    assert len(ids) == 1


# -- OnnxReID: preprocessing + fixed-batch logic (no model / onnxruntime) -----
# The real .onnx weights are gitignored and onnxruntime isn't a core dep, so we
# exercise the deterministic logic (ImageNet normalization, batch padding, row
# slicing, L2-norm) against a fake session, bypassing __init__.
from visiontrack.appearance.reid_onnx import _IMAGENET_MEAN, _IMAGENET_STD, OnnxReID  # noqa: E402


class _FakeSession:
    """Records the batch size it was handed; returns a per-image constant."""

    def __init__(self, batch, dim):
        self.batch, self.dim, self.seen = batch, dim, []

    def run(self, _outputs, feed):
        x = next(iter(feed.values()))
        self.seen.append(x.shape[0])
        # one scalar per image (mean of its pixels), broadcast to dim
        vals = x.reshape(x.shape[0], -1).mean(axis=1, keepdims=True)
        return [np.repeat(vals, self.dim, axis=1).astype(np.float32)]


def _fake_reid(batch=16, dim=512, h=256, w=128):
    o = OnnxReID.__new__(OnnxReID)
    o._session = _FakeSession(batch, dim)
    o._input_name = "input"
    o.batch, o.input_h, o.input_w, o.dim = batch, h, w, dim
    o.mean, o.std, o.bgr = _IMAGENET_MEAN, _IMAGENET_STD, False
    return o


def test_onnx_preprocess_applies_imagenet_normalization():
    reid = _fake_reid()
    gray = np.full((50, 30, 3), 128, dtype=np.uint8)  # ~0.502 after /255
    chw = reid._preprocess(gray)
    assert chw.shape == (3, 256, 128)  # CHW at the model's spatial size
    expected = (128 / 255.0 - _IMAGENET_MEAN) / _IMAGENET_STD
    for c in range(3):
        assert chw[c].mean() == pytest.approx(expected[c], abs=1e-4)


def test_onnx_pads_partial_batch_and_slices_back():
    reid = _fake_reid(batch=16)
    img = np.random.default_rng(0).integers(0, 255, (400, 200, 3), dtype=np.uint8)
    boxes = np.array([[10, 10, 40, 90], [50, 20, 90, 120], [100, 30, 150, 200]], float)
    feats = reid.embed(img, boxes)
    assert feats.shape == (3, 512)
    assert reid._session.seen == [16]  # padded up to the fixed batch, one call
    for row in feats:
        assert np.linalg.norm(row) == pytest.approx(1.0, abs=1e-6)


def test_onnx_chunks_more_than_one_batch():
    reid = _fake_reid(batch=16)
    img = np.random.default_rng(1).integers(0, 255, (500, 500, 3), dtype=np.uint8)
    boxes = np.array([[i, i, i + 20, i + 40] for i in range(20)], float)  # 20 > 16
    feats = reid.embed(img, boxes)
    assert feats.shape == (20, 512)
    assert reid._session.seen == [16, 16]  # 16 + (4 padded to 16)


def test_onnx_zero_area_box_maps_to_zero_row():
    reid = _fake_reid(batch=16)
    img = np.random.default_rng(2).integers(0, 255, (200, 200, 3), dtype=np.uint8)
    boxes = np.array([[10, 10, 60, 90], [30, 30, 30, 30]], float)  # 2nd degenerate
    feats = reid.embed(img, boxes)
    assert np.linalg.norm(feats[0]) == pytest.approx(1.0, abs=1e-6)
    assert np.all(feats[1] == 0.0)
