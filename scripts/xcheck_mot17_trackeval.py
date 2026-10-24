#!/usr/bin/env python3
"""End-to-end cross-check of our MOT17 evaluation against `trackeval`.

Validates the *whole* pipeline on a real sequence — MOT17 preprocessing
(distractor / zero-marked handling) **and** the HOTA/IDF1/CLEAR math — by
comparing our numbers to trackeval's own MOT17 evaluator on identical raw
tracker output. The metric math is separately unit-tested against trackeval in
``tests/test_hota_vs_trackeval.py``; this adds the preprocessing + real-scale
confirmation the metric tests can't.

Prerequisites::

    pip install "git+https://github.com/JonathonLuiten/TrackEval.git"
    python data/cache/precompute.py --data-root <MOT17> --detector FRCNN --out data/cache/mot17

Run::

    python scripts/xcheck_mot17_trackeval.py --seq MOT17-09-FRCNN --data-root ~/Downloads/MOT17

No expected PASS is assumed: check preprocessing separately from metric math.
Integer counts must agree exactly, unrounded floats within 1e-10. Retain any
discrepancy; do not dismiss an algorithm difference as Hungarian tie-breaking.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "src"))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", default="MOT17-09-FRCNN", help="sequence name")
    parser.add_argument("--data-root", default="~/Downloads/MOT17", help="MOT17 root")
    parser.add_argument("--cache-dir", default="data/cache/mot17")
    parser.add_argument("--tol", type=float, default=1e-10, help="float tolerance, at most 1e-10")
    args = parser.parse_args(argv)
    if not np.isfinite(args.tol) or not 0 < args.tol <= 1e-10:
        parser.error("--tol must be finite, positive and no greater than 1e-10")

    # trackeval predates NumPy 2.0 and references the removed builtin aliases.
    for name, py in (("float", float), ("int", int), ("bool", bool)):
        if not hasattr(np, name):
            setattr(np, name, py)

    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.eval.hota import compute_hota, compute_identity
    from visiontrack.eval.mot import MotAccumulator
    from visiontrack.eval.mot17 import preprocess_frame
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    seq_name = args.seq
    npz = Path(args.cache_dir) / f"{seq_name}.npz"
    if not npz.exists():
        print(f"cache missing: {npz} — run data/cache/precompute.py first")
        return 1
    cache = CachedSequence(npz)
    length = len(cache)

    # Run our tracker on the full sequence, capturing RAW output (no preproc).
    tracker = ByteTracker(TrackerConfig())
    lines, frames = [], []
    for fd in cache.iter_range(1, length):
        observations = tracker.update(fd.detections())
        for o in observations:
            x1, y1, x2, y2 = o.xyxy
            lines.append(
                f"{fd.frame},{o.track_id},{x1:.17g},{y1:.17g},"
                f"{x2 - x1:.17g},{y2 - y1:.17g},{o.score:.17g},-1,-1,-1"
            )
        frames.append(preprocess_frame(
            fd.gt_xyxy, fd.gt_ids, fd.gt_classes, fd.gt_conf,
            np.array([o.xyxy for o in observations]).reshape(-1, 4),
            np.array([o.track_id for o in observations], dtype=np.int64)))
    accumulator = MotAccumulator()
    for frame in frames:
        accumulator.update(*frame)
    clear = accumulator.result()
    identity, hota = compute_identity(frames), compute_hota(frames)
    ours = dict(MOTA=clear.mota, MOTP=clear.motp, IDF1=identity.idf1,
                HOTA=hota.hota, DetA=hota.det_a, AssA=hota.ass_a,
                TP=clear.true_positives, FP=clear.false_positives,
                FN=clear.false_negatives, IDSW=clear.id_switches, Frag=clear.fragmentations)

    # trackeval on the identical raw output, using its own MOT17 preprocessing.
    import trackeval

    tmp = Path(tempfile.mkdtemp())
    tdir = tmp / "trackers" / "ours" / "data"
    tdir.mkdir(parents=True)
    (tdir / f"{seq_name}.txt").write_text("\n".join(lines) + "\n")
    gt_root = str(Path(args.data_root).expanduser() / "train")

    eval_config = {
        "USE_PARALLEL": False, "NUM_PARALLEL_CORES": 1, "PRINT_RESULTS": False,
        "PRINT_CONFIG": False, "TIME_PROGRESS": False, "OUTPUT_SUMMARY": False,
        "OUTPUT_DETAILED": False, "PLOT_CURVES": False,
    }
    ds_config = {
        "GT_FOLDER": gt_root, "TRACKERS_FOLDER": str(tmp / "trackers"),
        "BENCHMARK": "MOT17", "SPLIT_TO_EVAL": "train", "DO_PREPROC": True,
        "TRACKERS_TO_EVAL": ["ours"], "CLASSES_TO_EVAL": ["pedestrian"],
        "SEQ_INFO": {seq_name: length}, "SKIP_SPLIT_FOL": True,
        "GT_LOC_FORMAT": "{gt_folder}/{seq}/gt/gt.txt",
    }
    evaluator = trackeval.Evaluator(eval_config)
    dataset = trackeval.datasets.MotChallenge2DBox(ds_config)
    metrics = [trackeval.metrics.HOTA(), trackeval.metrics.Identity(), trackeval.metrics.CLEAR()]
    out = evaluator.evaluate([dataset], metrics)[0]
    res = out["MotChallenge2DBox"]["ours"][seq_name]["pedestrian"]
    te = {
        "MOTA": float(res["CLEAR"]["MOTA"]),
        "IDF1": float(res["Identity"]["IDF1"]),
        "HOTA": float(np.mean(res["HOTA"]["HOTA"])),
        "DetA": float(np.mean(res["HOTA"]["DetA"])),
        "AssA": float(np.mean(res["HOTA"]["AssA"])),
        "MOTP": float(res["CLEAR"]["MOTP"]),
        **{key: int(res["CLEAR"][reference]) for key, reference in dict(
            TP="CLR_TP", FP="CLR_FP", FN="CLR_FN", IDSW="IDSW", Frag="Frag").items()},
    }

    keys = tuple(ours)
    print(f"cross-check on {seq_name} ({length} frames)\n")
    print(f"{'':10} " + " ".join(f"{k:>8}" for k in keys))
    print(f"{'OURS':10} " + " ".join(f"{ours[k]:>8.4f}" for k in keys))
    print(f"{'TRACKEVAL':10} " + " ".join(f"{te[k]:>8.4f}" for k in keys))
    print(f"{'DELTA':10} " + " ".join(f"{ours[k] - te[k]:>+8.4f}" for k in keys))

    ok = all(abs(ours[key] - te[key]) <= (0 if isinstance(ours[key], int) else args.tol)
             for key in keys)
    print("\n" + ("PASS" if ok else "FAIL") + f"  (counts exact, floats within {args.tol})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
