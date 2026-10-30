"""Export the existing rain diagnosis for the web UI, without replay or pixels.

This is a projection of three pinned exploratory records, not a new evaluation.
Only numeric pipeline observations are exported; private filenames and review
downloads are excluded. Original records remain in the owner-local workspace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_DIGESTS = {
    "rain-review-audit.json": "859df63a7fbec9ed7975c2af35a13cdf139188e42c9183c17a490a66593551c4",
    "rain-gate-trace.json": "3270841e737c98eb148350ac416e2b574a6c3883dc632d1e3f91319888df5508",
    "rain-threshold-replay.json": (
        "0b4a4e3231d929eca1214c17b69e37ddc258732097fd27c43628025eabeab4bc"),
}


def project(review: dict, trace: dict, paired: dict) -> dict:
    """Keep the measured numbers separate from the UI's written interpretation."""
    pipeline = review["exploratory_pipeline"]
    if not (pipeline["pipeline_receipt"] == trace["pipeline_receipt"]
            == paired["baseline_receipt"]):
        raise ValueError("baseline receipts disagree")
    if not (review["source"]["video_sha256"] == trace["source_video_sha256"]
            == paired["source_video_sha256"]):
        raise ValueError("source video receipts disagree")
    if trace["model_sha256"] != paired["model_sha256"]:
        raise ValueError("model receipts disagree")
    marks = [event["frame"] for event in review["unique_events"]]
    if marks != trace["mark_frames"] or marks != [27, 37, 57, 92, 160]:
        raise ValueError("review marks disagree")
    expected_frames = sorted({f for m in marks for f in range(m - 4, m + 5)})
    if [row["frame"] for row in pipeline["diagnostic_frames"]] != expected_frames:
        raise ValueError("diagnostic frame coverage is incomplete")
    if pipeline["crossings"] != paired["baseline"]["public_crossings"]:
        raise ValueError("baseline crossings disagree")
    if (paired["accuracy_claim"] is not False
            or paired["recommend_default_change"] is not False
            or paired["post_hoc_development_only"] is not True
            or trace["physical_object_correspondence_verified"] is not False):
        raise ValueError("exploratory limits changed")

    cases = []
    for mark in marks:
        cases.append({
            "mark_frame": mark,
            "frames": [row for row in pipeline["diagnostic_frames"]
                       if abs(row["frame"] - mark) <= 4],
            "association_pairs": [row for row in trace["pairs"]
                                  if abs(row["frame"] - mark) <= 4],
            "baseline_crossings": paired["baseline"]["crossings_near_owner_marks"][str(mark)],
            "candidate_crossings": paired["candidate"]["crossings_near_owner_marks"][str(mark)],
        })
    return {
        "schema": "visiontrack.rain-diagnosis/v1",
        "source_record_sha256": SOURCE_DIGESTS,
        "source_video_sha256": trace["source_video_sha256"],
        "model_sha256": trace["model_sha256"],
        "baseline_receipt": trace["pipeline_receipt"],
        "frame_count": paired["frame_count"],
        "line": review["source"]["line"],
        "crossing_rule": pipeline["crossing_rule"],
        "diagnostic_window_rule": pipeline["diagnostic_window_rule"],
        "settings": {key: trace[key] for key in (
            "new_track_score_min", "confirmation_hits", "iou_min", "mahalanobis_d2_max")},
        "candidate_changed_setting_only": paired["candidate_changed_setting_only"],
        "baseline": paired["baseline"],
        "candidate": paired["candidate"],
        "limits": {
            "owner_attested_all_frames_reviewed": review["owner_attested_all_194_frames_reviewed"],
            "dense_identity_truth": review["dense_identity_truth"],
            "physical_object_correspondence_verified": False,
            "post_hoc_development_only": True,
            "accuracy_claim": False,
            "recommend_default_change": False,
        },
        "cases": cases,
    }


def export(source_dir: Path) -> dict:
    records = []
    for name, expected in SOURCE_DIGESTS.items():
        raw = (source_dir / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"pinned source record changed: {name}")
        records.append(json.loads(raw))
    return project(*records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(export(args.source_dir), indent=2, sort_keys=True)
                           + "\n", encoding="utf-8")
    print(f"Exported existing observations to {args.output}; no tracking was run.")


if __name__ == "__main__":
    main()
