"""Read-only review model checks; synthetic data is not actual visual evidence."""
import copy
import json
import re
from pathlib import Path

import pytest

from experiments import mot17_visual_review as review


def fixture(monkeypatch):
    selected = dict(source_window=[36, 57], event=dict(
        source_frame=54, gt_id=85, previous_hyp_id=19, hyp_id=31))
    monkeypatch.setattr(review, "prepare", lambda *args: ({}, selected))
    rows = [dict(source_frame=f, gt_ids=[85, 89], gt_classes=[1, 1], gt_consider=[1, 1],
                 gt_xyxy=[[410, 66, 461, 231], [387, 88, 436, 242]], gt_visibility=[0.5, 0.6],
                 track_ids=[19] if f < 54 else [19, 31],
                 track_xyxy=[[400, 75, 451, 239]] if f < 54 else
                 [[435, 98, 489, 255], [389, 49, 441, 218]],
                 detections_xyxy=[[400, 75, 451, 239]], detection_scores=[0.9])
            for f in range(1, 1051)]
    return {"run-1/raw.jsonl": "\n".join(json.dumps(r) for r in rows).encode()}, selected


def test_model_is_same_fixed_event_with_original_boxes_no_replay(monkeypatch):
    contents, selected = fixture(monkeypatch)
    original = copy.deepcopy((contents, selected))
    value = review.model(contents, {})
    assert [r["source_frame"] for r in value["frames"]] == list(range(36, 58))
    assert value["first_event"] == selected["event"]
    assert value["frames"][0]["references"][0]["box"] == [410, 66, 461, 231]
    assert [r["id"] for r in value["frames"][0]["public_tracks"]] == [19]
    assert [r["id"] for r in value["frames"][18]["public_tracks"]] == [19, 31]
    assert value["frames"][0]["detections"][0]["row"] == 1
    assert not value["independent_review_completed"] and not value["tracker_or_label_changes"]
    assert (contents, selected) == original


@pytest.mark.parametrize("change,message", [
    (lambda selected: selected.update(source_window=[45, 57]), "fixed v2 window"),
    (lambda selected: selected["event"].update(gt_id=89), "same first chronological event"),
])
def test_no_different_event_or_legacy_window(monkeypatch, change, message):
    contents, selected = fixture(monkeypatch)
    change(selected)
    with pytest.raises(ValueError, match=message):
        review.model(contents, {})


def test_missing_source_frame_or_duplicate_reference_refused(monkeypatch):
    contents, _ = fixture(monkeypatch)
    rows = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    rows[35]["gt_ids"] = [85, 85]
    contents["run-1/raw.jsonl"] = "\n".join(json.dumps(r) for r in rows).encode()
    with pytest.raises(ValueError, match="unique target reference"):
        review.model(contents, {})
    rows.pop()
    contents["run-1/raw.jsonl"] = "\n".join(json.dumps(r) for r in rows).encode()
    with pytest.raises(ValueError, match="complete saved source"):
        review.model(contents, {})


def test_render_escapes_script_termination_and_has_no_remote_assets():
    value = {"comment": "</script><script>window.bad=true</script>"}
    html = review.render(value)
    assert "__REVIEW_DATA__" not in html
    assert "\\u003c/script>" in html and "window.bad=true</script>" not in html
    assert "connect-src 'none'" in html
    assert '<script src=' not in html and '<link ' not in html
    assert re.search(r'independent_review_verified:\s*false', html)


def test_bad_image_receipt_refused_before_display(monkeypatch, tmp_path):
    monkeypatch.setattr(review, "read_packet", lambda *args: {})
    with pytest.raises(ValueError, match="image inventory"):
        review.image_packet(tmp_path, "0" * 64)


def test_existing_or_repository_output_refused_before_inputs(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        review.execute(tmp_path, tmp_path, tmp_path, "0" * 64, tmp_path)
    with pytest.raises(ValueError, match="outside repository"):
        review.execute(tmp_path, tmp_path, tmp_path, "0" * 64,
                       Path(__file__).parent / "new-private-review")
