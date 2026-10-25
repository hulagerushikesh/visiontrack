"""Check real MOT text loading -> preprocessing -> metrics on saved outputs.

Offline preview by default. No tracker, network, images, tuning or old rewrites.
The exported confidence is a constant placeholder: the saved boxes have no score.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import (
    SEQUENCE,
    audit,
    raw_file,
    reference_arrays,
    require,
    source_members,
)
from experiments.mot17_coverage_v2 import RESCORE_MANIFEST, read_packet
from experiments.mot17_metric_crosscheck import (
    CLEAR_FIELDS,
    HOTA_FIELDS,
    IDENTITY_FIELDS,
    comparison,
    reference_api,
)
from experiments.mot17_preprocessing_audit import frame_arrays, verify_source_rows
from visiontrack.eval.definitions import EVALUATOR
from visiontrack.eval.mot17 import MOT17_PREPROCESSING

REFERENCE_COMMIT = "12c8791b303e0a0b50f753af204249e622d0281a"


def method():
    return dict(
        schema="visiontrack.mot17-text-roundtrip/v1", sequence=SEQUENCE, frames=[1, 1050],
        baseline_manifest_sha256=BASELINE_MANIFEST, rescore_manifest_sha256=RESCORE_MANIFEST,
        evaluator=EVALUATOR, preprocessing=MOT17_PREPROCESSING,
        reference_commit=REFERENCE_COMMIT, integer_tolerance=0, float_tolerance=1e-10,
        coordinates="saved float64 XYXY -> XYWH, 17 significant decimal digits; no rounding",
        confidence="constant 1 placeholder, not the original detector or track confidence",
        acceptance="exact loaded raw IDs/XYWH and processed dense IDs/XYWH in every frame; "
                   "all 45 corrected saved metric checks agree at the fixed tolerances",
        scope="real reference text loader, original GT bytes, preprocessing and sequence metrics; "
              "not multi-sequence aggregation, visual label validation or improved tracking",
        tracker_executed=False, images_read=False, network_used=False,
        independent_visual_review=False, historical_records_rewritten=False)


def xywh(boxes):
    result = np.asarray(boxes, dtype=np.float64).reshape(-1, 4).copy()
    require(bool(np.isfinite(result).all()), "finite boxes required")
    result[:, 2:] -= result[:, :2]
    require(bool((result[:, 2:] > 0).all()), "positive-area boxes required")
    return result


def tracker_text(rows):
    require(bool(rows) and [r["source_frame"] for r in rows] == list(range(1, len(rows) + 1)),
            "complete ordered frames required")
    lines = []
    for row in rows:
        *_, boxes, ids = frame_arrays(row)
        for identity, box in zip(ids, xywh(boxes), strict=True):
            # Standard ten-column MOT result. -1 placeholders are not class labels.
            lines.append(
                f'{row["source_frame"]},{identity},' +
                ",".join(format(float(v), ".17g") for v in box) + ",1,-1,-1,-1\n")
    return "".join(lines).encode("ascii")


def dataset(te, root, length):
    return te.datasets.MotChallenge2DBox(dict(
        GT_FOLDER=str(root / "gt"), TRACKERS_FOLDER=str(root / "trackers"),
        TRACKERS_TO_EVAL=["saved"], SEQ_INFO={SEQUENCE: length},
        SKIP_SPLIT_FOL=True, PRINT_CONFIG=False, BENCHMARK="MOT17", DO_PREPROC=True))


def verify_loaded(rows, loaded):
    require(loaded["num_timesteps"] == len(rows), "loaded frame count mismatch")
    for i, row in enumerate(rows):
        for side, ids, boxes in (("gt", "gt_ids", "gt_xyxy"),
                                 ("tracker", "track_ids", "track_xyxy")):
            require(np.array_equal(loaded[f"{side}_ids"][i], row[ids]) and
                    np.array_equal(loaded[f"{side}_dets"][i], xywh(row[boxes])),
                    f"text loader changed {side} IDs/geometry at frame {i + 1}")
        require(np.array_equal(loaded["gt_classes"][i], row["gt_classes"]) and
                np.array_equal(loaded["gt_extras"][i]["zero_marked"], row["gt_consider"]),
                f"text loader changed GT policy fields at frame {i + 1}")
        require(bool((loaded["tracker_confidences"][i] == 1).all()),
                "constant placeholder confidence changed")


def verify_processed(rows, processed):
    require(processed["num_timesteps"] == len(rows), "processed frame count mismatch")
    for side, ids, boxes in (("gt", "gt_ids", "gt_xyxy"),
                             ("tracker", "track_ids", "track_xyxy")):
        mapping = {identity: n for n, identity in enumerate(sorted(
            {identity for row in rows for identity in row[ids]}))}
        require(processed[f"num_{side}_ids"] == len(mapping) and
                processed[f"num_{side}_dets"] == sum(len(r[ids]) for r in rows),
                f"processed {side} inventory mismatch")
        for i, row in enumerate(rows):
            expected = [mapping[identity] for identity in row[ids]]
            require(np.array_equal(processed[f"{side}_ids"][i], expected) and
                    np.array_equal(processed[f"{side}_dets"][i], xywh(row[boxes])),
                    f"processed {side} correspondence changed at frame {i + 1}")


def metric_checks(saved, data, te):
    clear = te.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    identity = te.metrics.Identity(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    hota = te.metrics.HOTA().eval_sequence(data)
    checks = {}
    for group, fields, result in (("clear", CLEAR_FIELDS, clear),
                                   ("identity", IDENTITY_FIELDS, identity)):
        checks[group] = {name: comparison(saved[group][key], result[name])
                         for name, key in fields.items()}
    checks["hota"] = {name: comparison(saved["hota"][key], float(np.mean(hota[name])))
                      for name, key in HOTA_FIELDS.items()}
    require(len(saved["hota"]["per_alpha"]) == len(hota["HOTA"]) == 19,
            "HOTA alpha count mismatch")
    checks["hota_per_alpha"] = [comparison(o, r) for o, r in
                                zip(saved["hota"]["per_alpha"], hota["HOTA"], strict=True)]
    flat = [c for group in ("clear", "identity", "hota") for c in checks[group].values()]
    flat += checks["hota_per_alpha"]
    return dict(checks=checks, num_checks=len(flat),
                all_checks_agree=all(c["agrees"] for c in flat))


def execute(baseline, rescore, cache, labels, output):
    root = Path(__file__).resolve().parents[1]
    require(not output.exists() and not output.is_symlink(), "new output required")
    require(output.parent.is_dir() and not output.resolve().is_relative_to(root),
            "existing external output parent required")
    require(all(not output.resolve().is_relative_to(p.resolve()) for p in (baseline, rescore)),
            "output must not be inside sealed evidence")
    before = read_bundle(baseline)
    corrected = read_packet(rescore, RESCORE_MANIFEST)
    intake = audit(cache, labels)
    members = source_members(raw_file(labels))
    rows = [json.loads(line) for line in before["run-1/raw.jsonl"].splitlines()]
    scored = [json.loads(line) for line in before["run-1/scored.jsonl"].splitlines()]
    require(len(rows) == len(scored) == 1050 and
            [r["source_frame"] for r in scored] == list(range(1, 1051)),
            "complete saved raw/scored sequence required")
    verify_source_rows(rows, reference_arrays(members))
    text = tracker_text(rows)
    te, _, aliases = reference_api()
    distribution = importlib.metadata.distribution("trackeval")
    origin = json.loads(distribution.read_text("direct_url.json") or "null")
    require(isinstance(origin, dict) and
            origin.get("vcs_info", {}).get("commit_id") == REFERENCE_COMMIT,
            "pinned TrackEval installation required")
    paths = [Path(cache), Path(labels)] + sorted(Path(te.__file__).parent.rglob("*.py"))
    paths += sorted((root / "src/visiontrack/eval").glob("*.py"))
    paths += [root / "experiments" / name for name in (
        "mot17_text_roundtrip.py", "mot17_case_baseline.py", "mot17_case_coverage.py",
        "mot17_case_intake.py", "mot17_coverage_v2.py", "mot17_preprocessing_audit.py",
        "mot17_metric_crosscheck.py")]
    hashes = {str(p): sha(p) for p in paths}

    def guard():
        require(read_bundle(baseline) == before and
                read_packet(rescore, RESCORE_MANIFEST) == corrected, "sealed evidence changed")
        for name, digest in hashes.items():
            require(sha(Path(name)) == digest, f"input/implementation changed: {name}")

    guard()
    output.mkdir()
    write_json(output / "method.json", dict(
        **method(), source_intake=intake, source_sha256=hashes,
        reference_origin=origin, reference_version=distribution.version,
        numpy_compatibility_aliases=aliases,
        environment=dict(python=sys.version, numpy=np.__version__, platform=platform.platform(),
                         scipy=importlib.metadata.version("scipy"))))
    try:
        # Retain exactly the files actually read. No directory scan or image access.
        gt = output / "gt" / SEQUENCE / "gt" / "gt.txt"
        predictions = output / "trackers/saved/data" / f"{SEQUENCE}.txt"
        gt.parent.mkdir(parents=True)
        predictions.parent.mkdir(parents=True)
        gt.write_bytes(members["gt/gt.txt"])
        predictions.write_bytes(text)
        (gt.parent.parent / "seqinfo.ini").write_bytes(members["seqinfo.ini"])
        exports = {p: sha(p) for p in (gt, predictions, gt.parent.parent / "seqinfo.ini")}
        reference = dataset(te, output, len(rows))
        loaded = reference.get_raw_seq_data("saved", SEQUENCE)
        verify_loaded(rows, loaded)
        processed = reference.get_preprocessed_seq_data(loaded, "pedestrian")
        verify_processed(scored, processed)
        saved = json.loads(corrected["score.json"])["unrounded"]
        result = dict(**metric_checks(saved, processed, te),
                      raw_boxes=sum(len(r["track_ids"]) for r in rows),
                      scored_boxes=processed["num_tracker_dets"],
                      gt_boxes=processed["num_gt_dets"], frames=len(rows),
                      loaded_raw_exact=True, processed_correspondence_exact=True,
                      reference_text_loader_tested=True, tracker_executed=False,
                      independent_visual_review=False, improvement_tested=False)
        write_json(output / "summary.json", result)
        guard()
        require(all(sha(p) == digest for p, digest in exports.items()), "text inputs changed")
    except Exception as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    write_json(output / "manifest.json", {
        p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.rglob("*")) if p.is_file()})
    print(encoded({k: v for k, v in result.items() if k != "checks"}), flush=True)
    return result["all_checks_agree"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "rescore", "cache", "labels", "output"):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(encoded(method()))
        return
    values = [getattr(args, name) for name in ("baseline", "rescore", "cache", "labels", "output")]
    require(all(value is not None for value in values), "explicit inputs and new output required")
    raise SystemExit(0 if execute(*values) else 2)


if __name__ == "__main__":
    main()
