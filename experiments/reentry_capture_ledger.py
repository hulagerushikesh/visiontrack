"""Validate owner-local RQ5 capture metadata before any real-video scoring.

No video, crops, embeddings, names, or contact information are read or stored.
The caller must keep records and the private participant-group mapping local.
This contract cannot prove that the mapping or visual labels are truthful,
or that two distinct reviewer codes represent independent reviewers.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

EventLabel = Literal["novel", "return", "occlusion_control", "indeterminate"]
Split = Literal["development", "test"]
LABELS = frozenset(("novel", "return", "occlusion_control", "indeterminate"))
SPLITS = frozenset(("development", "test"))


@dataclass(frozen=True)
class IndependentReview:
    reviewer_code: str
    label: EventLabel

    def __post_init__(self) -> None:
        if not self.reviewer_code.strip():
            raise ValueError("reviewer_code must not be empty")
        if self.label not in LABELS:
            raise ValueError("invalid review label")


@dataclass(frozen=True)
class CaptureEvent:
    """One proposed opportunity, with two pre-decision visual reviews.

    ``participant_group`` is a stable, random owner-private key across
    sessions, used solely to catch development/test identity leakage.
    ``session_person_code`` is the within-session anonymous identity.
    ``opportunity_frame`` is the first visible frame of the proposed arrival.
    """

    event_id: str
    recording_id: str
    session_id: str
    participant_group: str
    session_person_code: str
    split: Split
    opportunity_frame: int
    reviews: tuple[IndependentReview, IndependentReview]
    last_visible_before_exit_frame: int | None = None
    first_out_of_scene_frame: int | None = None
    adjudicated_label: EventLabel | None = None
    adjudication_reason: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "event_id",
            "recording_id",
            "session_id",
            "participant_group",
            "session_person_code",
        ):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        if self.split not in SPLITS:
            raise ValueError("invalid split")
        if self.opportunity_frame < 1:
            raise ValueError("opportunity_frame must be positive")
        if len(self.reviews) != 2 or len({r.reviewer_code for r in self.reviews}) != 2:
            raise ValueError("require two distinct reviewer codes")

        first, second = self.reviews
        if first.label == second.label:
            if self.adjudicated_label is not None or self.adjudication_reason is not None:
                raise ValueError("agreed reviews must not be overridden")
        elif self.adjudicated_label is None:
            if self.adjudication_reason is not None:
                raise ValueError("adjudication_reason requires a final label")
        elif self.adjudicated_label not in LABELS or not (
            self.adjudication_reason and self.adjudication_reason.strip()
        ):
            raise ValueError("disagreement requires a valid label and reason")

        before = self.last_visible_before_exit_frame
        out = self.first_out_of_scene_frame
        if (before is None) != (out is None):
            raise ValueError("exit boundary needs both last-visible and first-out frames")
        if before is not None and not (1 <= before < out < self.opportunity_frame):
            raise ValueError("exit boundary frames must precede the opportunity in order")
        if self.resolved_label == "return" and before is None:
            raise ValueError("verified return requires an observable exit boundary")
        if self.resolved_label == "novel" and before is not None:
            raise ValueError("novel arrival must not have a prior exit boundary")

    @property
    def resolved_label(self) -> EventLabel:
        if self.reviews[0].label == self.reviews[1].label:
            return self.reviews[0].label
        return self.adjudicated_label or "indeterminate"


@dataclass(frozen=True)
class LedgerValidation:
    events: int
    novel: int
    returns: int
    occlusion_controls: int
    indeterminate: int
    development_events: int
    test_events: int


def validate_capture_ledger(events: Iterable[CaptureEvent]) -> LedgerValidation:
    """Fail closed on duplicate events, inconsistent codes, or split leakage.

    This checks metadata only. It does not turn accepted events into an
    accuracy claim or verify consent, footage, annotations, or sample power.
    """
    seen_events: set[str] = set()
    recording_splits: dict[str, Split] = {}
    session_recordings: dict[str, str] = {}
    session_splits: dict[str, Split] = {}
    participant_splits: dict[str, Split] = {}
    session_code_groups: dict[tuple[str, str], str] = {}
    session_group_codes: dict[tuple[str, str], str] = {}
    seen_opportunities: set[tuple[str, str, int]] = set()
    counts = {label: 0 for label in LABELS}
    splits = {split: 0 for split in SPLITS}

    for event in events:
        if event.event_id in seen_events:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        seen_events.add(event.event_id)
        opportunity = (event.session_id, event.participant_group, event.opportunity_frame)
        if opportunity in seen_opportunities:
            raise ValueError(f"duplicate participant opportunity: {opportunity}")
        seen_opportunities.add(opportunity)
        for mapping, key, value, name in (
            (recording_splits, event.recording_id, event.split, "recording split"),
            (session_recordings, event.session_id, event.recording_id, "session recording"),
            (session_splits, event.session_id, event.split, "session split"),
            (participant_splits, event.participant_group, event.split, "participant split"),
            (
                session_code_groups,
                (event.session_id, event.session_person_code),
                event.participant_group,
                "session person code",
            ),
            (
                session_group_codes,
                (event.session_id, event.participant_group),
                event.session_person_code,
                "session participant group",
            ),
        ):
            if key in mapping and mapping[key] != value:
                raise ValueError(f"conflicting {name}: {key}")
            mapping[key] = value
        counts[event.resolved_label] += 1
        splits[event.split] += 1

    return LedgerValidation(
        events=len(seen_events),
        novel=counts["novel"],
        returns=counts["return"],
        occlusion_controls=counts["occlusion_control"],
        indeterminate=counts["indeterminate"],
        development_events=splits["development"],
        test_events=splits["test"],
    )
