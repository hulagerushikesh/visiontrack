"""Deterministic, read-only construction of synchronized failure playback."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import (
    FailureEvent,
    FailurePlayback,
    PlaybackFrame,
    PlaybackLane,
    SourceManifest,
    canonical_json,
)
from .report import build_report_model
from .runner import load_experiment_bundle
from .storage import read_evidence_manifest, read_failure_jsonl

_VARIANT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _verified_report(bundle: Path) -> dict[str, Any]:
    report_path = bundle / "report" / "report.json"
    if report_path.is_symlink() or not report_path.is_file():
        raise ValueError("a local sealed report/report.json is required for playback")
    model = build_report_model(bundle)
    expected = f"{canonical_json(model)}\n".encode()
    if report_path.read_bytes() != expected:
        raise ValueError("stored report.json does not match the verified bundle evidence")
    return model


def _variant_failures(
    bundle: Path,
    variant: str,
    *,
    frame_count: int,
) -> tuple[FailureEvent, ...]:
    return tuple(
        read_failure_jsonl(
            bundle / "runs" / variant / "failures.jsonl",
            frame_count=frame_count,
        )
    )


def _counterpart(
    events: tuple[FailureEvent, ...],
    anchor: FailureEvent,
) -> FailureEvent | None:
    matches = [
        event
        for event in events
        if event.frame_index == anchor.frame_index
        and event.event_type == anchor.event_type
        and event.ground_truth_ids == anchor.ground_truth_ids
        and event.evidence_frames == anchor.evidence_frames
    ]
    if len(matches) > 1:
        raise ValueError("multiple failure events match the synchronized counterpart")
    return matches[0] if matches else None


def _full_frame_artifacts(
    bundle: Path,
    variant: str,
    event: FailureEvent | None,
    source: SourceManifest,
) -> dict[int, Any]:
    if event is None:
        return {}
    manifest_path = bundle / "runs" / variant / "evidence" / event.event_id / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = read_evidence_manifest(manifest_path, source=source, failure=event)
    result: dict[int, Any] = {}
    for artifact in manifest.artifacts:
        if artifact.view != "full_frame":
            continue
        if artifact.frame_index in result:
            raise ValueError("multiple full-frame artifacts exist for one playback frame")
        result[artifact.frame_index] = artifact
    return result


def _lane(
    bundle: Path,
    *,
    variant: str,
    run_id: str,
    event: FailureEvent | None,
    source: SourceManifest,
    frame_range: dict[str, int],
) -> PlaybackLane:
    artifacts = _full_frame_artifacts(bundle, variant, event, source)
    start, end = frame_range["start"], frame_range["end"]
    frames: list[PlaybackFrame] = []
    for frame_index in range(start, end):
        offset_ms = (
            round((frame_index - start) * 1000 / source.fps)
            if source.fps is not None
            else None
        )
        artifact = artifacts.get(frame_index)
        if artifact is None:
            frames.append(
                PlaybackFrame(frame_index, offset_ms, "missing", None, None, None)
            )
            continue
        if event is None:
            raise ValueError("available playback artifact has no declared failure event")
        relative_path = (
            PurePosixPath("runs")
            / variant
            / "evidence"
            / event.event_id
            / artifact.relative_path
        ).as_posix()
        frames.append(
            PlaybackFrame(
                frame_index,
                offset_ms,
                "available",
                relative_path,
                artifact.image_sha256,
                artifact.privacy,
            )
        )
    return PlaybackLane(variant=variant, run_id=run_id, frames=tuple(frames))


def build_failure_playback(
    bundle: str | Path,
    *,
    event_id: str,
    variant: str,
) -> FailurePlayback:
    """Build paired local playback metadata without copying or decoding media."""
    bundle_path = Path(bundle)
    if bundle_path.is_symlink() or not bundle_path.is_dir():
        raise ValueError("playback bundle must be an existing local directory")
    model = _verified_report(bundle_path)
    experiment, source, _ = load_experiment_bundle(bundle_path)
    variant_names = {item["name"] for item in experiment.variants}
    if any(not _VARIANT_NAME.fullmatch(name) for name in variant_names):
        raise ValueError("experiment variant names must be safe local path components")
    if variant == experiment.baseline or variant not in variant_names:
        raise ValueError("variant must name a declared non-baseline experiment variant")

    report_matches = [event for event in model["failures"] if event["event_id"] == event_id]
    if len(report_matches) != 1:
        raise ValueError("event_id must match exactly one event in the sealed report")
    report_event = report_matches[0]
    if report_event["variant"] not in {experiment.baseline, variant}:
        raise ValueError("report event does not belong to the requested playback pair")

    failures = {
        name: _variant_failures(bundle_path, name, frame_count=source.frame_count)
        for name in (experiment.baseline, variant)
    }
    stored_matches = [
        event
        for event in failures[report_event["variant"]]
        if event.event_id == event_id
    ]
    if len(stored_matches) != 1:
        raise ValueError("report event does not match one stored failure event")
    anchor = stored_matches[0]
    counterpart_variant = (
        variant if report_event["variant"] == experiment.baseline else experiment.baseline
    )
    counterpart = _counterpart(failures[counterpart_variant], anchor)
    lane_events = {
        report_event["variant"]: anchor,
        counterpart_variant: counterpart,
    }
    run_ids = {item["name"]: item["run_id"] for item in model["variants"]}
    lanes = tuple(
        _lane(
            bundle_path,
            variant=name,
            run_id=run_ids[name],
            event=lane_events[name],
            source=source,
            frame_range=anchor.evidence_frames,
        )
        for name in (experiment.baseline, variant)
    )
    playback = FailurePlayback.create(
        experiment_id=experiment.experiment_id,
        source_id=source.source_id,
        comparison_id=model["comparison_id"],
        report_id=model["report_id"],
        anchor_event_id=anchor.event_id,
        event_frame_index=anchor.frame_index,
        frame_range=anchor.evidence_frames,
        baseline=experiment.baseline,
        variant=variant,
        lanes=lanes,
    )
    playback.verify_lineage(
        experiment=experiment,
        source=source,
        comparison_id=model["comparison_id"],
        report_id=model["report_id"],
        failure=anchor,
        run_ids=run_ids,
    )
    return playback
