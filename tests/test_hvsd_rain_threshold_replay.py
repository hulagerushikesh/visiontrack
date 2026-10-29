"""One-change paired replay checks without requiring private video or a model."""
import numpy as np
import pytest

from experiments.hvsd_rain_threshold_replay import replay
from visiontrack.detection.base import Detection


def test_lower_threshold_only_yields_public_crossing_after_confirmation():
    frames = [[Detection(
        xyxy=np.array([x - 10, 290, x + 10, 310], dtype=float),
        score=0.57, class_id=2,
    )] for x in (490, 495, 499, 505)]
    result = replay(frames)
    assert result["baseline"]["tentative_births"] == 0
    assert result["baseline"]["public_crossings"] == []
    assert result["candidate"]["tentative_births"] == 1
    assert result["candidate"]["public_track_boxes"] == 2
    assert len(result["candidate"]["public_crossings"]) == 1
    assert result["recommend_default_change"] is False


def test_pinned_baseline_rejects_wrong_receipt():
    with pytest.raises(ValueError, match="baseline differs"):
        replay([[]], expected_receipt="not-a-receipt")
