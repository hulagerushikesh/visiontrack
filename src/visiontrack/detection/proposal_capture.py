"""Bounded, immutable per-frame YOLOX diagnostics; never tracker inputs.

Groups record greedy suppression, not verified alternative estimates of one
object. No covariance, calibrated probability or localization truth is inferred.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal

import numpy as np

ProposalStatus = Literal[
    "confidence_filtered", "nms_suppressed", "class_filtered", "returned"
]


@dataclass(frozen=True, slots=True)
class ProposalRecord:
    """One original decoder row (after layout normalization, before filtering).

    ``xyxy`` is in original-image pixels, unclipped, with top-left letterboxing
    undone by ``scale``. A group includes a greedy winner and its direct victims,
    including victims of another class. Below-threshold rows have no group.
    ``output_index`` refers to the ordinary returned detection list.
    """

    proposal_index: int
    xyxy: tuple[float, float, float, float]
    objectness: float
    class_score: float
    score: float
    class_id: int
    status: ProposalStatus
    group_winner_index: int | None = None
    group_size: int | None = None
    captured_group_size: int | None = None
    output_index: int | None = None

    @property
    def group_complete(self) -> bool | None:
        if self.group_size is None:
            return None
        return self.group_size == self.captured_group_size


@dataclass(frozen=True, slots=True)
class ProposalCapture:
    """One frame, first ``max_proposals`` rows in original decoder order.

    Counts cover the full frame even when records/groups are truncated. This
    prefix is not a representative sample. No image/model-output array is held.
    The caller controls any persistence; the detector retains no captures.
    """

    max_proposals: int
    total_proposals: int
    raw_shape: tuple[int, ...]
    transposed: bool
    grid_decode_applied: bool
    input_size: int
    strides: tuple[int, ...]
    scale: float
    conf_threshold: float
    iou_threshold: float
    class_filter: tuple[int, ...] | None
    confidence_filtered_count: int
    nms_suppressed_count: int
    nms_kept_count: int
    class_filtered_count: int
    returned_count: int
    records: tuple[ProposalRecord, ...]
    schema: Literal["visiontrack.yolox-proposals/v1"] = "visiontrack.yolox-proposals/v1"
    coordinates: Literal["original_image_xyxy_unclipped"] = "original_image_xyxy_unclipped"
    selection_policy: Literal["original_row_prefix"] = "original_row_prefix"
    nms_class_agnostic: bool = True
    class_filter_stage: Literal["after_nms"] = "after_nms"

    def to_dict(self) -> dict:
        """Detached plain values, including explicit truncation/completeness.

        No file is written. As with raw detector output, non-finite model values
        are not sanitized; use ``json.dumps(..., allow_nan=False)`` to refuse them.
        """
        result = asdict(self)
        result["omitted_count"] = self.omitted_count
        result["truncated"] = self.truncated
        result["records"] = [dict(asdict(r), group_complete=r.group_complete) for r in self.records]
        return result

    @property
    def omitted_count(self) -> int:
        return self.total_proposals - len(self.records)

    @property
    def truncated(self) -> bool:
        return self.omitted_count > 0


class _ProposalRecorder:
    """Transient recorder, allocated only by the explicit diagnostic call."""

    def __init__(
        self, boxes: np.ndarray, objectness: np.ndarray, class_scores: np.ndarray,
        class_ids: np.ndarray, scores: np.ndarray, eligible: np.ndarray,
        scale: float, limit: int,
    ) -> None:
        # Only this prefix is converted/copied for below-threshold diagnostics.
        n = min(limit, len(boxes))
        self.records = [
            ProposalRecord(
                proposal_index=i,
                xyxy=(
                    float((boxes[i, 0] - boxes[i, 2] / 2) / scale),
                    float((boxes[i, 1] - boxes[i, 3] / 2) / scale),
                    float((boxes[i, 0] + boxes[i, 2] / 2) / scale),
                    float((boxes[i, 1] + boxes[i, 3] / 2) / scale),
                ),
                objectness=float(objectness[i]),
                class_score=float(class_scores[i, class_ids[i]]),
                score=float(scores[i]), class_id=int(class_ids[i]),
                status="confidence_filtered",
            ) for i in range(n)
        ]
        self.eligible_indices = np.flatnonzero(eligible)
        self.nms_kept_count = 0
        self.nms_suppressed_count = 0
        self.class_filtered_count = 0

    def selection(
        self, winner: int, remaining: list[int], ious: np.ndarray, threshold: float,
    ) -> None:
        # Exactly the decoder's predicate: NaN overlap also fails <= threshold.
        suppressed = ~(ious <= threshold)
        size = 1 + int(np.count_nonzero(suppressed))
        original_winner = int(self.eligible_indices[winner])
        members = [original_winner] if original_winner < len(self.records) else []
        for local, removed in zip(remaining, suppressed, strict=True):
            original = int(self.eligible_indices[local])
            if removed and original < len(self.records):
                members.append(original)
        for original in members:
            self.records[original] = replace(
                self.records[original],
                status="returned" if original == original_winner else "nms_suppressed",
                group_winner_index=original_winner, group_size=size,
                captured_group_size=len(members),
            )
        self.nms_kept_count += 1
        self.nms_suppressed_count += size - 1

    def output(self, local: int, output_index: int | None) -> None:
        original = int(self.eligible_indices[local])
        if output_index is None:
            self.class_filtered_count += 1
        if original < len(self.records):
            self.records[original] = replace(
                self.records[original],
                status="class_filtered" if output_index is None else "returned",
                output_index=output_index,
            )


def _validate_limit(limit: int) -> None:
    if type(limit) is not int or limit < 0:
        raise ValueError("max_proposals must be a non-negative integer (not bool)")
