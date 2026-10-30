"""Screen MOT-format detections for exact ground-truth geometry reuse.

This is a development-data provenance diagnostic, not a detector metric or
proof that a stream with different boxes was produced independently. It reads
only the two explicit files supplied by the caller and never opens images.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

BoxKey = tuple[int, Decimal, Decimal, Decimal, Decimal]


def _box_key(row: list[str]) -> BoxKey:
    try:
        frame = int(row[0])
        x, y, width, height = (Decimal(value) for value in row[2:6])
    except (ValueError, InvalidOperation, IndexError) as exc:
        raise ValueError("invalid MOT frame or box") from exc
    if (frame < 1 or not all(value.is_finite() for value in (x, y, width, height))
            or width <= 0 or height <= 0):
        raise ValueError("invalid MOT frame or box")
    return frame, x, y, width, height


def audit_rows(gt_rows: list[list[str]], det_rows: list[list[str]]) -> dict:
    """Compare numeric box multisets, preserving duplicate multiplicity."""
    if not gt_rows or not det_rows:
        raise ValueError("both MOT streams must contain rows")
    if any(len(row) != 9 for row in gt_rows) or any(len(row) != 10 for row in det_rows):
        raise ValueError("expected nine GT columns and ten detection columns")
    gt_boxes = Counter(_box_key(row) for row in gt_rows)
    det_boxes = Counter(_box_key(row) for row in det_rows)
    shared = sum((gt_boxes & det_boxes).values())
    all_det = shared == len(det_rows)
    return {
        "gt_rows": len(gt_rows),
        "det_rows": len(det_rows),
        "exact_numeric_gt_det_box_matches": shared,
        "all_detection_boxes_match_gt_geometry": all_det,
        "identical_box_multisets": all_det and len(gt_rows) == len(det_rows),
        "geometry_screen": (
            "review_gt_geometry_mirror" if all_det else "independence_unverified"
        ),
        "independent_detector_verified": False,
    }


def _read_rows(path: Path, columns: int) -> tuple[list[list[str]], str]:
    payload = path.read_bytes()
    with io.StringIO(payload.decode("utf-8"), newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows or any(len(row) != columns for row in rows):
        raise ValueError(f"invalid {columns}-column MOT file: {path}")
    return rows, hashlib.sha256(payload).hexdigest()


def audit_files(gt_path: Path, det_path: Path) -> dict:
    if gt_path.resolve() == det_path.resolve():
        raise ValueError("GT and detection files must differ")
    gt_rows, gt_digest = _read_rows(gt_path, 9)
    det_rows, det_digest = _read_rows(det_path, 10)
    result = audit_rows(gt_rows, det_rows)
    return {
        "schema": "visiontrack.mot-detection-provenance-screen/v1",
        "scope": "explicit files only; numeric box geometry; no media or tracker",
        "gt_sha256": gt_digest,
        "detections_sha256": det_digest,
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gt", required=True, type=Path)
    parser.add_argument("--detections", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit_files(args.gt, args.detections)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
