"""Independent metric implementation check on the pinned saved scored pairs.

Does NOT validate MOT17 preprocessing, run a tracker, change the baseline or
turn a discrepancy into a silently relaxed tolerance. TrackEval is optional.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import require

FLOAT_TOLERANCE = 1e-10
CLEAR_FIELDS = dict(CLR_TP="true_positives", CLR_FN="false_negatives",
                    CLR_FP="false_positives", IDSW="id_switches", Frag="fragmentations",
                    MT="mostly_tracked", PT="partially_tracked", ML="mostly_lost",
                    CLR_Frames="num_frames", MOTA="mota", MOTP="motp",
                    CLR_Pr="precision", CLR_Re="recall")
IDENTITY_FIELDS = dict(IDTP="idtp", IDFP="idfp", IDFN="idfn", IDF1="idf1", IDP="idp", IDR="idr")
HOTA_FIELDS = dict(HOTA="hota", DetA="det_a", AssA="ass_a", DetRe="det_re",
                   DetPr="det_pr", AssRe="ass_re", AssPr="ass_pr")


def reference_api():
    # Compatibility aliases for this isolated dev-only process, as in the
    # existing reference tests. No changes to the installed reference sources.
    restored = []
    for name, builtin in (("float", float), ("int", int), ("bool", bool)):
        if not hasattr(np, name):
            setattr(np, name, builtin)
            restored.append(name)
    import trackeval
    from trackeval.datasets._base_dataset import _BaseDataset
    return trackeval, _BaseDataset._calculate_box_ious, restored


def data_for_reference(rows, box_iou):
    require([r["source_frame"] for r in rows] == list(range(1, len(rows) + 1)),
            "contiguous scored frames required")
    gt_map = {g: i for i, g in enumerate(sorted({g for r in rows for g in r["gt_ids"]}))}
    tr_map = {t: i for i, t in enumerate(sorted({t for r in rows for t in r["track_ids"]}))}
    gt_ids, tracker_ids, similarity = [], [], []
    for row in rows:
        g, t = row["gt_ids"], row["track_ids"]
        require(len(set(g)) == len(g) and len(set(t)) == len(t), "duplicate frame IDs")
        gb, tb = (np.asarray(row[key], dtype=float).reshape(-1, 4)
                  for key in ("gt_xyxy", "track_xyxy"))
        require(len(gb) == len(g) and len(tb) == len(t), "IDs/boxes disagree")
        require(bool(np.isfinite(gb).all()) and bool(np.isfinite(tb).all()), "nonfinite boxes")
        gt_ids.append(np.array([gt_map[x] for x in g], dtype=int))
        tracker_ids.append(np.array([tr_map[x] for x in t], dtype=int))
        # Independent reference geometry, not visiontrack.core.geometry.
        similarity.append(box_iou(gb, tb, box_format="x0y0x1y1"))
    return dict(num_gt_ids=len(gt_map), num_tracker_ids=len(tr_map),
                num_gt_dets=sum(len(g) for g in gt_ids),
                num_tracker_dets=sum(len(t) for t in tracker_ids), num_timesteps=len(rows),
                gt_ids=gt_ids, tracker_ids=tracker_ids, similarity_scores=similarity)


def comparison(ours, reference):
    integer = type(ours) is int
    delta = float(reference) - ours
    return dict(baseline=ours, reference=float(reference), reference_minus_baseline=delta,
                tolerance=0 if integer else FLOAT_TOLERANCE,
                agrees=abs(delta) <= (0 if integer else FLOAT_TOLERANCE))


def crosscheck(contents, te, box_iou):
    saved = json.loads(contents["run-1/summary.json"])["unrounded"]
    rows = [json.loads(line) for line in contents["run-1/scored.jsonl"].splitlines()]
    data = data_for_reference(rows, box_iou)
    clear = te.metrics.CLEAR(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    identity = te.metrics.Identity(dict(THRESHOLD=0.5, PRINT_CONFIG=False)).eval_sequence(data)
    hota = te.metrics.HOTA().eval_sequence(data)
    checks = {}
    for group, fields, reference in (("clear", CLEAR_FIELDS, clear),
                                      ("identity", IDENTITY_FIELDS, identity)):
        checks[group] = {name: comparison(saved[group][key], reference[name])
                         for name, key in fields.items()}
    checks["hota"] = {name: comparison(saved["hota"][key], float(np.mean(hota[name])))
                      for name, key in HOTA_FIELDS.items()}
    require(len(saved["hota"]["per_alpha"]) == len(hota["HOTA"]) == 19, "HOTA alpha mismatch")
    checks["hota_per_alpha"] = [comparison(o, r) for o, r in
                                zip(saved["hota"]["per_alpha"], hota["HOTA"], strict=True)]
    all_checks = [v for group in ("clear", "identity", "hota") for v in checks[group].values()]
    all_checks += checks["hota_per_alpha"]
    return dict(
        schema="visiontrack.mot17-saved-metric-crosscheck/v1", checks=checks,
        all_reported_checks_agree=all(c["agrees"] for c in all_checks),
        num_checks=len(all_checks), frames=data["num_timesteps"], gt_boxes=data["num_gt_dets"],
        scored_public_boxes=data["num_tracker_dets"], reference_gt_ids=data["num_gt_ids"],
        tracker_executed=False, independent_metric_implementation=True,
        independent_preprocessing=False, images_read=False, improvement_tested=False,
        reference_full_results=json.loads(json.dumps(
            dict(CLEAR=clear, Identity=identity, HOTA=hota),
            default=lambda x: x.tolist() if isinstance(x, np.ndarray) else x.item())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), "new output required")
    contents = read_bundle(args.baseline)
    te, box_iou, restored = reference_api()
    te_root = Path(te.__file__).resolve().parent
    hashes = {str(p): sha(p) for p in sorted(te_root.rglob("*.py"))}
    source = Path(__file__).resolve()
    hashes[str(source)] = sha(source)
    args.output.mkdir()
    distribution = importlib.metadata.distribution("trackeval")
    write_json(args.output / "method.json", dict(
        baseline_manifest_sha256=BASELINE_MANIFEST, source_sha256=hashes,
        reference_version=distribution.version,
        reference_install_origin=json.loads(distribution.read_text("direct_url.json") or "null"),
        environment=dict(python=sys.version, numpy=np.__version__, platform=platform.platform(),
                         scipy=importlib.metadata.version("scipy")),
        numpy_compatibility_aliases=restored,
        fixed_tolerance=dict(integer_counts=0, floats=FLOAT_TOLERANCE),
        scope="post-baseline metric check on unchanged scored pairs; not official preprocessing",
        inputs="one-based saved IDs densely relabelled; TrackEval computes its own box IoUs",
        discrepancy_policy="retain every comparison; no tolerance relaxation or baseline rewrite"))
    result = crosscheck(contents, te, box_iou)
    require(read_bundle(args.baseline) == contents, "baseline changed during crosscheck")
    for path, digest in hashes.items():
        require(sha(Path(path)) == digest, "reference/extractor implementation changed")
    write_json(args.output / "summary.json", result)
    write_json(args.output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(args.output.iterdir()) if p.is_file()})
    display = {k: v for k, v in result.items() if k != "reference_full_results"}
    print(json.dumps(display), flush=True)


if __name__ == "__main__":
    main()
