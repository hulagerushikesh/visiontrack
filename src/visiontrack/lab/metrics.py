"""Verified metric calculation for completed Reliability Lab runs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..eval.mot17 import evaluate_frames, preprocess_frame
from .comparison import load_variant_result
from .contracts import GroundTruthRecord, TrackObservationRecord, sha256_json
from .runner import load_experiment_bundle
from .storage import read_ground_truth_jsonl, write_variant_metrics


def _boxes(records) -> np.ndarray:
    if not records:
        return np.empty((0, 4), dtype=np.float64)
    return np.asarray([record.xyxy for record in records], dtype=np.float64)


def evaluation_frames(
    ground_truth: tuple[GroundTruthRecord, ...],
    tracks: tuple[TrackObservationRecord, ...],
    *,
    start: int,
    end: int,
):
    ground_truth_by_frame: dict[int, list[GroundTruthRecord]] = {}
    tracks_by_frame: dict[int, list[TrackObservationRecord]] = {}
    for record in ground_truth:
        if start <= record.frame_index < end:
            ground_truth_by_frame.setdefault(record.frame_index, []).append(record)
    for record in tracks:
        if start <= record.frame_index < end:
            tracks_by_frame.setdefault(record.frame_index, []).append(record)

    frames = []
    for frame_index in range(start, end):
        gt = ground_truth_by_frame.get(frame_index, [])
        tr = tracks_by_frame.get(frame_index, [])
        frames.append(
            preprocess_frame(
                _boxes(gt),
                np.asarray([record.object_id for record in gt], dtype=np.int64),
                np.asarray([record.class_id for record in gt], dtype=np.int64),
                np.asarray([0.0 if record.ignored else 1.0 for record in gt]),
                _boxes(tr),
                np.asarray([record.track_id for record in tr], dtype=np.int64),
            )
        )
    return frames


def calculate_bundle_metrics(bundle: str | Path) -> dict[str, dict[str, Any]]:
    """Calculate and persist metrics from verified GT and completed runs."""
    bundle_path = Path(bundle)
    if (bundle_path / "comparison.json").exists():
        raise ValueError(
            "comparison.json already seals this bundle; calculate metrics before the summary"
        )
    experiment, source, _ = load_experiment_bundle(bundle_path)
    if source.ground_truth_sha256 is None:
        raise ValueError("verified ground truth is required to calculate metrics")
    ground_truth = tuple(
        read_ground_truth_jsonl(
            bundle_path / "inputs" / "ground_truth.jsonl",
            frame_count=source.frame_count,
        )
    )
    start, end = experiment.frame_range["start"], experiment.frame_range["end"]
    artifacts: dict[str, dict[str, Any]] = {}
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
        values = evaluate_frames(
            evaluation_frames(ground_truth, tracks, start=start, end=end)
        )
        content: dict[str, Any] = {
            "schema_version": 1,
            "experiment_id": experiment.experiment_id,
            "source_id": source.source_id,
            "run_id": run_metadata["run_id"],
            "variant": name,
            "detection_sha256": source.detection_sha256,
            "ground_truth_sha256": source.ground_truth_sha256,
            "track_sha256": run_metadata["track_sha256"],
            "frame_range": experiment.frame_range,
            "iou_threshold": 0.5,
            "preprocessing": "visiontrack.eval.mot17.preprocess_frame",
            "values": values,
        }
        content["metric_id"] = sha256_json(content)
        write_variant_metrics(bundle_path, name, content)
        artifacts[name] = content
    return artifacts
