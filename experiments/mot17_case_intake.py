"""Read-only, annotation-only intake for one existing MOT17 diagnostic case.

No images, tracker execution, model weights, downloads or cache rewrites.
The pinned archive is the previously acquired official MOT17Labels.zip.
This establishes cache correspondence, not independent visual label correctness.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np

SEQUENCE = "MOT17-04-FRCNN"
ARCHIVE_SHA256 = "0aa79322e91583369f42f17c4d79a0b145380d8732487bba59272048dc82b2b9"
MAX_BYTES = 16 * 1024 * 1024
METADATA = dict(schema_version=1, name=SEQUENCE, detector="FRCNN", length=1050,
                width=1920, height=1080, frame_rate=30)
ARRAY_DTYPES = dict(det_frame="int32", det_xyxy="float32", det_score="float32",
                    gt_frame="int32", gt_id="int32", gt_xyxy="float32",
                    gt_class="int16", gt_conf="float32", gt_vis="float32")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_file(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "regular non-symlink input required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "input exceeds intake byte budget")
    return raw


def source_members(raw):
    require(hashlib.sha256(raw).hexdigest() == ARCHIVE_SHA256,
            "official annotation archive fingerprint mismatch")
    result = {}
    with ZipFile(io.BytesIO(raw)) as archive:
        for suffix in ("seqinfo.ini", "det/det.txt", "gt/gt.txt"):
            name = f"train/{SEQUENCE}/{suffix}"
            entries = [entry for entry in archive.infolist() if entry.filename == name]
            require(len(entries) == 1, "missing or duplicate annotation member")
            require(entries[0].file_size <= MAX_BYTES, "annotation member exceeds budget")
            result[suffix] = archive.read(entries[0])
    return result


def reference_arrays(members):
    parser = configparser.ConfigParser()
    parser.read_string(members["seqinfo.ini"].decode("utf-8"))
    info = parser["Sequence"]
    for key, value in dict(name=SEQUENCE, seqLength="1050", imWidth="1920",
                           imHeight="1080", frameRate="30").items():
        require(info[key] == value, f"source metadata mismatch: {key}")
    det = np.loadtxt(io.BytesIO(members["det/det.txt"]), delimiter=",", ndmin=2)
    gt = np.loadtxt(io.BytesIO(members["gt/gt.txt"]), delimiter=",", ndmin=2)
    # This pinned labels archive has seven-column FRCNN detections, not the
    # optional trailing x/y/z columns described in the general MOT format.
    for rows, columns in ((det, 7), (gt, 9)):
        require(rows.ndim == 2 and rows.shape[1] == columns and len(rows) > 0,
                "unexpected annotation columns or empty source")
        require(bool(np.isfinite(rows).all()), "non-finite source annotation")
        require(bool(((rows[:, 0] >= 1) & (rows[:, 0] <= 1050)
                      & (rows[:, 0] == np.floor(rows[:, 0]))).all()), "invalid source frame")
        require(bool((rows[:, 4:6] > 0).all()), "non-positive source box dimensions")
    require(bool(((det[:, 6] >= 0) & (det[:, 6] <= 1)).all()),
            "FRCNN source scores require unexpected normalization")
    require(bool(((gt[:, 1] > 0) & (gt[:, 1] == np.floor(gt[:, 1]))).all()),
            "invalid source GT identity")
    require(len(np.unique(gt[:, :2], axis=0)) == len(gt), "duplicate source frame/GT id")
    require(bool(np.isin(gt[:, 6], [0, 1]).all()), "invalid source consider flag")
    require(bool(((gt[:, 8] >= 0) & (gt[:, 8] <= 1)).all()), "invalid visibility")

    def xyxy(rows):
        boxes = rows[:, 2:6].copy()
        boxes[:, 2:] += boxes[:, :2]
        return boxes

    # The existing cache writer streams frames in order and stores float32.
    det = det[np.argsort(det[:, 0], kind="stable")]
    gt = gt[np.argsort(gt[:, 0], kind="stable")]
    arrays = dict(det_frame=det[:, 0], det_xyxy=xyxy(det), det_score=det[:, 6],
                  gt_frame=gt[:, 0], gt_id=gt[:, 1], gt_xyxy=xyxy(gt),
                  gt_class=gt[:, 7], gt_conf=gt[:, 6], gt_vis=gt[:, 8])
    return {key: value.astype(ARRAY_DTYPES[key]) for key, value in arrays.items()}


def verify_cache(raw, expected):
    with ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len({entry.filename for entry in entries}) == len(entries),
                "duplicate cache member")
        require(sum(entry.file_size for entry in entries) <= MAX_BYTES,
                "expanded cache exceeds budget")
    with np.load(io.BytesIO(raw), allow_pickle=False) as cache:
        require(set(cache.files) == set(METADATA) | set(ARRAY_DTYPES),
                "unexpected cache keys (no appearance or image input allowed)")
        for key, value in METADATA.items():
            actual = cache[key]
            kinds = "U" if isinstance(value, str) else "iu"
            require(actual.shape == () and actual.dtype.kind in kinds and actual.item() == value,
                    f"cache metadata mismatch: {key}")
        for key, value in expected.items():
            actual = cache[key]
            require(actual.dtype == np.dtype(ARRAY_DTYPES[key]), f"cache dtype mismatch: {key}")
            require(np.array_equal(actual, value), f"cache/source mismatch: {key}")


def audit(cache_path, labels_path):
    labels_raw, cache_raw = raw_file(labels_path), raw_file(cache_path)
    members = source_members(labels_raw)
    expected = reference_arrays(members)
    verify_cache(cache_raw, expected)
    scoring = (expected["gt_class"] == 1) & (expected["gt_conf"] == 1)
    classes, counts = np.unique(expected["gt_class"], return_counts=True)
    return dict(
        schema="visiontrack.mot17-case-intake/v1", sequence=SEQUENCE,
        decision="admit_annotation_only_diagnostic", frame_range=[1, 1050],
        input_sha256=dict(cache=hashlib.sha256(cache_raw).hexdigest(),
                          labels_archive=hashlib.sha256(labels_raw).hexdigest()),
        member_sha256={key: hashlib.sha256(value).hexdigest()
                       for key, value in members.items()},
        metadata=METADATA,
        detections=len(expected["det_frame"]), ground_truth_rows=len(scoring),
        scoring_pedestrian_rows=int(scoring.sum()),
        non_scoring_rows=int((~scoring).sum()),
        scoring_pedestrian_ids=len(np.unique(expected["gt_id"][scoring])),
        class_rows={str(int(key)): int(value) for key, value in zip(classes, counts, strict=True)},
        correspondence="all nine cache arrays equal source conversion at stored precision",
        images_read=False, tracker_executed=False, independent_visual_review=False,
        untouched_validation=False, commercial_admission=False,
        reentry_or_flow_count_truth=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.cache, args.labels), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
