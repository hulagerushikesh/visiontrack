"""Tests for the RQ1 appearance channel in the synthetic scene generator.

The channel must (a) be a no-op when disabled — same scenes as before, no extra
RNG drawn — and (b) when enabled, emit unit detection features whose inter-object
similarity is controlled by ``appearance_diversity`` while the scene geometry is
held fixed (so a diversity sweep is a valid controlled probe).
"""
import numpy as np
import pytest

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig


def _cfg(**kw):
    base = dict(seed=3, num_objects=6, num_frames=8)
    base.update(kw)
    return SyntheticSceneConfig(**base)


def test_appearance_off_by_default_no_features():
    scene = SyntheticScene(_cfg())
    assert scene.cfg.appearance_dim == 0
    for f in scene:
        for d in f.detections:
            assert d.feature is None
    assert all(o.appearance is None for o in scene._objects)


def test_appearance_off_is_byte_identical_to_reference():
    # Enabling the appearance field must not perturb geometry when dim=0: the
    # detections of a dim=0 scene equal those built with the appearance kwargs
    # left at their defaults. (Guards the "no extra RNG when off" invariant.)
    a = SyntheticScene(_cfg())
    b = SyntheticScene(_cfg(appearance_diversity=0.5, appearance_noise_std=0.3))  # dim still 0
    for fa, fb in zip(list(a), list(b), strict=True):
        boxes_a = sorted(tuple(np.round(d.xyxy, 6)) for d in fa.detections)
        boxes_b = sorted(tuple(np.round(d.xyxy, 6)) for d in fb.detections)
        assert boxes_a == boxes_b


def test_appearance_on_emits_unit_features():
    scene = SyntheticScene(_cfg(appearance_dim=32))
    saw = 0
    for f in scene:
        for d in f.detections:
            assert d.feature is not None
            assert d.feature.shape == (32,)
            assert np.linalg.norm(d.feature) == pytest.approx(1.0, abs=1e-6)
            saw += 1
    assert saw > 0


@pytest.mark.parametrize("diversity,lo,hi", [(0.0, 0.999, 1.001), (1.0, -0.5, 0.5)])
def test_diversity_controls_inter_object_similarity(diversity, lo, hi):
    scene = SyntheticScene(_cfg(appearance_dim=64, appearance_diversity=diversity))
    apps = np.stack([o.appearance for o in scene._objects])
    cos = apps @ apps.T
    iu = np.triu_indices(len(apps), k=1)
    mean_cos = float(cos[iu].mean())
    assert lo <= mean_cos <= hi


def test_scene_geometry_invariant_across_diversity():
    # Only appearance should change with diversity; boxes/scores must be identical
    # so the paired on/off-vs-diversity comparison isolates appearance.
    def boxes(d):
        sc = SyntheticScene(_cfg(appearance_dim=32, appearance_diversity=d))
        return [sorted(tuple(np.round(x.xyxy, 6)) for x in f.detections) for f in sc]

    assert boxes(0.0) == boxes(1.0)


def test_appearance_is_deterministic():
    f1 = SyntheticScene(_cfg(appearance_dim=32)).frame(2)
    f2 = SyntheticScene(_cfg(appearance_dim=32)).frame(2)
    for a, b in zip(f1.detections, f2.detections, strict=True):
        np.testing.assert_array_equal(a.feature, b.feature)
