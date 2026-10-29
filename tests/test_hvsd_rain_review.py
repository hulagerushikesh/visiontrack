"""Contract checks for independent event intake and adjacent-frame crossings."""
import json

import pytest

from experiments.hvsd_rain_review import SOURCE, audit_reviews, line_crossings


def write_review(path, events):
    path.write_text(json.dumps({
        "schema": "visiontrack.hvsd-rain-event-review/v1",
        "source": SOURCE,
        "review_role": "owner_independent_scene_pass",
        "events": events,
        "dense_identity_truth": False,
        "tracker_output_seen_in_page": False,
    }))
    return path


def test_merge_exact_repeat_but_reject_conflicting_mark(tmp_path):
    mark = {"frame": 57, "vehicle": "car", "certainty": "clear"}
    first = write_review(tmp_path / "first.json", [mark])
    second = write_review(tmp_path / "second.json", [mark])
    result = audit_reviews([first, second])
    assert result["exact_duplicate_frames"] == [57]
    assert result["unique_events"] == [mark]
    assert result["complete_negative_frame_review_verified"] is False
    write_review(second, [{**mark, "certainty": "uncertain"}])
    with pytest.raises(ValueError, match="conflicting marks"):
        audit_reviews([first, second])


def test_reject_wrong_source_or_disclosure(tmp_path):
    path = write_review(tmp_path / "review.json", [])
    data = json.loads(path.read_text())
    data["source"]["line"]["x"] = 499
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="wrong review schema or source"):
        audit_reviews([path])
    data["source"] = SOURCE
    data["tracker_output_seen_in_page"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="wrong review role or disclosure"):
        audit_reviews([path])


def test_crossing_requires_adjacent_same_id_and_right_direction():
    rows = [
        (0, 1, 490, 300), (1, 1, 510, 300),  # valid
        (0, 2, 490, 300), (2, 2, 510, 300),  # gap, invalid
        (0, 3, 510, 300), (1, 3, 490, 300),  # wrong direction
        (0, 4, 490, 100), (1, 4, 510, 100),  # outside lower road
        (0, 5, 490, 300), (1, 6, 510, 300),  # changed ID
    ]
    result = line_crossings(rows)
    assert len(result) == 1
    assert result[0]["track_id"] == 1
    assert result[0]["estimated_frame"] == 0.5


def test_crossing_interpolates_y_on_segment_boundary():
    result = line_crossings([(0, 1, 490, 190), (1, 1, 510, 220)])
    assert len(result) == 1
    assert result[0]["crossing_y"] == 205
