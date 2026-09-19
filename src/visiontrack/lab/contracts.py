"""Portable v1 records for the local-first Reliability Lab.

The tracker and experiment harness remain the computation layer.  These records
are the small, explicit persistence boundary around them: canonical JSON,
content hashes, validation, and adapters from the existing public tracker types.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import Any, ClassVar, TypeVar

from ..detection.base import Detection
from ..tracking.tracker import TrackObservation

SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_T = TypeVar("_T", bound="ContractRecord")


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically and reject non-finite numbers."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_json(value: Any) -> str:
    """Return the SHA-256 of a value's canonical JSON representation."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_utc(value: str, field_name: str = "created_at") -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field_name} must include the UTC timezone")


def _validate_hash(value: str | None, field_name: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")


def _box(value: Any) -> tuple[float, float, float, float]:
    try:
        box = tuple(float(v) for v in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("xyxy must contain four finite numbers") from exc
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError("xyxy must contain four finite numbers")
    if box[2] < box[0] or box[3] < box[1]:
        raise ValueError("xyxy must satisfy x2 >= x1 and y2 >= y1")
    return box  # type: ignore[return-value]


class ContractRecord:
    """Shared canonical JSON and strict schema loading."""

    schema_version: int
    _record_fields: ClassVar[set[str] | None] = None

    def to_dict(self) -> dict[str, Any]:
        # JSON round-trip normalizes tuples to arrays and rejects NaN/Inf.
        return json.loads(canonical_json(asdict(self)))

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def content_sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls: type[_T], value: dict[str, Any]) -> _T:
        if not isinstance(value, dict):
            raise ValueError(f"{cls.__name__} must be a JSON object")
        allowed = {field.name for field in fields(cls)}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown {cls.__name__} fields: {sorted(unknown)}")
        return cls(**value)

    @classmethod
    def from_json(cls: type[_T], value: str) -> _T:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid {cls.__name__} JSON") from exc
        return cls.from_dict(parsed)


@dataclass(frozen=True, slots=True)
class SourceManifest(ContractRecord):
    """Immutable identity and provenance for one detection stream."""

    source_id: str
    kind: str
    name: str
    detection_sha256: str
    ground_truth_sha256: str | None
    video_sha256: str | None
    detector: dict[str, Any]
    frame_count: int
    width: int
    height: int
    fps: float | None
    coordinate_space: str
    created_at: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.kind not in {"synthetic", "visiontrack_cache", "mot"}:
            raise ValueError("kind must be synthetic, visiontrack_cache, or mot")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        _validate_hash(self.detection_sha256, "detection_sha256")
        _validate_hash(self.ground_truth_sha256, "ground_truth_sha256", optional=True)
        _validate_hash(self.video_sha256, "video_sha256", optional=True)
        if not isinstance(self.detector, dict):
            raise ValueError("detector must be an object")
        if self.frame_count <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("frame_count, width, and height must be positive")
        if self.fps is not None and (not math.isfinite(self.fps) or self.fps <= 0):
            raise ValueError("fps must be positive and finite when present")
        if self.coordinate_space != "pixel_xyxy":
            raise ValueError("coordinate_space must be pixel_xyxy in schema v1")
        _validate_utc(self.created_at)
        if self.source_id != self.derive_source_id():
            raise ValueError("source_id does not match the manifest content")

    def _identity_payload(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("source_id")
        data.pop("created_at")
        return data

    def derive_source_id(self) -> str:
        return sha256_json(self._identity_payload())

    @classmethod
    def create(cls, *, created_at: str | None = None, **values: Any) -> SourceManifest:
        timestamp = created_at or _utc_now()
        provisional = object.__new__(cls)
        for field in fields(cls):
            if field.name == "source_id":
                object.__setattr__(provisional, field.name, "")
            elif field.name == "created_at":
                object.__setattr__(provisional, field.name, timestamp)
            elif field.name == "schema_version":
                object.__setattr__(provisional, field.name, SCHEMA_VERSION)
            else:
                object.__setattr__(provisional, field.name, values[field.name])
        source_id = provisional.derive_source_id()
        return cls(source_id=source_id, created_at=timestamp, **values)


@dataclass(frozen=True, slots=True)
class DetectionRecord(ContractRecord):
    """One portable detector observation."""

    frame_index: int
    source_frame: int | None
    detection_index: int
    xyxy: tuple[float, float, float, float]
    score: float
    class_id: int
    feature_ref: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.frame_index < 0 or self.detection_index < 0:
            raise ValueError("frame_index and detection_index must be non-negative")
        if self.source_frame is not None and self.source_frame < 0:
            raise ValueError("source_frame must be non-negative when present")
        object.__setattr__(self, "xyxy", _box(self.xyxy))
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("score must be finite and in [0, 1]")
        if not isinstance(self.class_id, int):
            raise ValueError("class_id must be an integer")
        if self.feature_ref is not None and not self.feature_ref.strip():
            raise ValueError("feature_ref must not be blank")

    @classmethod
    def from_detection(
        cls,
        detection: Detection,
        *,
        frame_index: int,
        detection_index: int,
        source_frame: int | None = None,
        feature_ref: str | None = None,
    ) -> DetectionRecord:
        return cls(
            frame_index=frame_index,
            source_frame=source_frame,
            detection_index=detection_index,
            xyxy=tuple(float(v) for v in detection.xyxy),
            score=float(detection.score),
            class_id=int(detection.class_id),
            feature_ref=feature_ref,
        )


@dataclass(frozen=True, slots=True)
class ExperimentManifest(ContractRecord):
    """Immutable specification for one paired Reliability Lab comparison."""

    experiment_id: str
    source_id: str
    baseline: str
    variants: tuple[dict[str, Any], ...]
    metrics: tuple[str, ...]
    frame_range: dict[str, int]
    visiontrack_version: str
    git_revision: str | None
    environment: dict[str, Any]
    config_sha256: str
    created_at: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        _validate_hash(self.source_id, "source_id")
        object.__setattr__(self, "variants", tuple(dict(v) for v in self.variants))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        names = [v.get("name") for v in self.variants]
        if not names or any(not isinstance(name, str) or not name for name in names):
            raise ValueError("each variant must have a non-empty name")
        if len(names) != len(set(names)):
            raise ValueError("variant names must be unique")
        if self.baseline not in names:
            raise ValueError("baseline must name one variant")
        if not self.metrics or len(self.metrics) != len(set(self.metrics)):
            raise ValueError("metrics must be non-empty and unique")
        if set(self.frame_range) != {"start", "end"}:
            raise ValueError("frame_range must contain only start and end")
        start, end = self.frame_range["start"], self.frame_range["end"]
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError("frame_range must satisfy 0 <= start < end")
        if not self.visiontrack_version.strip():
            raise ValueError("visiontrack_version must not be empty")
        if not isinstance(self.environment, dict) or not self.environment:
            raise ValueError("environment must be a non-empty object")
        _validate_hash(self.config_sha256, "config_sha256")
        _validate_utc(self.created_at)
        if self.config_sha256 != self.derive_config_sha256():
            raise ValueError("config_sha256 does not match the configuration")
        if self.experiment_id != self.derive_experiment_id():
            raise ValueError("experiment_id does not match the manifest content")

    def _config_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "baseline": self.baseline,
            "variants": list(self.variants),
            "metrics": list(self.metrics),
            "frame_range": self.frame_range,
        }

    def derive_config_sha256(self) -> str:
        return sha256_json(self._config_payload())

    def derive_experiment_id(self) -> str:
        data = self.to_dict()
        data.pop("experiment_id")
        return sha256_json(data)

    @classmethod
    def create(cls, *, created_at: str | None = None, **values: Any) -> ExperimentManifest:
        timestamp = created_at or _utc_now()
        variants = tuple(dict(v) for v in values["variants"])
        metrics = tuple(values["metrics"])
        config_sha256 = sha256_json({
            "source_id": values["source_id"],
            "baseline": values["baseline"],
            "variants": list(variants),
            "metrics": list(metrics),
            "frame_range": values["frame_range"],
        })
        content = {
            **values,
            "variants": list(variants),
            "metrics": list(metrics),
            "config_sha256": config_sha256,
            "created_at": timestamp,
            "schema_version": SCHEMA_VERSION,
        }
        experiment_id = sha256_json(content)
        return cls(
            experiment_id=experiment_id,
            variants=variants,
            metrics=metrics,
            config_sha256=config_sha256,
            created_at=timestamp,
            **{k: v for k, v in values.items() if k not in {"variants", "metrics"}},
        )


@dataclass(frozen=True, slots=True)
class TrackObservationRecord(ContractRecord):
    """Portable form of the tracker's public confirmed observation."""

    frame_index: int
    track_id: int
    xyxy: tuple[float, float, float, float]
    score: float
    class_id: int
    state: str = "confirmed"
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.frame_index < 0 or self.track_id <= 0:
            raise ValueError("frame_index must be non-negative and track_id positive")
        object.__setattr__(self, "xyxy", _box(self.xyxy))
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("score must be finite and in [0, 1]")
        if not isinstance(self.class_id, int):
            raise ValueError("class_id must be an integer")
        if self.state != "confirmed":
            raise ValueError("schema v1 exports confirmed observations only")

    @classmethod
    def from_observation(cls, observation: TrackObservation) -> TrackObservationRecord:
        return cls(
            frame_index=int(observation.frame),
            track_id=int(observation.track_id),
            xyxy=tuple(float(v) for v in observation.xyxy),
            score=float(observation.score),
            class_id=int(observation.class_id),
        )
