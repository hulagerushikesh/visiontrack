"""Strict, dataset-free Python/C++ tracker synchronization contract."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import numpy as np

from .detection.base import Detection
from .tracking.config import TrackerConfig
from .tracking.tracker import ByteTracker, TrackObservation

CONTRACT_ID = "visiontrack.tracker-parity/v1"
STABLE_CONFIG_FIELDS = frozenset(
    {
        "high_score_thresh",
        "low_score_thresh",
        "match_iou_thresh",
        "recovery_iou_thresh",
        "new_track_thresh",
        "n_init",
        "max_age",
        "use_mahalanobis_gating",
        "class_aware",
        "w_iou",
        "w_app",
        "w_unc",
        "use_giou",
        "appearance_ema_alpha",
        "kf_noise_scale",
    }
)
_ROOT_FIELDS = {"contract_id", "config", "frames", "expected_observations"}
_FRAME_FIELDS = {"frame_index", "detections"}
_DETECTION_FIELDS = {"xyxy", "score", "class_id", "feature"}
_OBSERVATION_FIELDS = {"frame_index", "track_id", "xyxy", "score", "class_id"}
_BOOL_CONFIG_FIELDS = {"use_mahalanobis_gating", "class_aware", "use_giou"}
_INT_CONFIG_FIELDS = {"n_init", "max_age"}
_UNIT_CONFIG_FIELDS = {
    "high_score_thresh",
    "low_score_thresh",
    "match_iou_thresh",
    "recovery_iou_thresh",
    "new_track_thresh",
    "appearance_ema_alpha",
}


def canonical_json(value: Any) -> str:
    """Return the one byte representation used by both repositories."""
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def fixture_sha256(value: bytes | str) -> str:
    """Hash fixture bytes, or UTF-8 text, without normalizing them first."""
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _object(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing:
        raise ValueError(f"missing {name} fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown {name} fields: {sorted(unknown)}")
    return value


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _number(value: Any, name: str, *, score: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if score and not 0 <= result <= 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return result


def _box(value: Any, name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{name} must contain four numbers")
    box = tuple(_number(item, name) for item in value)
    if box[2] < box[0] or box[3] < box[1]:
        raise ValueError(f"{name} must satisfy x2 >= x1 and y2 >= y1")
    return box  # type: ignore[return-value]


def validate_contract(value: Any) -> dict[str, Any]:
    """Validate v1 structure and values without running the tracker."""
    root = _object(value, _ROOT_FIELDS, "contract")
    if root["contract_id"] != CONTRACT_ID:
        raise ValueError(f"contract_id must be {CONTRACT_ID}")

    config = root["config"]
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    unknown_config = set(config) - STABLE_CONFIG_FIELDS
    if unknown_config:
        raise ValueError(f"unsupported config fields: {sorted(unknown_config)}")
    for field, raw_value in config.items():
        if field in _BOOL_CONFIG_FIELDS:
            if not isinstance(raw_value, bool):
                raise ValueError(f"config.{field} must be a boolean")
        elif field in _INT_CONFIG_FIELDS:
            _integer(raw_value, f"config.{field}", minimum=1)
        else:
            value = _number(raw_value, f"config.{field}")
            if field in _UNIT_CONFIG_FIELDS and not 0 <= value <= 1:
                raise ValueError(f"config.{field} must be in [0, 1]")
            if field == "kf_noise_scale" and value <= 0:
                raise ValueError("config.kf_noise_scale must be positive")
    try:
        TrackerConfig(**config)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid tracker config: {exc}") from exc

    frames = root["frames"]
    if not isinstance(frames, list) or not frames:
        raise ValueError("frames must be a non-empty array")
    feature_dim: int | None = None
    for expected_index, raw_frame in enumerate(frames):
        frame = _object(raw_frame, _FRAME_FIELDS, "frame")
        if _integer(frame["frame_index"], "frame_index", minimum=0) != expected_index:
            raise ValueError("frame_index must be contiguous and zero-based")
        detections = frame["detections"]
        if not isinstance(detections, list):
            raise ValueError("detections must be an array")
        presence: set[bool] = set()
        for raw_detection in detections:
            detection = _object(raw_detection, _DETECTION_FIELDS, "detection")
            _box(detection["xyxy"], "detection.xyxy")
            _number(detection["score"], "detection.score", score=True)
            _integer(detection["class_id"], "detection.class_id")
            feature = detection["feature"]
            presence.add(feature is not None)
            if feature is None:
                continue
            if not isinstance(feature, list) or not feature:
                raise ValueError("detection.feature must be null or a non-empty array")
            for component in feature:
                _number(component, "detection.feature")
            if feature_dim is None:
                feature_dim = len(feature)
            elif len(feature) != feature_dim:
                raise ValueError("all detection features must have one consistent width")
        if len(presence) > 1:
            raise ValueError("features must be present for every detection in a frame or none")

    expected = root["expected_observations"]
    if not isinstance(expected, list):
        raise ValueError("expected_observations must be an array")
    last_key = (-1, -1)
    for raw_observation in expected:
        observation = _object(raw_observation, _OBSERVATION_FIELDS, "observation")
        frame_index = _integer(observation["frame_index"], "frame_index", minimum=0)
        if frame_index >= len(frames):
            raise ValueError("observation frame_index is outside frames")
        track_id = _integer(observation["track_id"], "track_id", minimum=1)
        _box(observation["xyxy"], "observation.xyxy")
        _number(observation["score"], "observation.score", score=True)
        _integer(observation["class_id"], "observation.class_id")
        if (frame_index, track_id) <= last_key:
            raise ValueError("observations must be ordered by frame_index and stable track order")
        last_key = (frame_index, track_id)
    return root


def load_contract(path: str | Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    """Load canonical fixture bytes, optionally enforcing their recorded digest."""
    raw = Path(path).read_bytes()
    actual_digest = fixture_sha256(raw)
    if expected_sha256 is not None and actual_digest != expected_sha256:
        raise ValueError(
            f"fixture SHA-256 mismatch: expected {expected_sha256}, got {actual_digest}"
        )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("fixture must be valid UTF-8 JSON") from exc
    validate_contract(value)
    canonical = canonical_json(value).encode("utf-8")
    if raw != canonical:
        raise ValueError("fixture bytes are not canonical JSON with one final newline")
    return value


def _detections(raw_frame: dict[str, Any]) -> list[Detection]:
    return [
        Detection(
            xyxy=np.asarray(item["xyxy"], dtype=np.float64),
            score=float(item["score"]),
            class_id=int(item["class_id"]),
            feature=(
                None
                if item["feature"] is None
                else np.asarray(item["feature"], dtype=np.float64)
            ),
        )
        for item in raw_frame["detections"]
    ]


def _record(observation: TrackObservation) -> dict[str, Any]:
    return {
        "frame_index": observation.frame,
        "track_id": observation.track_id,
        "xyxy": [float(value) for value in observation.xyxy],
        "score": float(observation.score),
        "class_id": observation.class_id,
    }


def execute_contract(value: dict[str, Any], *, verify_reset: bool = True) -> list[dict[str, Any]]:
    """Run the public NumPy tracker over a validated fixture."""
    validate_contract(value)
    tracker = ByteTracker(TrackerConfig(**value["config"]))

    def run() -> list[dict[str, Any]]:
        return [
            _record(observation)
            for frame in value["frames"]
            for observation in tracker.update(_detections(frame))
        ]

    actual = run()
    if verify_reset:
        tracker.reset()
        if run() != actual:
            raise AssertionError("tracker reset did not reproduce the same observation stream")
    return actual


def _float_bits(value: Any) -> bytes:
    return struct.pack(">d", float(value))


def assert_contract(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute v1 and require exact scalar and IEEE-754 output parity."""
    actual = execute_contract(value)
    expected = value["expected_observations"]
    if len(actual) != len(expected):
        raise AssertionError(
            f"observation count differs: expected {len(expected)}, got {len(actual)}"
        )
    for index, (want, got) in enumerate(zip(expected, actual, strict=True)):
        for field in ("frame_index", "track_id", "class_id"):
            if got[field] != want[field]:
                raise AssertionError(
                    f"observation {index} {field} differs: expected {want[field]}, got {got[field]}"
                )
        if _float_bits(got["score"]) != _float_bits(want["score"]):
            raise AssertionError(f"observation {index} score differs at the bit level")
        for component, (want_value, got_value) in enumerate(
            zip(want["xyxy"], got["xyxy"], strict=True)
        ):
            if _float_bits(got_value) != _float_bits(want_value):
                raise AssertionError(
                    f"observation {index} xyxy[{component}] differs at the bit level"
                )
    return actual
