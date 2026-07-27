"""Tests for the tracker preset registry (visiontrack.tracking.presets)."""
from __future__ import annotations

import numpy as np
import pytest

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.presets import (
    PRESET_NAMES,
    PRESETS,
    preset,
    preset_overrides,
)
from visiontrack.tracking.tracker import ByteTracker


def test_registry_contains_the_lineage():
    for name in ["sort", "deepsort", "bytetrack", "bytetrack_reid", "bytetrack_giou"]:
        assert name in PRESETS
    assert PRESET_NAMES == list(PRESETS)


def test_preset_builds_valid_config():
    for name in PRESET_NAMES:
        cfg = preset(name)
        assert isinstance(cfg, TrackerConfig)


def test_bytetrack_preset_is_the_default_core():
    # The baseline preset must be behaviourally the plain default config.
    assert preset("bytetrack") == TrackerConfig()
    assert PRESETS["bytetrack"] == {}


def test_single_stage_presets_collapse_the_score_band():
    # "SORT-style" = single stage: low and high thresholds coincide, so the
    # recovery stage receives no detections.
    for name in ["sort", "deepsort"]:
        cfg = preset(name)
        assert cfg.low_score_thresh == cfg.high_score_thresh
    # ByteTrack keeps a real low/high band (two-stage).
    bt = preset("bytetrack")
    assert bt.low_score_thresh < bt.high_score_thresh


def test_appearance_presets_enable_the_reid_term():
    assert preset("deepsort").w_app > 0
    assert preset("bytetrack_reid").w_app > 0
    assert preset("sort").w_app == 0
    assert preset("bytetrack").w_app == 0


def test_giou_preset_uses_giou():
    assert preset("bytetrack_giou").use_giou is True
    assert preset("bytetrack").use_giou is False


def test_extra_overrides_compose():
    cfg = preset("sort", max_age=15)
    assert cfg.max_age == 15
    assert cfg.low_score_thresh == cfg.high_score_thresh  # preset still applied


def test_preset_overrides_returns_a_copy():
    d = preset_overrides("bytetrack_reid")
    d["w_app"] = 999.0
    assert PRESETS["bytetrack_reid"]["w_app"] != 999.0  # registry untouched


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        preset("not_a_tracker")
    with pytest.raises(KeyError):
        preset_overrides("not_a_tracker")


def test_every_preset_runs_end_to_end_on_a_synthetic_scene():
    # Smoke test: each preset drives a full sequence and returns sane output.
    scene_cfg = SyntheticSceneConfig(
        num_objects=5, num_frames=30, seed=7,
        appearance_dim=32, appearance_diversity=0.7,  # so Re-ID presets are live
    )
    for name in PRESET_NAMES:
        scene = SyntheticScene(scene_cfg)
        tracker = ByteTracker(preset(name))
        total_obs = 0
        for frame in scene:
            obs = tracker.update(frame.detections)
            total_obs += len(obs)
            for o in obs:
                assert o.xyxy.shape == (4,)
                assert np.all(np.isfinite(o.xyxy))
        assert total_obs > 0, f"preset {name!r} produced no observations"
