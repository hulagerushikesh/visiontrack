"""Independent MOT17 preprocessing check on sealed raw outputs, not tracking.

The reference dataset constructor is real; temporary empty files only satisfy
its inventory checks. Its text loader is NOT tested: lossless in-memory rows
are supplied at the source-verified cache precision. No images are accessed.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import (
    audit,
    raw_file,
    reference_arrays,
    require,
    source_members,
)
from experiments.mot17_metric_crosscheck import reference_api
from visiontrack.eval.mot17 import (
    LEGACY_MOT17_PREPROCESSING,
    MOT17_PREPROCESSING,
    preprocess_frame,
)


@contextmanager
def reference_dataset(te, count):
    """Use the actual constructor/default class map without downloading data."""
    with TemporaryDirectory(prefix="visiontrack-preproc-reference-") as folder:
        root = Path(folder)
        (root / "gt/audit/gt").mkdir(parents=True)
        (root / "gt/audit/gt/gt.txt").touch()
        (root / "trackers/saved/data").mkdir(parents=True)
        (root / "trackers/saved/data/audit.txt").touch()
        yield te.datasets.MotChallenge2DBox(dict(
            GT_FOLDER=str(root / "gt"), TRACKERS_FOLDER=str(root / "trackers"),
            TRACKERS_TO_EVAL=["saved"], SEQ_INFO={"audit": count},
            SKIP_SPLIT_FOL=True, PRINT_CONFIG=False, BENCHMARK="MOT17", DO_PREPROC=True))


def frame_arrays(row):
    gt = np.asarray(row["gt_xyxy"], dtype=float).reshape(-1, 4)
    tr = np.asarray(row["track_xyxy"], dtype=float).reshape(-1, 4)
    g, t = (np.asarray(row[key]) for key in ("gt_ids", "track_ids"))
    require(all(ids.ndim == 1 and (not len(ids) or ids.dtype.kind in "iu")
                for ids in (g, t)), "integer ID vectors required")
    g, t = g.astype(np.int64), t.astype(np.int64)
    classes, flags = (np.asarray(row[key]) for key in ("gt_classes", "gt_consider"))
    require(len(gt) == len(g) == len(classes) == len(flags), "GT alignment mismatch")
    require(len(tr) == len(t), "tracker alignment mismatch")
    require(len(set(g)) == len(g) and len(set(t)) == len(t), "duplicate frame ID")
    require(bool((g > 0).all() and (t > 0).all()), "positive IDs required")
    require(bool(np.isfinite(gt).all() and np.isfinite(tr).all()), "nonfinite geometry")
    require(bool(np.isin(flags, [0, 1]).all()), "binary consider flags required")
    return gt, g, classes, flags, tr, t


def reference_rows(rows, te, box_iou):
    """Run TrackEval's own ignore assignment; recover original ID lineage.

    Saved public outputs lack confidence. The unused confidence payload carries
    original IDs, allowing exact inversion of TrackEval's dense relabelling even
    for identical boxes. It is not detection confidence and never selects boxes.
    """
    require(bool(rows), "nonempty sequence required")
    require([r["source_frame"] for r in rows] == list(range(1, len(rows) + 1)),
            "contiguous raw frames required")
    fields = ("gt_ids", "gt_dets", "gt_classes", "gt_extras", "tracker_ids",
              "tracker_dets", "tracker_classes", "tracker_confidences", "similarity_scores")
    data = {key: [] for key in fields}
    original_gt = set()
    for row in rows:
        gt, g, classes, flags, tr, t = frame_arrays(row)
        original_gt.update(g[(classes == 1) & (flags != 0)].tolist())

        def xywh(boxes):
            result = boxes.copy()
            result[:, 2:] -= result[:, :2]
            return result

        values = (g, xywh(gt), classes, {"zero_marked": flags}, t, xywh(tr),
                  np.ones(len(t), dtype=int), t.copy(),
                  box_iou(gt, tr, box_format="x0y0x1y1"))
        for key, value in zip(fields, values, strict=True):
            data[key].append(value)
    data.update(num_timesteps=len(rows), seq="audit")
    with reference_dataset(te, len(rows)) as dataset:
        processed = dataset.get_preprocessed_seq_data(data, "pedestrian")
    gt_inverse = np.asarray(sorted(original_gt), dtype=np.int64)
    surviving = sorted({int(i) for ids in processed["tracker_confidences"] for i in ids})
    tracker_inverse = np.asarray(surviving, dtype=np.int64)
    result = []
    for i, row in enumerate(rows):
        gids = gt_inverse[processed["gt_ids"][i]]
        tids = tracker_inverse[processed["tracker_ids"][i]]
        require(np.array_equal(tids, processed["tracker_confidences"][i]),
                "reference ID lineage recovery failed")

        def original_boxes(ids, id_key, box_key, returned, row=row):
            positions = {identity: n for n, identity in enumerate(row[id_key])}
            boxes = np.asarray(row[box_key], dtype=float).reshape(-1, 4)
            selected = boxes[[positions[int(identity)] for identity in ids]].reshape(-1, 4)
            xywh = selected.copy()
            xywh[:, 2:] -= xywh[:, :2]
            require(np.array_equal(xywh, returned), "reference changed selected box geometry")
            # Recover the verified originals, not a potentially lossy XYWH -> XYXY roundtrip.
            return selected.tolist()

        result.append(dict(source_frame=row["source_frame"], gt_ids=gids.tolist(),
                           gt_xyxy=original_boxes(gids, "gt_ids", "gt_xyxy",
                                                  processed["gt_dets"][i]),
                           track_ids=tids.tolist(),
                           track_xyxy=original_boxes(tids, "track_ids", "track_xyxy",
                                                     processed["tracker_dets"][i])))
    return result


def local_row(raw, *, policy=MOT17_PREPROCESSING):
    pairs = preprocess_frame(*frame_arrays(raw), policy=policy)
    return dict(source_frame=raw["source_frame"], **dict(zip(
        ("gt_ids", "gt_xyxy", "track_ids", "track_xyxy"),
        (p.tolist() for p in pairs), strict=True)))


def compare(raw_rows, scored_rows, reference, *, policy=MOT17_PREPROCESSING):
    require(len(raw_rows) == len(scored_rows) == len(reference), "frame count mismatch")
    changes, count = [], dict(raw=0, saved=0, reference=0)
    for raw, saved, ref in zip(raw_rows, scored_rows, reference, strict=True):
        require(raw["source_frame"] == saved["source_frame"] == ref["source_frame"],
                "frame order mismatch")
        require(local_row(raw, policy=policy) == saved, "saved preprocessing not reproduced")
        require(saved["gt_ids"] == ref["gt_ids"] and saved["gt_xyxy"] == ref["gt_xyxy"],
                "scoring GT disagreement")
        for key, row in (("raw", raw), ("saved", saved), ("reference", ref)):
            count[key] += len(row["track_ids"])
        if saved != ref:
            old, new = set(saved["track_ids"]), set(ref["track_ids"])
            changes.append(dict(source_frame=raw["source_frame"],
                                saved_only_ids=sorted(old - new),
                                reference_only_ids=sorted(new - old),
                                saved_ids=saved["track_ids"], reference_ids=ref["track_ids"]))
    return dict(schema="visiontrack.mot17-preprocessing-audit/v1", frames=len(raw_rows),
                all_frames_agree=not changes, disagreement_frames=len(changes),
                prediction_counts=count, frame_changes=changes, preprocessing=policy,
                tracker_executed=False, images_read=False, independent_visual_review=False,
                reference_text_loader_tested=False, historical_records_rewritten=False)


def verify_source_rows(rows, arrays):
    for frame, row in enumerate(rows, start=1):
        require(row["source_frame"] == frame, "contiguous source frames required")
        selected = arrays["gt_frame"] == frame
        for key, field in (("gt_ids", "gt_id"), ("gt_xyxy", "gt_xyxy"),
                           ("gt_classes", "gt_class"), ("gt_consider", "gt_conf")):
            require(np.array_equal(np.asarray(row[key]), arrays[field][selected]),
                    f"raw/source GT mismatch: {key}, frame {frame}")


def execute(baseline, cache, labels, output, policy=MOT17_PREPROCESSING):
    require(not output.exists() and not output.is_symlink(), "new output required")
    contents = read_bundle(baseline)
    intake = audit(cache, labels)
    arrays = reference_arrays(source_members(raw_file(labels)))
    rows = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    require(len(rows) == 1050, "full pinned sequence required")
    verify_source_rows(rows, arrays)
    te, box_iou, aliases = reference_api()
    root = Path(__file__).resolve().parents[1]
    paths = [Path(__file__).resolve(), root / "src/visiontrack/eval/mot17.py",
             root / "src/visiontrack/core/geometry.py", root / "src/visiontrack/core/assignment.py",
             Path(cache), Path(labels)] + sorted(Path(te.__file__).parent.rglob("*.py"))
    hashes = {str(p): sha(p) for p in paths}

    def guard():
        require(read_bundle(baseline) == contents, "baseline changed")
        for name, digest in hashes.items():
            require(sha(Path(name)) == digest, f"input/source changed: {name}")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        schema="visiontrack.mot17-preprocessing-method/v1", source_sha256=hashes,
        baseline_manifest_sha256=BASELINE_MANIFEST, source_intake=intake,
        numpy_compatibility_aliases=aliases,
        environment=dict(python=sys.version, platform=platform.platform()),
        policy="compare all saved raw outputs; no tracker, tuning, pixels or source edits",
        preprocessing=policy,
        coordinate_policy="source verified float32 cache -> float64; no text roundtrip",
        reference_adapter="actual dataset constructor, full GT, class=1 predictions; original "
                          "track IDs carried in unused confidence field to invert dense IDs",
        acceptance="exact ordered IDs and boxes in every frame; any difference fails",
        discrepancy_policy="retain every difference; do not rewrite original baseline"))
    reference = reference_rows(rows, te, box_iou)
    saved = [json.loads(line) for line in contents["run-1/scored.jsonl"].splitlines()]
    result = compare(rows, saved, reference, policy=policy)
    with (output / "reference-scored.jsonl").open("x") as stream:
        for row in reference:
            stream.write(encoded(row))
    write_json(output / "summary.json", result)
    guard()
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded({k: v for k, v in result.items() if k != "frame_changes"}), flush=True)
    return result["all_frames_agree"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "cache", "labels", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--policy", choices=(MOT17_PREPROCESSING, LEGACY_MOT17_PREPROCESSING),
                        default=MOT17_PREPROCESSING)
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.baseline, args.cache, args.labels, args.output,
                                args.policy) else 2)


if __name__ == "__main__":
    main()
