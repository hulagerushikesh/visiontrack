"""Evidence-aware summaries for completed Reliability Lab comparisons."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import TrackObservationRecord, sha256_json
from .runner import load_experiment_bundle, resolve_variant_config
from .storage import read_track_jsonl, write_comparison_summary

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


def _load_variant_result(
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
    diagnostics: dict[str, dict[str, Any]] = {}
    for variant in experiment.variants:
        metadata, tracks = _load_variant_result(
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
        diagnostics[name] = _diagnostics(tracks, frame_total)

    baseline_diagnostics = diagnostics[experiment.baseline]
    deltas = {
        name: _deltas(values, baseline_diagnostics)
        for name, values in diagnostics.items()
    }
    ground_truth_status = (
        "available_unmeasured" if source.ground_truth_sha256 is not None else "absent"
    )
    unavailable = [
        {
            "metric": metric,
            "status": "insufficient_evidence",
            "reason": "ground_truth_absent"
            if source.ground_truth_sha256 is None
            else "metric_integration_not_implemented",
        }
        for metric in _GROUND_TRUTH_METRICS
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
        "evidence": {
            "detection_sha256": source.detection_sha256,
            "ground_truth_status": ground_truth_status,
            "ground_truth_sha256": source.ground_truth_sha256,
        },
        "insufficient_evidence": unavailable,
        "decision": {
            "status": "not_selected",
            "accepted_variant": None,
            "reason": "diagnostic_counts_are_not_tracking_quality_metrics",
        },
    }
    content["comparison_id"] = sha256_json(content)
    write_comparison_summary(bundle_path, content)
    return content
