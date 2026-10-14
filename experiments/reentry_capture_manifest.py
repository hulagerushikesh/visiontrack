"""Validate a private, pre-recording RQ5 pilot plan without handling footage.

The owner keeps populated manifests outside the repository. A valid structure
does not establish consent, legal rights, independent review, or data quality.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

Split = Literal["development", "test"]
Scenario = Literal[
    "novel",
    "short_return",
    "long_return",
    "expired_return",
    "lookalike_novel",
    "occlusion_control",
    "session_reset",
]
SPLITS = frozenset(("development", "test"))
SCENARIOS = frozenset(
    (
        "novel",
        "short_return",
        "long_return",
        "expired_return",
        "lookalike_novel",
        "occlusion_control",
        "session_reset",
    )
)


@dataclass(frozen=True)
class PlannedTake:
    split: Split
    scenario: Scenario
    count: int

    def __post_init__(self) -> None:
        if self.split not in SPLITS or self.scenario not in SCENARIOS:
            raise ValueError("invalid split or scenario")
        if self.count < 1:
            raise ValueError("planned take count must be positive")


@dataclass(frozen=True)
class CaptureManifest:
    """Frozen choices for one owner-local, same-camera pilot.

    Reference fields are owner-local document IDs, not names, URLs, or proof
    that a rights/consent review was performed. Do not commit populated plans.
    """

    study_id: str
    frozen_on: str
    camera_setup: str
    scene_exit_rule: str
    frame_rate: int
    width: int
    height: int
    short_absence_seconds: int
    long_absence_seconds: int
    gallery_ttl_seconds: int
    expired_return_seconds: int
    gallery_capacity: int
    retention_days: int
    rights_review_ref: str
    consent_process_ref: str
    withdrawal_process_ref: str
    storage_plan_ref: str
    permitted_scene_changes: tuple[str, ...]
    planned_takes: tuple[PlannedTake, ...]

    def __post_init__(self) -> None:
        for field in (
            "study_id",
            "camera_setup",
            "scene_exit_rule",
            "rights_review_ref",
            "consent_process_ref",
            "withdrawal_process_ref",
            "storage_plan_ref",
        ):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        try:
            if date.fromisoformat(self.frozen_on).isoformat() != self.frozen_on:
                raise ValueError
        except ValueError as exc:
            raise ValueError("frozen_on must be an ISO calendar date") from exc
        for field in ("frame_rate", "width", "height", "gallery_capacity", "retention_days"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")
        if not (
            0 < self.short_absence_seconds
            < self.long_absence_seconds
            < self.gallery_ttl_seconds
            < self.expired_return_seconds
        ):
            raise ValueError("absence intervals must order short < long < TTL < expired")
        if not self.permitted_scene_changes or any(
            not change.strip() for change in self.permitted_scene_changes
        ):
            raise ValueError("state permitted scene changes, including 'none'")
        seen: set[tuple[Split, Scenario]] = set()
        for take in self.planned_takes:
            key = (take.split, take.scenario)
            if key in seen:
                raise ValueError(f"duplicate planned take: {key}")
            seen.add(key)
        if {split for split, _ in seen} != SPLITS:
            raise ValueError("plan both development and test takes")
        if {scenario for _, scenario in seen} != SCENARIOS:
            raise ValueError("plan every required control scenario")

    @property
    def fingerprint(self) -> str:
        """Stable plan identifier; record it before capture, outside Git."""
        canonical = asdict(self)
        canonical["permitted_scene_changes"] = sorted(canonical["permitted_scene_changes"])
        canonical["planned_takes"] = sorted(
            canonical["planned_takes"], key=lambda take: (take["split"], take["scenario"])
        )
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
