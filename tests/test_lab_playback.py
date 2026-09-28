"""Synchronized failure playback stays bounded, local, and read-only."""

from __future__ import annotations

import pytest

from visiontrack.lab import (
    ExperimentManifest,
    FailureEvent,
    FailurePlayback,
    PlaybackFrame,
    PlaybackLane,
    SourceManifest,
)

NOW = "2026-09-28T10:00:00Z"
SHA_A = "a" * 64
SHA_B = "b" * 64
COMPARISON_ID = "c" * 64
REPORT_ID = "d" * 64
BASELINE_RUN_ID = "1" * 64
VARIANT_RUN_ID = "2" * 64


def context():
    source = SourceManifest.create(
        kind="synthetic",
        name="playback-fixture",
        detection_sha256=SHA_A,
        ground_truth_sha256=SHA_B,
        video_sha256=None,
        detector={"name": "fixture"},
        frame_count=12,
        width=640,
        height=360,
        fps=25.0,
        coordinate_space="pixel_xyxy",
        created_at=NOW,
    )
    experiment = ExperimentManifest.create(
        source_id=source.source_id,
        baseline="baseline",
        variants=(
            {"name": "baseline", "overrides": {}},
            {"name": "appearance", "overrides": {"w_app": 0.3}},
        ),
        metrics=("HOTA", "IDF1"),
        frame_range={"start": 0, "end": 12},
        visiontrack_version="0.2.0",
        git_revision="abc1234",
        environment={"python": "3.12"},
        created_at=NOW,
    )
    failure = FailureEvent.create(
        run_id=VARIANT_RUN_ID,
        frame_index=5,
        event_type="id_switch",
        track_ids=(3, 8),
        ground_truth_ids=(7,),
        context={"metric_id": "e" * 64},
        evidence_frames={"start": 4, "end": 7},
    )
    return source, experiment, failure


def frame(index: int, *, privacy: str | None = "synthetic") -> PlaybackFrame:
    if privacy is None:
        return PlaybackFrame(index, (index - 4) * 40, "missing", None, None, None)
    return PlaybackFrame(
        index,
        (index - 4) * 40,
        "available",
        f"runs/evidence/frame-{index:06d}.png",
        str(index) * 64,
        privacy,
    )


def playback() -> tuple[FailurePlayback, SourceManifest, ExperimentManifest, FailureEvent]:
    source, experiment, failure = context()
    baseline = PlaybackLane(
        "baseline",
        BASELINE_RUN_ID,
        (frame(4), frame(5, privacy="redacted"), frame(6, privacy=None)),
    )
    variant = PlaybackLane(
        "appearance",
        VARIANT_RUN_ID,
        (frame(4), frame(5), frame(6)),
    )
    result = FailurePlayback.create(
        experiment_id=experiment.experiment_id,
        source_id=source.source_id,
        comparison_id=COMPARISON_ID,
        report_id=REPORT_ID,
        anchor_event_id=failure.event_id,
        event_frame_index=failure.frame_index,
        frame_range=failure.evidence_frames,
        baseline="baseline",
        variant="appearance",
        lanes=(baseline, variant),
    )
    return result, source, experiment, failure


def test_playback_is_content_addressed_round_trippable_and_explicit() -> None:
    result, *_ = playback()

    assert FailurePlayback.from_json(result.to_json()) == result
    assert result.lanes[0].frames[1].privacy == "redacted"
    assert result.lanes[0].frames[2].status == "missing"
    assert result.lanes[0].frames[2].relative_path is None


def test_playback_revalidates_complete_report_and_run_lineage() -> None:
    result, source, experiment, failure = playback()
    result.verify_lineage(
        experiment=experiment,
        source=source,
        comparison_id=COMPARISON_ID,
        report_id=REPORT_ID,
        failure=failure,
        run_ids={"baseline": BASELINE_RUN_ID, "appearance": VARIANT_RUN_ID},
    )

    with pytest.raises(ValueError, match="report_id"):
        result.verify_lineage(
            experiment=experiment,
            source=source,
            comparison_id=COMPARISON_ID,
            report_id="f" * 64,
            failure=failure,
            run_ids={"baseline": BASELINE_RUN_ID, "appearance": VARIANT_RUN_ID},
        )
    with pytest.raises(ValueError, match="run_id"):
        result.verify_lineage(
            experiment=experiment,
            source=source,
            comparison_id=COMPARISON_ID,
            report_id=REPORT_ID,
            failure=failure,
            run_ids={"baseline": "9" * 64, "appearance": VARIANT_RUN_ID},
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"status": "remote"}, "status"),
        ({"relative_path": "https://example.com/frame.png"}, "relative_path"),
        ({"relative_path": "../frame.png"}, "relative_path"),
        ({"privacy": "unknown"}, "privacy"),
    ],
)
def test_available_frame_rejects_remote_or_ambiguous_media(change, message) -> None:
    values = frame(4).to_dict()
    values.update(change)
    with pytest.raises(ValueError, match=message):
        PlaybackFrame.from_dict(values)


def test_missing_frame_cannot_smuggle_media_or_privacy() -> None:
    values = frame(4, privacy=None).to_dict()
    values["relative_path"] = "frame.png"
    with pytest.raises(ValueError, match="must not reference media"):
        PlaybackFrame.from_dict(values)


def test_playback_requires_identical_complete_frame_and_timing_grids() -> None:
    result, *_ = playback()
    values = result.to_dict()
    values["playback_id"] = "0" * 64
    values["lanes"][1]["frames"][1]["offset_ms"] = 41
    with pytest.raises(ValueError, match="identical timing"):
        FailurePlayback.from_dict(values)

    values = result.to_dict()
    values["playback_id"] = "0" * 64
    values["lanes"][1]["frames"] = values["lanes"][1]["frames"][:-1]
    with pytest.raises(ValueError, match="complete frame_range"):
        FailurePlayback.from_dict(values)


def test_playback_timing_is_derived_from_source_fps() -> None:
    result, source, experiment, failure = playback()
    values = result.to_dict()
    values.pop("playback_id")
    values.pop("schema_version")
    for lane in values["lanes"]:
        lane["frames"][1]["offset_ms"] = 50
        lane["frames"][2]["offset_ms"] = 100
    changed = FailurePlayback.create(**values)
    with pytest.raises(ValueError, match="source fps"):
        changed.verify_lineage(
            experiment=experiment,
            source=source,
            comparison_id=COMPARISON_ID,
            report_id=REPORT_ID,
            failure=failure,
            run_ids={"baseline": BASELINE_RUN_ID, "appearance": VARIANT_RUN_ID},
        )


def test_playback_window_is_bounded_and_cannot_compare_baseline_to_itself() -> None:
    result, *_ = playback()
    values = result.to_dict()
    values["playback_id"] = "0" * 64
    values["frame_range"] = {"start": 0, "end": 302}
    values["event_frame_index"] = 5
    with pytest.raises(ValueError, match="at most 301"):
        FailurePlayback.from_dict(values)

    values = result.to_dict()
    values["playback_id"] = "0" * 64
    values["variant"] = "baseline"
    with pytest.raises(ValueError, match="differ"):
        FailurePlayback.from_dict(values)
