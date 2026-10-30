"""The public diagnostic view must retain observations and their evidence limits."""
import copy
import json
from pathlib import Path

import pytest

from experiments.hvsd_rain_diagnosis import export, project

ROOT = Path(__file__).parents[1]
SNAPSHOT = ROOT / "src/features/crossing-diagnosis/rain.json"


def inputs():
    data = json.loads(SNAPSHOT.read_text())
    review = {
        "source": {"video_sha256": data["source_video_sha256"], "line": data["line"]},
        "unique_events": [{"frame": c["mark_frame"]} for c in data["cases"]],
        "exploratory_pipeline": {
            "pipeline_receipt": data["baseline_receipt"],
            "diagnostic_frames": [f for c in data["cases"] for f in c["frames"]],
            "crossings": data["baseline"]["public_crossings"],
            "crossing_rule": data["crossing_rule"],
            "diagnostic_window_rule": data["diagnostic_window_rule"],
        },
        "dense_identity_truth": False,
        "owner_attested_all_194_frames_reviewed": True,
        "private_contact": "must not be exported",
    }
    trace = {
        **data["settings"],
        "pipeline_receipt": data["baseline_receipt"],
        "source_video_sha256": data["source_video_sha256"],
        "model_sha256": data["model_sha256"],
        "mark_frames": [c["mark_frame"] for c in data["cases"]],
        "pairs": [p for c in data["cases"] for p in c["association_pairs"]],
        "physical_object_correspondence_verified": False,
    }
    paired = {
        **{k: data[k] for k in ("baseline_receipt", "source_video_sha256", "model_sha256",
                               "frame_count", "baseline", "candidate",
                               "candidate_changed_setting_only")},
        "accuracy_claim": False,
        "recommend_default_change": False,
        "post_hoc_development_only": True,
    }
    return data, review, trace, paired


def test_projection_retains_all_case_observations_without_private_review_fields():
    expected, review, trace, paired = inputs()
    before = copy.deepcopy((review, trace, paired))
    result = project(review, trace, paired)
    assert result == expected
    assert (review, trace, paired) == before
    assert "private_contact" not in json.dumps(result)
    assert len([f for c in result["cases"] for f in c["frames"]]) == 45
    assert [c["mark_frame"] for c in result["cases"]] == [27, 37, 57, 92, 160]


@pytest.mark.parametrize("breakage", ["receipt", "source", "model", "frames", "marks",
                                      "crossings", "accuracy", "acceptance", "identity"])
def test_inconsistent_or_overstated_evidence_cannot_be_exported(breakage):
    _, review, trace, paired = inputs()
    if breakage == "receipt":
        trace["pipeline_receipt"] = "different-run"
    elif breakage == "source":
        paired["source_video_sha256"] = "different-video"
    elif breakage == "model":
        paired["model_sha256"] = "different-model"
    elif breakage == "frames":
        review["exploratory_pipeline"]["diagnostic_frames"].pop()
    elif breakage == "marks":
        trace["mark_frames"] = [27]
    elif breakage == "crossings":
        paired["baseline"]["public_crossings"] = []
    elif breakage == "accuracy":
        paired["accuracy_claim"] = True
    elif breakage == "acceptance":
        paired["recommend_default_change"] = True
    elif breakage == "identity":
        trace["physical_object_correspondence_verified"] = True
    with pytest.raises(ValueError):
        project(review, trace, paired)


def test_export_rejects_edited_original_record(tmp_path):
    (tmp_path / "rain-review-audit.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="pinned source record changed"):
        export(tmp_path)


def test_recorded_case_numbers_support_the_explanations():
    data, *_ = inputs()
    by_mark = {c["mark_frame"]: c for c in data["cases"]}
    assert len(by_mark[27]["baseline_crossings"]) == 1
    assert not by_mark[57]["baseline_crossings"]
    assert len(by_mark[57]["candidate_crossings"]) == 1
    frames = {f["frame"]: f for f in by_mark[57]["frames"]}
    for frame, x, score in [(57, 494.8, 0.577), (58, 500.3, 0.597)]:
        assert any(d["center_x"] == x and d["score"] == score
                   for d in frames[frame]["near_line_detections"])
        assert score < data["settings"]["new_track_score_min"]
    assert all(not f["near_line_detections"] for f in by_mark[92]["frames"])
    pair = next(p for p in by_mark[160]["association_pairs"]
                if p["frame"] == 162 and p["tentative_track_id"] == 16)
    assert pair["iou_gate_pass"] and pair["class_gate_pass"]
    assert not pair["mahalanobis_gate_pass"] and not pair["matched"]
    assert pair["mahalanobis_d2"] == 33.107
    assert data["baseline"]["public_track_boxes"] == 117
    assert data["candidate"]["public_track_boxes"] == 143
