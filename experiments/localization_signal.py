"""Offline proposal-spread arithmetic for the localization research audit.

This module is deliberately outside the installed tracker package. A small
spread is agreement among decoder proposals, not evidence of correct location.
No labels, tracker matches or model state enter the calculation.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

from visiontrack.detection.proposal_capture import ProposalCapture, ProposalRecord

Refusal = Literal[
    "frame_truncated",
    "missing_winner",
    "incomplete_group",
    "singleton_group",
    "few_same_class",
    "invalid_geometry",
]


@dataclass(frozen=True, slots=True)
class SpreadRow:
    output_index: int
    winner_index: int | None
    status: Literal["supported"] | Refusal
    spread: float | None
    group_size: int | None
    same_class_count: int | None
    mixed_class_fraction: float | None


@dataclass(frozen=True, slots=True)
class FrameSpreadAudit:
    schema: Literal["visiontrack.localization-spread/v1"]
    frame_status: Literal["complete", "frame_truncated"]
    total_proposals: int
    returned_count: int
    rows: tuple[SpreadRow, ...]

    def to_dict(self) -> dict:
        """Compact, JSON-ready values; no boxes, images or proposal records."""
        return asdict(self)


def _anchor(record: ProposalRecord) -> tuple[float, float] | None:
    box = record.xyxy
    if len(box) != 4 or not all(math.isfinite(x) for x in box):
        return None
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return None
    anchor_x = x1 / 2 + x2 / 2
    return (anchor_x, y2) if math.isfinite(anchor_x) else None


def _row(
    output_index: int,
    winner: ProposalRecord | None,
    members: tuple[ProposalRecord, ...],
) -> SpreadRow:
    def refused(
        reason: Refusal,
        *,
        group_size: int | None = None,
        same_class_count: int | None = None,
        mixed_class_fraction: float | None = None,
    ) -> SpreadRow:
        return SpreadRow(
            output_index,
            None if winner is None else winner.proposal_index,
            reason,
            None,
            group_size,
            same_class_count,
            mixed_class_fraction,
        )

    if winner is None:
        return refused("missing_winner")
    size = winner.group_size
    # A claimed complete group must still agree with the actual captured rows.
    if (
        winner.group_winner_index != winner.proposal_index
        or size is None
        or winner.group_complete is not True
        or len(members) != size
        or any(
            r.group_size != size
            or r.captured_group_size != size
            or r.group_complete is not True
            or (r.status == "nms_suppressed") != (r is not winner)
            for r in members
        )
    ):
        return refused("incomplete_group", group_size=size)
    if size == 1:
        return refused(
            "singleton_group", group_size=size, same_class_count=1, mixed_class_fraction=0.0
        )
    same = tuple(r for r in members if r.class_id == winner.class_id)
    fraction = (size - len(same)) / size
    if len(same) < 3:
        return refused(
            "few_same_class",
            group_size=size,
            same_class_count=len(same),
            mixed_class_fraction=fraction,
        )
    if any(_anchor(r) is None for r in members):
        return refused(
            "invalid_geometry",
            group_size=size,
            same_class_count=len(same),
            mixed_class_fraction=fraction,
        )
    winner_anchor = _anchor(winner)
    assert winner_anchor is not None
    wx, wy = winner_anchor
    distances = []
    for record in same:
        anchor = _anchor(record)
        assert anchor is not None
        distances.append(math.hypot(anchor[0] - wx, anchor[1] - wy))
    distances.sort()
    middle = len(distances) // 2
    median = (
        distances[middle] if len(distances) % 2 else (distances[middle - 1] + distances[middle]) / 2
    )
    spread = median / (winner.xyxy[3] - winner.xyxy[1])
    if not math.isfinite(spread):
        return refused(
            "invalid_geometry",
            group_size=size,
            same_class_count=len(same),
            mixed_class_fraction=fraction,
        )
    return SpreadRow(
        output_index, winner.proposal_index, "supported", spread, size, len(same), fraction
    )


def audit_capture(capture: ProposalCapture) -> FrameSpreadAudit:
    """Summarize one frame, refusing *all* outputs when any row was omitted.

    Call with a full-frame cap chosen from the pinned model shape. The caller
    owns the capture lifetime and input provenance; this retains neither.
    """
    if capture.schema != "visiontrack.yolox-proposals/v1":
        raise ValueError("unsupported proposal capture schema")
    if (
        capture.total_proposals < 0
        or capture.returned_count < 0
        or capture.returned_count > capture.total_proposals
        or capture.omitted_count < 0
    ):
        raise ValueError("inconsistent capture counts")
    truncated = capture.truncated
    if truncated:
        rows = tuple(
            SpreadRow(i, None, "frame_truncated", None, None, None, None)
            for i in range(capture.returned_count)
        )
    else:
        records = capture.records
        if len({r.proposal_index for r in records}) != len(records) or {
            r.proposal_index for r in records
        } != set(range(capture.total_proposals)):
            raise ValueError("full capture must contain each proposal index once")
        winners: dict[int, ProposalRecord] = {}
        for record in records:
            if record.output_index is None or record.status != "returned":
                continue
            if not 0 <= record.output_index < capture.returned_count:
                raise ValueError("returned output index outside capture count")
            if record.output_index in winners:
                raise ValueError("duplicate returned output index")
            winners[record.output_index] = record
        # Index once: scanning every proposal for each returned detection made
        # full-frame audits quadratic when a frame contained many small groups.
        grouped: dict[int, list[ProposalRecord]] = {}
        for record in records:
            if record.group_winner_index is not None:
                grouped.setdefault(record.group_winner_index, []).append(record)
        audited = []
        for i in range(capture.returned_count):
            winner = winners.get(i)
            members = tuple(grouped.get(winner.proposal_index, ())) if winner else ()
            audited.append(_row(i, winner, members))
        rows = tuple(audited)
    return FrameSpreadAudit(
        "visiontrack.localization-spread/v1",
        "frame_truncated" if truncated else "complete",
        capture.total_proposals,
        capture.returned_count,
        rows,
    )
