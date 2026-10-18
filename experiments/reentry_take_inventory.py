"""Reconcile a private RQ5 pilot's planned take slots with reviewed events.

This is a metadata check, not proof that footage exists, labels are truthful,
or exclusions are justified. Populated inventories remain outside Git.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from experiments.reentry_capture_ledger import CaptureEvent
from experiments.reentry_capture_manifest import CaptureManifest, Scenario, Split

TakeStatus = Literal["recorded", "missing", "excluded"]
ExclusionCode = Literal["withdrawn", "bystander", "technical", "other"]
STATUSES = frozenset(("recorded", "missing", "excluded"))
EXCLUSION_CODES = frozenset(("withdrawn", "bystander", "technical", "other"))
EVENT_LABELS = {
    "novel": "novel",
    "short_return": "return",
    "long_return": "return",
    "expired_return": "return",
    "lookalike_novel": "novel",
    "occlusion_control": "occlusion_control",
}
MAX_TAKES = 20_000


@dataclass(frozen=True)
class TakeRecord:
    take_id: str
    split: Split
    scenario: Scenario
    slot: int
    status: TakeStatus
    recording_id: str | None
    session_id: str | None
    event_id: str | None
    exclusion_code: ExclusionCode | None

    def __post_init__(self) -> None:
        if not self.take_id.strip():
            raise ValueError("take_id must not be empty")
        if type(self.slot) is not int or self.slot < 1:
            raise ValueError("slot must be a positive integer")
        if self.status not in STATUSES:
            raise ValueError("invalid take status")
        if self.status == "recorded":
            if (
                not self.recording_id
                or not self.recording_id.strip()
                or not self.session_id
                or not self.session_id.strip()
                or self.exclusion_code is not None
            ):
                raise ValueError("recorded take needs recording and session, without exclusion")
            if self.scenario == "session_reset":
                if self.event_id is not None:
                    raise ValueError("session reset must not reference an event")
            elif not self.event_id or not self.event_id.strip():
                raise ValueError("recorded opportunity needs an event_id")
        elif self.recording_id or self.session_id or self.event_id:
            raise ValueError("missing or excluded take must not reference media or events")
        elif self.status == "excluded" and self.exclusion_code not in EXCLUSION_CODES:
            raise ValueError("excluded take needs a permitted exclusion code")
        elif self.status == "missing" and self.exclusion_code is not None:
            raise ValueError("missing take must not have an exclusion code")


@dataclass(frozen=True)
class TakeInventory:
    manifest_sha256: str
    takes: tuple[TakeRecord, ...]


@dataclass(frozen=True)
class InventoryValidation:
    planned: int
    recorded: int
    missing: int
    excluded: int
    linked_events: int
    reset_controls: int


def validate_take_inventory(
    manifest: CaptureManifest,
    inventory: TakeInventory,
    events: tuple[CaptureEvent, ...],
) -> InventoryValidation:
    """Require one inventory row per frozen slot and exact event linkage."""
    if inventory.manifest_sha256 != manifest.fingerprint:
        raise ValueError("inventory does not match the frozen manifest")
    planned = sum(take.count for take in manifest.planned_takes)
    if planned > MAX_TAKES or len(inventory.takes) > MAX_TAKES:
        raise ValueError("pilot exceeds the take limit")
    expected = {
        (take.split, take.scenario, slot)
        for take in manifest.planned_takes
        for slot in range(1, take.count + 1)
    }
    actual = [(take.split, take.scenario, take.slot) for take in inventory.takes]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("inventory must cover each planned slot exactly once")
    if len({take.take_id for take in inventory.takes}) != len(inventory.takes):
        raise ValueError("duplicate take_id")

    by_event = {event.event_id: event for event in events}
    referenced: set[str] = set()
    recording_splits: dict[str, str] = {}
    session_links: dict[str, tuple[str, str]] = {}
    for take in inventory.takes:
        if take.status != "recorded":
            continue
        assert take.recording_id is not None and take.session_id is not None
        if (
            take.recording_id in recording_splits
            and recording_splits[take.recording_id] != take.split
        ):
            raise ValueError("recording crosses development/test split")
        recording_splits[take.recording_id] = take.split
        link = (take.recording_id, take.split)
        if take.session_id in session_links and session_links[take.session_id] != link:
            raise ValueError("session changes recording or split")
        session_links[take.session_id] = link
        if take.scenario == "session_reset":
            continue
        if take.event_id in referenced or take.event_id not in by_event:
            raise ValueError("take event link is missing or duplicated")
        referenced.add(take.event_id)
        event = by_event[take.event_id]
        if (
            event.split != take.split
            or event.recording_id != take.recording_id
            or event.session_id != take.session_id
            or event.resolved_label != EVENT_LABELS[take.scenario]
        ):
            raise ValueError("take event metadata does not match its planned scenario")
    if referenced != set(by_event):
        raise ValueError("ledger contains events not linked to recorded takes")
    return InventoryValidation(
        planned=planned,
        recorded=sum(take.status == "recorded" for take in inventory.takes),
        missing=sum(take.status == "missing" for take in inventory.takes),
        excluded=sum(take.status == "excluded" for take in inventory.takes),
        linked_events=len(referenced),
        reset_controls=sum(
            take.status == "recorded" and take.scenario == "session_reset"
            for take in inventory.takes
        ),
    )
