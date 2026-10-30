"""Audit the small DroneTrafficZA2020 count files without scoring a tracker.

The publisher's reference marks frame entry; OpenDataCam records crossings of
three configured lines. This audit checks source integrity and whether those
streams can even be aligned. It never opens the video or executes publisher code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

PUBLISHER_SHA256 = {
    "groundTruth.csv": "886464d19e1824d3b6a96eef5ae94b0db72699810eb256780d5e0b33a9fdf3af",
    "OpenDataCam.csv": "03eda3d056910e4592c9377398708a89d9f00178a68e3ce81a431ea31640ded2",
}


def _read_pinned(path: Path, name: str) -> list[list[str]]:
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != PUBLISHER_SHA256[name]:
        raise ValueError(f"{name} SHA-256 differs from publisher file manifest")
    with io.StringIO(payload.decode("utf-8-sig"), newline="") as stream:
        return list(csv.reader(stream))


def _frame(value: str) -> int:
    frame = int(value)
    if frame < 0:
        raise ValueError("negative frame")
    return frame


def audit_rows(reference: list[list[str]], candidate: list[list[str]]) -> dict:
    """Report file-format and temporal questions, never a count accuracy score."""
    if not reference or not candidate:
        raise ValueError("both event streams must contain rows")
    invalid_reference: list[int] = []
    invalid_candidate: list[int] = []
    reference_events: list[tuple[int, str]] = []
    candidate_events: list[tuple[int, str, str]] = []
    for line, row in enumerate(reference, 1):
        try:
            if len(row) != 2 or row[1] not in {"c", "t", "m", "p"}:
                raise ValueError("invalid reference columns or class")
            reference_events.append((_frame(row[0]), row[1]))
        except ValueError:
            invalid_reference.append(line)
    for line, row in enumerate(candidate, 1):
        try:
            if len(row) != 8 or row[2] not in {"1", "2", "3"}:
                raise ValueError("invalid candidate columns or line")
            if row[3] not in {"car", "truck", "motorbike", "person"}:
                raise ValueError("invalid candidate class")
            candidate_events.append((_frame(row[0]), row[2], row[6]))
        except ValueError:
            invalid_candidate.append(line)
    if not reference_events or not candidate_events:
        raise ValueError("no valid events in one or both streams")
    last_candidate = max(frame for frame, _, _ in candidate_events)
    ref_after = sum(frame > last_candidate for frame, _ in reference_events)
    reference_classes = Counter(cls for _, cls in reference_events)
    candidate_lines = Counter(line for _, line, _ in candidate_events)
    candidate_directions = Counter(direction for _, _, direction in candidate_events)
    reference_frames = [frame for frame, _ in reference_events]
    candidate_frames = [frame for frame, _, _ in candidate_events]
    return {
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "invalid_reference_lines": invalid_reference,
        "invalid_candidate_lines": invalid_candidate,
        "reference_class_counts_valid_rows": dict(sorted(reference_classes.items())),
        "candidate_line_counts_valid_rows": dict(sorted(candidate_lines.items())),
        "candidate_direction_counts_valid_rows": dict(sorted(candidate_directions.items())),
        "reference_frame_range_valid_rows": [min(reference_frames), max(reference_frames)],
        "candidate_event_frame_range_valid_rows": [min(candidate_frames), last_candidate],
        "reference_events_after_last_candidate_event": ref_after,
        "reference_event_semantics": "vehicle first observed entering frame; westbound only",
        "candidate_event_semantics": (
            "crossing one of three configured lines; includes both directions"
        ),
        "direct_event_comparison_ready": False,
        "dense_tracking_identity_truth_available": False,
        "admission": "hold",
        "hold_reasons": [
            "event definitions differ (frame entry versus line crossing)",
            (
                "reference file has malformed rows"
                if invalid_reference else "reference labels need visual audit"
            ),
            (
                "candidate processing interval needs verification: reference events "
                "occur after its last event"
                if ref_after else "candidate processing interval needs verification"
            ),
            "single drone scene has no scene-disjoint outcome split or dense identity labels",
        ],
    }


def audit_files(reference_path: Path, candidate_path: Path) -> dict:
    if reference_path.resolve() == candidate_path.resolve():
        raise ValueError("reference and candidate paths must differ")
    result = audit_rows(
        _read_pinned(reference_path, "groundTruth.csv"),
        _read_pinned(candidate_path, "OpenDataCam.csv"),
    )
    return {
        "schema": "visiontrack.dronetrafficza-source-screen/v1",
        "publisher": "https://data.mendeley.com/datasets/wdfkxsnpzc/1",
        "reference_sha256": PUBLISHER_SHA256["groundTruth.csv"],
        "candidate_sha256": PUBLISHER_SHA256["OpenDataCam.csv"],
        "scope": "small count files only; no video, tracker replay or outcome score",
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit_files(args.reference, args.candidate)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
