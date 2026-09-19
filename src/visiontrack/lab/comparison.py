"""Evidence-aware summaries for completed Reliability Lab comparisons."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import FailureEvent, TrackObservationRecord, sha256_json
from .runner import load_experiment_bundle, resolve_variant_config
from .storage import read_failure_jsonl, read_track_jsonl, write_comparison_summary

_RUN_FIELDS = {
    "schema_version",
    "experiment_id",
    "source_id",
    "variant",
    "config",
    "config_sha256",
    "detection_sha256",
    "frame_range",
    "track_sha256",
    "observation_count",
    "run_id",
}
_GROUND_TRUTH_METRICS = ("HOTA", "IDF1", "MOTA", "identity_switches", "fragmentation")
_METRIC_FIELDS = {
    "schema_version",
    "metric_id",
    "experiment_id",
    "source_id",
    "run_id",
    "variant",
    "detection_sha256",
    "ground_truth_sha256",
    "track_sha256",
    "frame_range",
    "iou_threshold",
    "preprocessing",
    "values",
}
_FAILURE_TYPES = ("id_switch", "fragmentation", "miss", "false_positive")


def _read_run_metadata(path: Path) -> dict[str, Any]:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read run metadata: {path}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"run metadata must be an object: {path}")
    unknown = set(metadata) - _RUN_FIELDS
    missing = _RUN_FIELDS - set(metadata)
    if unknown or missing:
        raise ValueError(
            f"run metadata fields do not match schema v1; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
    if metadata["schema_version"] != 1:
        raise ValueError(f"unsupported run schema_version: {metadata['schema_version']}")
    stored_run_id = metadata["run_id"]
    content = dict(metadata)
    content.pop("run_id")
    if stored_run_id != sha256_json(content):
        raise ValueError("run_id does not match run metadata content")
    return metadata


def load_variant_result(
    bundle: Path,
    variant: dict[str, Any],
    *,
    experiment_id: str,
    source_id: str,
    detection_sha256: str,
    frame_range: dict[str, int],
    frame_count: int,
) -> tuple[dict[str, Any], tuple[TrackObservationRecord, ...]]:
    name = variant["name"]
    run_path = bundle / "runs" / name
    metadata = _read_run_metadata(run_path / "run.json")
    expected_config = asdict(resolve_variant_config(variant))
    expected = {
        "experiment_id": experiment_id,
        "source_id": source_id,
        "variant": name,
        "config": expected_config,
        "config_sha256": sha256_json(expected_config),
        "detection_sha256": detection_sha256,
        "frame_range": frame_range,
    }
    for field, value in expected.items():
        if metadata[field] != value:
            raise ValueError(f"run metadata {field} does not match experiment evidence")

    track_path = run_path / "tracks.jsonl"
    try:
        payload = track_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read track payload: {track_path}") from exc
    if hashlib.sha256(payload).hexdigest() != metadata["track_sha256"]:
        raise ValueError(f"track payload SHA-256 does not match run metadata for {name!r}")
    tracks = tuple(read_track_jsonl(track_path, frame_count=frame_count))
    if len(tracks) != metadata["observation_count"]:
        raise ValueError(f"track observation count does not match run metadata for {name!r}")
    start, end = frame_range["start"], frame_range["end"]
    if any(not start <= track.frame_index < end for track in tracks):
        raise ValueError(f"track observation falls outside experiment frame_range for {name!r}")
    return metadata, tracks


def load_variant_metrics(
    path: Path,
    *,
    experiment_id: str,
    source_id: str,
    variant: str,
    run_metadata: dict[str, Any],
    ground_truth_sha256: str,
    frame_range: dict[str, int],
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read metric artifact: {path}") from exc
    if not isinstance(artifact, dict) or set(artifact) != _METRIC_FIELDS:
        raise ValueError("metric artifact fields do not match schema v1")
    if artifact["schema_version"] != 1:
        raise ValueError(f"unsupported metric schema_version: {artifact['schema_version']}")
    metric_id = artifact["metric_id"]
    content = dict(artifact)
    content.pop("metric_id")
    if metric_id != sha256_json(content):
        raise ValueError("metric_id does not match metric artifact content")
    expected = {
        "experiment_id": experiment_id,
        "source_id": source_id,
        "run_id": run_metadata["run_id"],
        "variant": variant,
        "detection_sha256": run_metadata["detection_sha256"],
        "ground_truth_sha256": ground_truth_sha256,
        "track_sha256": run_metadata["track_sha256"],
        "frame_range": frame_range,
    }
    for field, value in expected.items():
        if artifact[field] != value:
            raise ValueError(f"metric artifact {field} does not match verified evidence")
    values = artifact["values"]
    if not isinstance(values, dict) or not values:
        raise ValueError("metric artifact values must be a non-empty object")
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        for value in values.values()
    ):
        raise ValueError("metric artifact values must contain only finite numbers")
    return artifact


def _load_variant_failures(
    path: Path,
    *,
    run_metadata: dict[str, Any],
    metric_artifact: dict[str, Any],
    ground_truth_sha256: str,
    frame_range: dict[str, int],
    frame_count: int,
) -> tuple[tuple[FailureEvent, ...], str] | None:
    if not path.exists():
        return None
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read failure artifact: {path}") from exc
    events = tuple(read_failure_jsonl(path, frame_count=frame_count))
    start, end = frame_range["start"], frame_range["end"]
    expected_context = {
        "metric_id": metric_artifact["metric_id"],
        "detection_sha256": run_metadata["detection_sha256"],
        "ground_truth_sha256": ground_truth_sha256,
        "track_sha256": run_metadata["track_sha256"],
        "iou_threshold": metric_artifact["iou_threshold"],
    }
    for event in events:
        if event.run_id != run_metadata["run_id"]:
            raise ValueError("failure event run_id does not match verified run evidence")
        if not start <= event.frame_index < end:
            raise ValueError("failure event falls outside experiment frame_range")
        for field, value in expected_context.items():
            if event.context.get(field) != value:
                raise ValueError(
                    f"failure event context {field} does not match verified evidence"
                )
    return events, hashlib.sha256(payload).hexdigest()


def _diagnostics(tracks: tuple[TrackObservationRecord, ...], frame_total: int) -> dict[str, Any]:
    track_ids = {track.track_id for track in tracks}
    active_frames = {track.frame_index for track in tracks}
    return {
        "observation_count": len(tracks),
        "unique_track_count": len(track_ids),
        "active_frame_count": len(active_frames),
        "active_frame_fraction": len(active_frames) / frame_total,
        "first_active_frame": min(active_frames) if active_frames else None,
        "last_active_frame": max(active_frames) if active_frames else None,
    }


def _deltas(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int | float]:
    fields = (
        "observation_count",
        "unique_track_count",
        "active_frame_count",
        "active_frame_fraction",
    )
    deltas = {field: current[field] - baseline[field] for field in fields}
    if not all(math.isfinite(float(value)) for value in deltas.values()):
        raise ValueError("comparison diagnostics produced a non-finite delta")
    return deltas


def create_comparison_summary(bundle: str | Path) -> dict[str, Any]:
    """Verify completed runs and persist a diagnostic-only comparison."""
    bundle_path = Path(bundle)
    experiment, source, _ = load_experiment_bundle(bundle_path)
    frame_total = experiment.frame_range["end"] - experiment.frame_range["start"]

    run_ids: dict[str, str] = {}
    run_metadata: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for variant in experiment.variants:
        metadata, tracks = load_variant_result(
            bundle_path,
            variant,
            experiment_id=experiment.experiment_id,
            source_id=source.source_id,
            detection_sha256=source.detection_sha256,
            frame_range=experiment.frame_range,
            frame_count=source.frame_count,
        )
        name = variant["name"]
        run_ids[name] = metadata["run_id"]
        run_metadata[name] = metadata
        diagnostics[name] = _diagnostics(tracks, frame_total)

    baseline_diagnostics = diagnostics[experiment.baseline]
    deltas = {
        name: _deltas(values, baseline_diagnostics)
        for name, values in diagnostics.items()
    }
    metric_artifacts: dict[str, dict[str, Any]] = {}
    if source.ground_truth_sha256 is not None:
        loaded = {
            variant["name"]: load_variant_metrics(
                bundle_path / "runs" / variant["name"] / "metrics.json",
                experiment_id=experiment.experiment_id,
                source_id=source.source_id,
                variant=variant["name"],
                run_metadata=run_metadata[variant["name"]],
                ground_truth_sha256=source.ground_truth_sha256,
                frame_range=experiment.frame_range,
            )
            for variant in experiment.variants
        }
        present = [artifact is not None for artifact in loaded.values()]
        if any(present) and not all(present):
            raise ValueError("metric artifacts must exist for every declared variant")
        metric_artifacts = {
            name: artifact for name, artifact in loaded.items() if artifact is not None
        }

    metric_values = {
        name: artifact["values"] for name, artifact in metric_artifacts.items()
    }
    metric_deltas: dict[str, dict[str, int | float]] = {}
    if metric_values:
        baseline_metrics = metric_values[experiment.baseline]
        baseline_keys = set(baseline_metrics)
        if any(set(values) != baseline_keys for values in metric_values.values()):
            raise ValueError("metric artifacts do not contain the same metric keys")
        metric_deltas = {
            name: {
                metric: values[metric] - baseline_metrics[metric]
                for metric in baseline_metrics
            }
            for name, values in metric_values.items()
        }
    ground_truth_status = "absent"
    if source.ground_truth_sha256 is not None:
        ground_truth_status = "available_measured" if metric_values else "available_unmeasured"

    loaded_failures: dict[str, tuple[tuple[FailureEvent, ...], str] | None] = {}
    for variant in experiment.variants:
        name = variant["name"]
        failure_path = bundle_path / "runs" / name / "failures.jsonl"
        if failure_path.exists() and name not in metric_artifacts:
            raise ValueError("failure artifacts require verified metrics for every variant")
        loaded_failures[name] = (
            _load_variant_failures(
                failure_path,
                run_metadata=run_metadata[name],
                metric_artifact=metric_artifacts[name],
                ground_truth_sha256=source.ground_truth_sha256,
                frame_range=experiment.frame_range,
                frame_count=source.frame_count,
            )
            if name in metric_artifacts
            else None
        )
    failure_presence = [value is not None for value in loaded_failures.values()]
    if any(failure_presence) and not all(failure_presence):
        raise ValueError("failure artifacts must exist for every declared variant")
    failure_counts: dict[str, dict[str, int]] = {}
    failure_sets: dict[str, dict[str, Any]] = {}
    for name, loaded in loaded_failures.items():
        if loaded is None:
            continue
        events, failure_sha256 = loaded
        failure_counts[name] = {
            event_type: sum(event.event_type == event_type for event in events)
            for event_type in _FAILURE_TYPES
        }
        failure_sets[name] = {
            "failure_sha256": failure_sha256,
            "event_count": len(events),
            "run_id": run_metadata[name]["run_id"],
            "metric_id": metric_artifacts[name]["metric_id"],
            "track_sha256": run_metadata[name]["track_sha256"],
            "ground_truth_sha256": source.ground_truth_sha256,
        }
    computed_claims = {
        "HOTA": "HOTA",
        "IDF1": "IDF1",
        "MOTA": "MOTA",
        "identity_switches": "IDSW",
        "fragmentation": "Frag",
    }
    computed_keys = set(next(iter(metric_values.values()))) if metric_values else set()
    unavailable = [
        {
            "metric": metric,
            "status": "insufficient_evidence",
            "reason": "ground_truth_absent"
            if source.ground_truth_sha256 is None
            else "metric_integration_not_implemented",
        }
        for metric in _GROUND_TRUTH_METRICS
        if computed_claims[metric] not in computed_keys
    ]
    content: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment.experiment_id,
        "source_id": source.source_id,
        "baseline": experiment.baseline,
        "requested_metrics": list(experiment.metrics),
        "run_ids": run_ids,
        "diagnostics": diagnostics,
        "deltas_vs_baseline": deltas,
        "metrics": metric_values,
        "metric_deltas_vs_baseline": metric_deltas,
        "failure_counts": failure_counts,
        "failure_sets": failure_sets,
        "evidence": {
            "detection_sha256": source.detection_sha256,
            "ground_truth_status": ground_truth_status,
            "ground_truth_sha256": source.ground_truth_sha256,
        },
        "insufficient_evidence": unavailable,
        "decision": {
            "status": "not_selected",
            "accepted_variant": None,
            "reason": "requires_human_acceptance_decision"
            if metric_values
            else "diagnostic_counts_are_not_tracking_quality_metrics",
        },
    }
    content["comparison_id"] = sha256_json(content)
    write_comparison_summary(bundle_path, content)
    return content
