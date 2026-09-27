"""Versioned, browser-readable benchmark report records.

The experiment harness owns computation.  This module is the small persistence
boundary that lets those structured results cross into the web explorer without
parsing Markdown or HTML.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

SCHEMA_VERSION = 1
_REPORT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_VARIANT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_METRIC_KEY = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")
_CONFIG_HASH = re.compile(r"^[a-f0-9]{12}$")
_GIT_REVISION = re.compile(r"^[a-f0-9]{7,40}$")
_SOURCE_KINDS = {"checked_in_research_artifact", "structured_experiment_result"}


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")


@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    name: str
    split: str
    protocol: str
    detector: str
    pair_count: int
    runs_per_variant: int

    def __post_init__(self) -> None:
        for field_name in ("name", "split", "protocol", "detector"):
            _required_text(getattr(self, field_name), f"dataset.{field_name}")
        if (not isinstance(self.pair_count, int) or isinstance(self.pair_count, bool)
                or self.pair_count < 1):
            raise ValueError("dataset.pair_count must be a positive integer")
        if (not isinstance(self.runs_per_variant, int)
                or isinstance(self.runs_per_variant, bool)
                or self.runs_per_variant != self.pair_count):
            raise ValueError("dataset runs_per_variant must equal pair_count")


@dataclass(frozen=True, slots=True)
class BenchmarkProvenance:
    source_document: str
    source_kind: str
    config_hash: str
    visiontrack_version: str
    git_revision: str | None

    def __post_init__(self) -> None:
        _required_text(self.source_document, "provenance.source_document")
        if self.source_kind not in _SOURCE_KINDS:
            raise ValueError("unsupported benchmark provenance source_kind")
        if not isinstance(self.config_hash, str) or not _CONFIG_HASH.fullmatch(self.config_hash):
            raise ValueError("provenance.config_hash must be 12 lowercase hex characters")
        _required_text(self.visiontrack_version, "provenance.visiontrack_version")
        if (self.git_revision is not None
                and (not isinstance(self.git_revision, str)
                     or not _GIT_REVISION.fullmatch(self.git_revision))):
            raise ValueError("provenance.git_revision must be 7-40 lowercase hex characters")


@dataclass(frozen=True, slots=True)
class BenchmarkMetric:
    key: str
    label: str
    direction: str
    format: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not _METRIC_KEY.fullmatch(self.key):
            raise ValueError("metric.key is invalid")
        _required_text(self.label, "metric.label")
        if self.direction not in {"higher", "lower"}:
            raise ValueError("metric.direction must be higher or lower")
        if self.format not in {"score", "count"}:
            raise ValueError("metric.format must be score or count")


@dataclass(frozen=True, slots=True)
class BenchmarkValue:
    mean: float
    std: float | None
    delta: float
    p_value: float | None
    significant: bool

    def __post_init__(self) -> None:
        _finite(self.mean, "value.mean")
        _finite(self.delta, "value.delta")
        if self.std is not None:
            _finite(self.std, "value.std")
            if self.std < 0:
                raise ValueError("value.std must not be negative")
        if self.p_value is not None:
            _finite(self.p_value, "value.p_value")
            if not 0 <= self.p_value <= 1:
                raise ValueError("value.p_value must be in [0, 1]")
            if self.significant != (self.p_value < 0.05):
                raise ValueError("value.significant must match p_value < 0.05")
        elif self.significant:
            raise ValueError("value.significant requires a p_value")
        if not isinstance(self.significant, bool):
            raise ValueError("value.significant must be a boolean")


@dataclass(frozen=True, slots=True)
class BenchmarkVariant:
    name: str
    baseline: bool
    values: dict[str, BenchmarkValue]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _VARIANT_NAME.fullmatch(self.name):
            raise ValueError("variant.name is invalid")
        if not isinstance(self.baseline, bool):
            raise ValueError("variant.baseline must be a boolean")
        if not isinstance(self.values, dict) or not self.values:
            raise ValueError("variant.values must not be empty")
        if not all(isinstance(value, BenchmarkValue) for value in self.values.values()):
            raise ValueError("variant.values must contain BenchmarkValue records")
        if self.baseline:
            for result in self.values.values():
                if result.delta != 0 or result.significant:
                    raise ValueError("baseline values must remain zero-delta references")


@dataclass(frozen=True, slots=True)
class BenchmarkReportRecord:
    report_id: str
    title: str
    summary: str
    dataset: BenchmarkDataset
    provenance: BenchmarkProvenance
    baseline: str
    metrics: tuple[BenchmarkMetric, ...]
    variants: tuple[BenchmarkVariant, ...]
    limitations: tuple[str, ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if not isinstance(self.report_id, str) or not _REPORT_ID.fullmatch(self.report_id):
            raise ValueError("report_id is invalid")
        _required_text(self.title, "title")
        _required_text(self.summary, "summary")
        _required_text(self.baseline, "baseline")
        if not isinstance(self.dataset, BenchmarkDataset):
            raise ValueError("dataset must be a BenchmarkDataset record")
        if not isinstance(self.provenance, BenchmarkProvenance):
            raise ValueError("provenance must be a BenchmarkProvenance record")
        if not self.metrics:
            raise ValueError("at least one metric is required")
        if not all(isinstance(metric, BenchmarkMetric) for metric in self.metrics):
            raise ValueError("metrics must contain BenchmarkMetric records")
        metric_keys = [metric.key for metric in self.metrics]
        if len(metric_keys) != len(set(metric_keys)):
            raise ValueError("metric keys must be unique")
        if len(self.variants) < 2:
            raise ValueError("at least two variants are required")
        if not all(isinstance(variant, BenchmarkVariant) for variant in self.variants):
            raise ValueError("variants must contain BenchmarkVariant records")
        names = [variant.name for variant in self.variants]
        if len(names) != len(set(names)):
            raise ValueError("variant names must be unique")
        baselines = [variant for variant in self.variants if variant.baseline]
        if len(baselines) != 1 or baselines[0].name != self.baseline:
            raise ValueError("baseline must match exactly one variant")
        for variant in self.variants:
            if set(variant.values) != set(metric_keys):
                raise ValueError(f"variant {variant.name} must contain every metric exactly once")
        if not self.limitations:
            raise ValueError("at least one limitation is required")
        for limitation in self.limitations:
            _required_text(limitation, "limitation")

    def to_dict(self) -> dict[str, Any]:
        """Return the exact schema-v1 JSON object."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize deterministically, rejecting NaN and Infinity."""
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def to_bytes(self) -> bytes:
        """Return canonical, newline-terminated artifact bytes."""
        return (self.to_json() + "\n").encode("utf-8")
