"""Strict MOTChallenge ground-truth import for Reliability Lab bundles."""
from __future__ import annotations

import math
from pathlib import Path

from .contracts import GroundTruthRecord


def _number(value: str, *, line: int, field: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"MOT line {line}: {field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"MOT line {line}: {field} must be finite")
    return parsed


def _integer(value: str, *, line: int, field: str) -> int:
    parsed = _number(value, line=line, field=field)
    if not parsed.is_integer():
        raise ValueError(f"MOT line {line}: {field} must be an integer")
    return int(parsed)


def import_mot_ground_truth(
    path: str | Path, *, frame_count: int | None = None
) -> list[GroundTruthRecord]:
    """Import strict nine-column MOTChallenge ground truth.

    MOT frame numbers are one-based and become zero-based ``frame_index``
    values. The original number is preserved as ``source_frame``. Spatial
    coordinates are not shifted: ``(left, top, width, height)`` becomes
    ``(left, top, left + width, top + height)`` in pixel space.
    """
    source_path = Path(path)
    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read MOT ground truth: {source_path}") from exc

    records: list[GroundTruthRecord] = []
    seen: set[tuple[int, int]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            raise ValueError(f"MOT line {line_number}: blank lines are not supported")
        columns = [column.strip() for column in raw_line.split(",")]
        if len(columns) != 9:
            raise ValueError(
                f"MOT line {line_number}: expected exactly 9 columns, got {len(columns)}"
            )
        frame = _integer(columns[0], line=line_number, field="frame")
        object_id = _integer(columns[1], line=line_number, field="id")
        left = _number(columns[2], line=line_number, field="left")
        top = _number(columns[3], line=line_number, field="top")
        width = _number(columns[4], line=line_number, field="width")
        height = _number(columns[5], line=line_number, field="height")
        consider = _integer(columns[6], line=line_number, field="consider")
        class_id = _integer(columns[7], line=line_number, field="class")
        visibility = _number(columns[8], line=line_number, field="visibility")

        if frame < 1:
            raise ValueError(f"MOT line {line_number}: frame must be one-based and positive")
        if object_id <= 0:
            raise ValueError(f"MOT line {line_number}: id must be positive")
        if width <= 0 or height <= 0:
            raise ValueError(f"MOT line {line_number}: width and height must be positive")
        if consider not in {0, 1}:
            raise ValueError(f"MOT line {line_number}: consider must be 0 or 1")
        if not 0 <= visibility <= 1:
            raise ValueError(f"MOT line {line_number}: visibility must be in [0, 1]")

        frame_index = frame - 1
        if frame_count is not None and frame_index >= frame_count:
            raise ValueError(
                f"MOT line {line_number}: frame {frame} exceeds frame_count {frame_count}"
            )
        key = (frame_index, object_id)
        if key in seen:
            raise ValueError(
                f"MOT line {line_number}: duplicate object id {object_id} in frame {frame}"
            )
        seen.add(key)
        records.append(
            GroundTruthRecord(
                frame_index=frame_index,
                source_frame=frame,
                object_id=object_id,
                xyxy=(left, top, left + width, top + height),
                class_id=class_id,
                visibility=visibility,
                ignored=consider == 0,
            )
        )
    return sorted(records, key=lambda record: (record.frame_index, record.object_id))
