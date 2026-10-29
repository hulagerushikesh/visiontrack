"""Audit a small, local SVMOT development sample before any tracker experiment.

The script reads only explicitly named official-train sequences. It never reads
the publisher test split, runs tracking, or treats supplied detections as an
independent detector without checking their box coordinates against GT.
"""
from __future__ import annotations

import argparse
import configparser
import csv
import json
from collections import Counter
from pathlib import Path


def _audit_occlusions(path: Path, gt_by_frame: dict[int, dict[int, tuple[float, ...]]],
                      length: int) -> dict:
    """Check annotation cross-references, not the truth of the labels in pixels."""
    if not path.is_file():
        return {"occlusion_annotation_present": False}
    frames = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(frames, list) or len(frames) != length:
        raise ValueError("occlusion frame coverage mismatch")
    links = 0
    objects = 0
    stopped = 0
    for expected_frame, entry in enumerate(frames, 1):
        if not isinstance(entry, dict) or entry.get("frame_id") != expected_frame:
            raise ValueError("occlusion frame order mismatch")
        listed = entry.get("objects")
        if not isinstance(listed, list):
            raise ValueError("invalid occlusion objects")
        ids = [obj.get("object_id") for obj in listed if isinstance(obj, dict)]
        if (len(ids) != len(listed) or len(ids) != len(set(ids)) or
                set(ids) != set(gt_by_frame.get(expected_frame, {}))):
            raise ValueError("occlusion/GT object IDs mismatch")
        for obj in listed:
            object_id = obj["object_id"]
            box = obj.get("bbox")
            if (not isinstance(box, list) or len(box) != 4 or
                    tuple(box) != gt_by_frame[expected_frame][object_id]):
                raise ValueError("occlusion/GT box mismatch")
            if (not isinstance(obj.get("stopped"), bool) or
                    not isinstance(obj.get("occlusions"), list)):
                raise ValueError("invalid stopped/occlusion fields")
            objects += 1
            stopped += obj["stopped"]
            x, y, width, height = box
            for link in obj["occlusions"]:
                if (not isinstance(link, dict) or link.get("occluder_id") not in ids or
                        link["occluder_id"] == object_id):
                    raise ValueError("invalid occluder reference")
                area_box = link.get("occlusion_bbox")
                area = link.get("area")
                if (not isinstance(area_box, list) or len(area_box) != 4 or
                        not all(isinstance(value, (int, float)) for value in area_box) or
                        not isinstance(area, (int, float))):
                    raise ValueError("invalid occlusion geometry")
                ox, oy, ow, oh = area_box
                if (ow <= 0 or oh <= 0 or area != ow * oh or
                        not (x <= ox and y <= oy and ox + ow <= x + width and
                             oy + oh <= y + height)):
                    raise ValueError("invalid occlusion geometry")
                links += 1
    return {
        "occlusion_annotation_present": True,
        "occlusion_frames": len(frames),
        "occlusion_objects": objects,
        "occlusion_links": links,
        "stopped_true_rows": stopped,
        "occlusion_gt_structure_matches": True,
    }


def _rows(path: Path, columns: int) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    if not rows or any(len(row) != columns for row in rows):
        raise ValueError(f"invalid {columns}-column rows: {path}")
    return rows


def _geometry(row: list[str], *, width: int, height: int) -> tuple[str, ...]:
    frame, x, y, box_width, box_height = row[0], *row[2:6]
    f = int(frame)
    x0, y0, w, h = map(float, (x, y, box_width, box_height))
    if f < 1 or not (0 <= x0 < width and 0 <= y0 < height
                     and w > 0 and h > 0 and x0 + w <= width + 1
                     and y0 + h <= height + 1):
        raise ValueError("invalid frame or bounding-box geometry")
    return frame, x, y, box_width, box_height


