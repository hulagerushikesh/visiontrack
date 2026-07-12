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

Expected: MOTA and IDF1 match exactly; HOTA agrees within ~2e-3 (Hungarian
tie-breaking across HOTA's 19 localisation thresholds accounts for the rest).
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
    parser.add_argument("--tol", type=float, default=3e-3, help="HOTA agreement tolerance")
    args = parser.parse_args(argv)

    # trackeval predates NumPy 2.0 and references the removed builtin aliases.
    for name, py in (("float", float), ("int", int), ("bool", bool)):
        if not hasattr(np, name):
            setattr(np, name, py)

    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.datasets.splits import Split
    from visiontrack.eval.mot17 import evaluate_sequences
    from visiontrack.tracking.config import TrackerConfig
    from visiontrack.tracking.tracker import ByteTracker

    seq_name = args.seq
    npz = Path(args.cache_dir) / f"{seq_name}.npz"
    if not npz.exists():
        print(f"cache missing: {npz} — run data/cache/precompute.py first")
        return 1
    cache = CachedSequence(npz)
    length = len(cache)
    video = seq_name.rsplit("-", 1)[0]  # MOT17-09-FRCNN -> MOT17-09

    # Run our tracker on the full sequence, capturing RAW output (no preproc).
    tracker = ByteTracker(TrackerConfig())
    lines = []
    for fd in cache.iter_range(1, length):
        for o in tracker.update(fd.detections()):
            x1, y1, x2, y2 = o.xyxy
            lines.append(
                f"{fd.frame},{o.track_id},{x1:.2f},{y1:.2f},"
                f"{x2 - x1:.2f},{y2 - y1:.2f},{o.score:.3f},-1,-1,-1"
            )

    # Our pipeline (preprocessing + all metrics) over the full sequence.
    entry = {"length": length, "train": [1, length // 2], "val": [1, length]}
    split = Split("xcheck", "full", {video: entry})
    ours, _ = evaluate_sequences([cache], TrackerConfig(), split, subset="all", per_sequence=False)

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
    }

    keys = ("MOTA", "IDF1", "HOTA", "DetA", "AssA")
    print(f"cross-check on {seq_name} ({length} frames)\n")
    print(f"{'':10} " + " ".join(f"{k:>8}" for k in keys))
    print(f"{'OURS':10} " + " ".join(f"{ours[k]:>8.4f}" for k in keys))
    print(f"{'TRACKEVAL':10} " + " ".join(f"{te[k]:>8.4f}" for k in keys))
    print(f"{'DELTA':10} " + " ".join(f"{ours[k] - te[k]:>+8.4f}" for k in keys))

    ok = (
        abs(ours["MOTA"] - te["MOTA"]) < 1e-3
        and abs(ours["IDF1"] - te["IDF1"]) < 1e-3
        and abs(ours["HOTA"] - te["HOTA"]) < args.tol
    )
    print("\n" + ("PASS" if ok else "FAIL") + f"  (MOTA/IDF1 exact, HOTA within {args.tol})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
