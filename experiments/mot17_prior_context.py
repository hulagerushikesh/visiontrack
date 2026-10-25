"""Read saved frames 1--35 before the fixed image window; no new pixels/replay.

Exploratory geometry is not evaluator correspondence or physical identity.
Neither an independent review nor a further image acquisition is authorized.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from experiments.mot17_case_baseline import encoded, sha, write_json
from experiments.mot17_case_coverage import BASELINE_MANIFEST, read_bundle
from experiments.mot17_case_intake import require
from visiontrack.eval.geometry import metric_iou

WINDOW = (1, 35)
REFERENCES = (85, 89)


def method():
    return dict(
        schema="visiontrack.mot17-prior-context/v1", source_window=list(WINDOW),
        baseline_manifest_sha256=BASELINE_MANIFEST, track_id=19,
        reference_ids=list(REFERENCES), iou_threshold=0.5,
        question="What saved geometric support precedes the already reviewed 36--57 window?",
        rule="Inspect every prior frame, including missing references/output; classify all "
             "present scored-reference overlaps >=0.5, not a maximum-IoU winner. "
             "Compress only consecutive identical support states; keep every numeric row.",
        limits="Exploratory, not prospectively untouched validation, evaluator assignment, "
               "physical identity, a causal finding, or permission to obtain further images.",
        tracker_or_label_changes=False, independent_review_completed=False,
        new_image_acquisition=False)


def box(value):
    array = np.asarray(value, dtype=np.float64)
    require(array.shape == (4,) and bool(np.isfinite(array).all()) and
            bool((array[2:] > array[:2]).all()), "finite positive-area box required")
    return array


def analyze(contents):
    saved = [json.loads(line) for line in contents["run-1/raw.jsonl"].splitlines()]
    require([r["source_frame"] for r in saved] == list(range(1, 1051)),
            "complete ordered saved sequence required")
    rows = []
    for raw in saved[:WINDOW[1]]:
        require(len(raw["track_ids"]) == len(raw["track_xyxy"]) and
                len(set(raw["track_ids"])) == len(raw["track_ids"]),
                "aligned unique public tracks required")
        require(len(set(raw["gt_ids"])) == len(raw["gt_ids"]) and
                all(len(raw[k]) == len(raw["gt_ids"]) for k in (
                    "gt_xyxy", "gt_classes", "gt_consider", "gt_visibility")),
                "aligned unique references required")
        public = 19 in raw["track_ids"]
        track = box(raw["track_xyxy"][raw["track_ids"].index(19)]) if public else None
        references = []
        for identity in REFERENCES:
            present = identity in raw["gt_ids"]
            reference, visibility, overlap = None, None, None
            if present:
                index = raw["gt_ids"].index(identity)
                require(raw["gt_classes"][index] == 1 and raw["gt_consider"][index] == 1,
                        "target must be a scored pedestrian reference")
                reference = box(raw["gt_xyxy"][index])
                visibility = float(raw["gt_visibility"][index])
                require(np.isfinite(visibility) and 0 <= visibility <= 1,
                        "finite reference visibility in [0,1] required")
                if public:
                    overlap = float(metric_iou([track], [reference])[0, 0])
            references.append(dict(id=identity, present=present,
                                   box=reference.tolist() if present else None,
                                   visibility=visibility, track_iou=overlap))
        support = [r["id"] for r in references
                   if r["track_iou"] is not None and r["track_iou"] >= 0.5]
        # Missing != zero overlap. Preserve the presence mask in each state.
        state = ("no_public_19" if not public else
                 "+".join(map(str, support)) if support else "no_supported_reference")
        presence = [r["id"] for r in references if r["present"]]
        pair_iou = (float(metric_iou([references[0]["box"]], [references[1]["box"]])[0, 0])
                    if len(presence) == 2 else None)
        rows.append(dict(source_frame=raw["source_frame"], public_19=public,
                         track_box=track.tolist() if public else None, references=references,
                         supported_reference_ids=support, state=state,
                         present_reference_ids=presence, reference_pair_iou=pair_iou))
    runs = []
    for row in rows:
        key = (row["state"], row["present_reference_ids"])
        if runs and (runs[-1]["state"], runs[-1]["present_reference_ids"]) == key:
            runs[-1]["last_frame"] = row["source_frame"]
        else:
            runs.append(dict(first_frame=row["source_frame"], last_frame=row["source_frame"],
                             state=key[0], present_reference_ids=key[1]))
    summary = dict(
        source_window=list(WINDOW), frames=len(rows),
        first_public_19=next((r["source_frame"] for r in rows if r["public_19"]), None),
        state_counts=dict(Counter(r["state"] for r in rows)), runs=runs,
        physical_identity_established=False, independent_review_completed=False,
        new_image_acquisition=False, intervention_justified=False)
    return rows, summary


def execute(baseline, output):
    root = Path(__file__).resolve().parents[1]
    require(not output.exists() and not output.is_symlink(), "new output required")
    require(output.parent.is_dir() and not output.resolve().is_relative_to(root),
            "existing external output parent required")
    before = read_bundle(baseline)
    implementation = sha(Path(__file__))
    geometry_file = root / "src/visiontrack/eval/geometry.py"
    geometry_digest = sha(geometry_file)
    output.mkdir()
    write_json(output / "method.json", dict(**method(), source_sha256=implementation,
                                           geometry_sha256=geometry_digest))
    try:
        rows, summary = analyze(before)
        require(read_bundle(baseline) == before and sha(Path(__file__)) == implementation and
                sha(geometry_file) == geometry_digest, "analysis input or source changed")
        write_json(output / "frames.json", rows)
        write_json(output / "summary.json", summary)
    except Exception as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
    write_json(output / "manifest.json", {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(output.iterdir()) if p.is_file()})
    print(encoded(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(encoded(method()))
        return
    require(args.baseline is not None and args.output is not None,
            "explicit baseline and new external output required")
    execute(args.baseline, args.output)


if __name__ == "__main__":
    main()
