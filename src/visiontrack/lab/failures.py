"""Deterministic failure extraction for verified Reliability Lab runs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..eval.definitions import LEGACY_EVALUATOR, accumulator_for
from ..eval.mot import MotFailure
from .comparison import load_variant_metrics, load_variant_result
from .contracts import FailureEvent
from .evaluation_policy import preprocessing_for
from .metrics import evaluation_frames
from .runner import load_experiment_bundle
from .storage import read_ground_truth_jsonl, serialize_failure_jsonl, write_failure_jsonl


def _track_ids(failure: MotFailure) -> tuple[int, ...]:
    candidates = (failure.previous_hyp_id, failure.hyp_id)
    return tuple(dict.fromkeys(value for value in candidates if value is not None))


def _context(
    failure: MotFailure,
    *,
    metric_id: str,
    detection_sha256: str,
    ground_truth_sha256: str,
    track_sha256: str,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "detection_sha256": detection_sha256,
        "ground_truth_sha256": ground_truth_sha256,
        "track_sha256": track_sha256,
        "iou_threshold": 0.5,
        "previous_track_id": failure.previous_hyp_id,
        "current_track_id": failure.hyp_id,
        "ground_truth_box": list(failure.gt_box) if failure.gt_box is not None else None,
        "track_box": list(failure.hyp_box) if failure.hyp_box is not None else None,
    }


def calculate_failure_events(bundle: str | Path) -> dict[str, tuple[FailureEvent, ...]]:
    """Extract immutable events from the exact correspondence used by metrics."""
    bundle_path = Path(bundle)
    if (bundle_path / "comparison.json").exists():
        raise ValueError(
            "comparison.json already seals this bundle; extract failures before the summary"
        )
    experiment, source, _ = load_experiment_bundle(bundle_path)
    ground_truth_sha256 = source.ground_truth_sha256
    if ground_truth_sha256 is None:
        raise ValueError("verified ground truth is required to extract failures")
    ground_truth = tuple(
        read_ground_truth_jsonl(
            bundle_path / "inputs" / "ground_truth.jsonl",
            frame_count=source.frame_count,
        )
    )
    start, end = experiment.frame_range["start"], experiment.frame_range["end"]
    results: dict[str, tuple[FailureEvent, ...]] = {}
    definitions: set[tuple[str, str]] = set()

    for variant in experiment.variants:
        name = variant["name"]
        run_metadata, tracks = load_variant_result(
            bundle_path,
            variant,
            experiment_id=experiment.experiment_id,
            source_id=source.source_id,
            detection_sha256=source.detection_sha256,
            frame_range=experiment.frame_range,
            frame_count=source.frame_count,
        )
        metric_artifact = load_variant_metrics(
            bundle_path / "runs" / name / "metrics.json",
            experiment_id=experiment.experiment_id,
            source_id=source.source_id,
            variant=name,
            run_metadata=run_metadata,
            ground_truth_sha256=ground_truth_sha256,
            frame_range=experiment.frame_range,
        )
        if metric_artifact is None:
            raise ValueError(f"metric artifact is required before failure extraction for {name!r}")

        evaluator = metric_artifact.get("evaluator", LEGACY_EVALUATOR)
        accumulator = accumulator_for(evaluator)
        failures: list[FailureEvent] = []
        preprocessing = preprocessing_for(metric_artifact)
        definitions.add((evaluator, preprocessing))
        if len(definitions) > 1:
            raise ValueError("cannot extract failures using mixed metric evaluation policies")
        frames = evaluation_frames(
            ground_truth, tracks, start=start, end=end, preprocessing=preprocessing,
        )
        for gt_ids, gt_boxes, track_ids, track_boxes in frames:
            for failure in accumulator.update(gt_ids, gt_boxes, track_ids, track_boxes):
                frame_index = start + failure.frame_index
                failures.append(
                    FailureEvent.create(
                        run_id=run_metadata["run_id"],
                        frame_index=frame_index,
                        event_type=failure.event_type,
                        track_ids=_track_ids(failure),
                        ground_truth_ids=()
                        if failure.gt_id is None
                        else (failure.gt_id,),
                        context={**_context(
                            failure,
                            metric_id=metric_artifact["metric_id"],
                            detection_sha256=source.detection_sha256,
                            ground_truth_sha256=ground_truth_sha256,
                            track_sha256=run_metadata["track_sha256"],
                        ), **({"evaluator": evaluator}
                              if metric_artifact["schema_version"] >= 2 else {}),
                            **({"preprocessing": preprocessing}
                               if metric_artifact["schema_version"] == 3 else {})},
                        evidence_frames={
                            "start": max(start, frame_index - 2),
                            "end": min(end, frame_index + 3),
                        },
                    )
                )

        results[name] = tuple(failures)
    # Validate the complete batch before writing; preserve historical events and
    # avoid publishing earlier variants if a later artifact is incompatible.
    for name, failures in results.items():
        path = bundle_path / "runs" / name / "failures.jsonl"
        payload = serialize_failure_jsonl(failures, frame_count=source.frame_count)
        if path.is_symlink() or (path.exists() and path.read_bytes() != payload):
            raise FileExistsError(f"refusing to overwrite conflicting file: {path}")
    for name, failures in results.items():
        write_failure_jsonl(
            bundle_path / "runs" / name / "failures.jsonl",
            failures,
            frame_count=source.frame_count,
        )
    return results