def audit_sequence(root: Path, sequence: str, class_count: int) -> dict:
    folder = root / "data" / sequence
    meta = configparser.ConfigParser()
    if not meta.read(folder / "seqinfo.ini") or "Sequence" not in meta:
        raise ValueError(f"missing sequence metadata: {sequence}")
    section = meta["Sequence"]
    length = section.getint("seqlength")
    width = section.getint("imwidth")
    height = section.getint("imheight")
    if min(length, width, height) <= 0:
        raise ValueError(f"invalid sequence metadata: {sequence}")
    gt = _rows(folder / "gt" / "gt.txt", 9)
    det = _rows(folder / "det" / "det.txt", 10)
    ids: set[int] = set()
    frame_ids: set[tuple[int, int]] = set()
    classes: Counter[int] = Counter()
    gt_boxes: Counter[tuple[str, ...]] = Counter()
    det_boxes: Counter[tuple[str, ...]] = Counter()
    gt_frames: set[int] = set()
    gt_by_frame: dict[int, dict[int, tuple[float, ...]]] = {}
    for row in gt:
        box = _geometry(row, width=width, height=height)
        frame = int(row[0])
        object_id = int(row[1])
        category = int(row[7])
        visibility = float(row[8])
        if (frame > length or row[1] == "" or not 0 <= category < class_count
                or not 0 <= visibility <= 1):
            raise ValueError(f"invalid GT label: {sequence}")
        if (frame, object_id) in frame_ids:
            raise ValueError(f"duplicate GT frame/ID: {sequence}")
        frame_ids.add((frame, object_id))
        gt_by_frame.setdefault(frame, {})[object_id] = tuple(map(float, row[2:6]))
        gt_frames.add(frame)
        ids.add(object_id)
        classes[category] += 1
        gt_boxes[box] += 1
    for row in det:
        box = _geometry(row, width=width, height=height)
        if int(row[0]) > length or not 0 <= float(row[6]) <= 1:
            raise ValueError(f"invalid detection: {sequence}")
        det_boxes[box] += 1
    samples = sorted((folder / "img").glob("*.jpg"))
    for image in samples:
        if not image.stem.isdigit() or not 1 <= int(image.stem) <= length:
            raise ValueError(f"invalid sample image frame: {image}")
    shared = sum((gt_boxes & det_boxes).values())
    result = {
        "sequence": sequence,
        "declared_sequence_name": section.get("name"),
        "declared_name_matches_directory": section.get("name") == sequence,
        "declared_frames": length,
        "gt_rows": len(gt),
        "gt_nonempty_frames": len(gt_frames),
        "gt_unique_ids": len(ids),
        "gt_classes": dict(sorted(classes.items())),
        "det_rows": len(det),
        "exact_gt_det_box_matches": shared,
        "all_det_boxes_match_gt": shared == len(det),
        "all_gt_boxes_match_det": shared == len(gt),
        "local_sample_images": len(samples),
    }
    result.update(_audit_occlusions(folder / "occlusion.json", gt_by_frame, length))
    return result


def audit(root: Path, train_file: Path, test_file: Path, sequences: list[str]) -> dict:
    train = set(train_file.read_text(encoding="utf-8").split())
    test = set(test_file.read_text(encoding="utf-8").split())
    if not train or train & test or not sequences or len(sequences) != len(set(sequences)):
        raise ValueError("invalid or overlapping split/selection")
    if any(Path(sequence).name != sequence or sequence in {".", ".."}
           for sequence in sequences):
        raise ValueError("sequence name must be a plain directory name")
    if not set(sequences) <= train or set(sequences) & test:
        raise ValueError("selection must contain official train sequences only")
    classes = (root / "classes.txt").read_text(encoding="utf-8").splitlines()
    if not classes or len(classes) != len(set(classes)):
        raise ValueError("missing or duplicate classes")
    return {
        "schema": "visiontrack.svmot-development-source-audit/v1",
        "scope": "selected official-train sequences, local sample only",
        "test_labels_opened": False,
        "tracker_ran": False,
        "independent_annotation_quality_verified": False,
        "sequences": [audit_sequence(root, seq, len(classes)) for seq in sequences],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--train-file", required=True, type=Path)
    parser.add_argument("--test-file", required=True, type=Path)
    parser.add_argument("--sequence", required=True, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.root, args.train_file, args.test_file, args.sequence)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
