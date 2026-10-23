"""Post-study development-only symptom diagnosis from saved records, not replay.

No tracker, generator, scorer or held-out inputs are loaded. Missing public
output is not proof of association rejection; below-threshold output is not
proof of a detector hallucination. Internal gate distances were not retained.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from experiments.box_gate_audit import audit as development_audit
from experiments.box_gate_combined_audit import (
    Evidence,
    canonical,
    check,
    grid,
    same,
    sha,
    write_output,
)

PHASES = ("outside_pulse_windows", "bottom_pulse_window", "top_pulse_window")
MISS_TYPES = ("no_public_output", "all_public_boxes_below_iou", "eligible_box_unmatched")
COUNTS = ("reference_object_frames", "misses", "id_switches", "false_positive_rows", *MISS_TYPES)


def phase(frame, parent):
    for edge in ("bottom", "top"):
        pulse = parent["observation_error"][edge + "_truncation"]
        if pulse["start_frame"] <= frame < pulse["stop_frame_exclusive"]:
            return edge + "_pulse_window"
    return "outside_pulse_windows"


def box(value):
    check(
        isinstance(value, list)
        and len(value) == 4
        and all(type(x) in (int, float) and math.isfinite(x) for x in value)
        and value[2] > value[0]
        and value[3] > value[1],
        "invalid diagnostic box",
    )
    return value


def iou(a, b):
    """Plain scalar pixel IoU; no new matching or truth-based output filtering."""
    a, b = box(a), box(b)
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    check(math.isfinite(union) and union > 0, "invalid diagnostic area")
    return intersection / union


def intervals(frames):
    """Inclusive consecutive ranges, retaining gaps rather than interpolating."""
    result = []
    for frame in sorted(frames):
        if result and frame == result[-1][1] + 1:
            result[-1][1] = frame
        else:
            result.append([frame, frame])
    return result


def diagnose_variant(variant, objects, parent):
    """Describe audited correspondence/output symptoms, not internal causes."""
    d = variant["scoring"]["diagnostics"]
    frames, threshold = parent["frame_grid"]["frames"], parent["diagnostics"]["gt_match_iou"]
    check(d["iou_threshold"] == threshold, "diagnostic IoU threshold differs")
    samples = d["samples"]
    same(
        [(s["frame"], s["object_id"]) for s in samples],
        [(f, identity) for f in range(frames) for identity in objects],
        "exact diagnostic sample grid",
    )
    rows = defaultdict(list)
    row_keys = set()
    for row in variant["output"]:
        f, identity = row["frame"], row["track_id"]
        check(type(f) is int and 0 <= f < frames, "invalid public frame")
        check(type(identity) is int and identity > 0, "invalid public track ID")
        check((f, identity) not in row_keys, "duplicate public row")
        box(row["xyxy"])
        row_keys.add((f, identity))
        rows[f].append(row)
    miss_events = {
        (e["frame_index"], e["gt_id"]): e for e in d["failures"] if e["event_type"] == "miss"
    }
    check(
        len(miss_events) == sum(e["event_type"] == "miss" for e in d["failures"]),
        "duplicate miss event",
    )
    missing = {(s["frame"], s["object_id"]) for s in samples if s["matched_track_id"] is None}
    check(set(miss_events) == missing, "miss events disagree with sample grid")
    counts = {p: dict.fromkeys(COUNTS, 0) for p in PHASES}
    details, matched_keys = [], set()
    for sample in samples:
        f, identity = sample["frame"], sample["object_id"]
        p = phase(f, parent)
        check(sample["phase"] == p, "recorded phase differs from fixed frame windows")
        counts[p]["reference_object_frames"] += 1
        counts[p]["id_switches"] += int(sample["id_switch"])
        track = sample["matched_track_id"]
        if track is not None:
            key = (f, track)
            check(key in row_keys and key not in matched_keys, "invalid saved correspondence")
            matched_keys.add(key)
            continue
        counts[p]["misses"] += 1
        public = rows[f]
        candidates = [
            (iou(miss_events[f, identity]["gt_box"], r["xyxy"]), r["track_id"]) for r in public
        ]
        best = min(candidates, key=lambda x: (-x[0], x[1])) if candidates else None
        category = (
            "no_public_output"
            if best is None
            else "all_public_boxes_below_iou"
            if best[0] < threshold
            else "eligible_box_unmatched"
        )
        counts[p][category] += 1
        details.append(
            dict(
                frame=f,
                object_id=identity,
                phase=p,
                category=category,
                public_row_count=len(public),
                max_public_box_iou=best[0] if best else None,
                best_overlap_track_id=best[1] if best else None,
            )
        )
    for f, _ in row_keys - matched_keys:
        counts[phase(f, parent)]["false_positive_rows"] += 1
    endpoints = variant["scoring"]["endpoints"]
    for key, endpoint in (
        ("misses", "missed_object_frames"),
        ("id_switches", "id_switches"),
        ("false_positive_rows", "false_positive_rows"),
    ):
        check(
            sum(p[key] for p in counts.values()) == endpoints["tracking." + endpoint],
            "symptom count disagrees with audited endpoint",
        )
    return dict(
        by_phase=counts,
        missed_reference_frames=details,
        objects=[
            dict(
                object_id=identity,
                matched_track_ids=sorted(
                    {
                        s["matched_track_id"]
                        for s in samples
                        if s["object_id"] == identity and s["matched_track_id"] is not None
                    }
                ),
                miss_frame_ranges_inclusive=intervals(
                    [
                        s["frame"]
                        for s in samples
                        if s["object_id"] == identity and s["matched_track_id"] is None
                    ]
                ),
                id_switch_frames=[
                    s["frame"] for s in samples if s["object_id"] == identity and s["id_switch"]
                ],
            )
            for identity in objects
        ],
        bottom_centre_crossing=variant["scoring"]["crossing"]["bottom_centre"],
    )


def common_localization(a, b):
    """Paired matched-only errors on identical reference frame/object keys."""
    lookup = []
    for variant in (a, b):
        lookup.append(
            {
                (s["frame"], s["object_id"]): s["matched_track_error"]
                for s in variant["scoring"]["diagnostics"]["samples"]
                if s["matched_track_id"] is not None
            }
        )
    keys = sorted(lookup[0].keys() & lookup[1].keys())
    result = dict(common_matched_object_frames=len(keys))
    for anchor in ("bottom_centre", "box_centre"):
        means = [
            math.fsum(v[k][anchor]["distance"] for k in keys) / len(keys) if keys else None
            for v in lookup
        ]
        result[anchor] = dict(
            baseline_mean_distance_world=means[0],
            gate_off_mean_distance_world=means[1],
            candidate_minus_baseline=means[1] - means[0] if keys else None,
        )
    return result


def diagnose(bundle, root):
    """Require original development evidence; never open held-out files."""
    check(root.resolve() == Path(__file__).resolve().parents[1], "use this script's repository")
    evidence = Evidence()
    script = evidence.bytes(Path(__file__).resolve())
    index = evidence.index(root, "development")
    spec = evidence.load(root / "experiments/box_gate_protocol_v1.json")
    parent = evidence.load(root / "experiments/traffic_protocol_v1.json")
    for name, digest in index["protocol_hashes"].items():
        same(sha(evidence.bytes(root / name)), digest, "frozen protocol changed")
    manifest, _ = evidence.bundle(bundle, index, spec, parent, "development")
    helper = index["audit"]
    same(sha(evidence.bytes(root / helper["script"])), helper["script_sha256"], "audit helper")
    saved = evidence.load(bundle.parent / "audit.json")
    same(sha(evidence.bytes(bundle.parent / "audit.json")), helper["output_sha256"], "saved audit")
    # Reuse the unchanged arithmetic/provenance auditor, not the tracker/scorer.
    check(development_audit(bundle, root) == saved, "reviewed development audit differs")
    cases, groups = [], {}
    for scenario, seed, condition in grid(spec, parent, "development"):
        variants = {}
        diagnostics = {}
        for name in ("baseline", "gate_off"):
            path = f"pairs/{scenario}/{seed}/{condition}/{name}.json"
            variants[name] = evidence.load(bundle / path)
            objects = [o["object_id"] for o in spec["scenarios"][scenario]]
            diagnostics[name] = diagnose_variant(variants[name], objects, parent)
            group = groups.setdefault(
                (scenario, condition, name), {p: dict.fromkeys(COUNTS, 0) for p in PHASES}
            )
            for p in PHASES:
                for key in COUNTS:
                    group[p][key] += diagnostics[name]["by_phase"][p][key]
        cases.append(
            dict(
                scenario=scenario,
                seed=seed,
                condition=condition,
                variants=diagnostics,
                common_matched_localization=common_localization(
                    variants["baseline"], variants["gate_off"]
                ),
            )
        )
    evidence.unchanged()
    return dict(
        format="visiontrack.box-gate-development-diagnosis/v1",
        scope="post-study exploratory saved-development symptoms, not a new intervention trial",
        diagnosis_script_sha256=sha(script),
        development_manifest_sha256=manifest["manifest_sha256"],
        source_revision=index["source_revision"],
        paired_cases=len(cases),
        variant_records=2 * len(cases),
        new_tracker_runs=0,
        heldout_files_read=False,
        internal_gate_cause_established=False,
        production_change_authorized=False,
        aggregation="totals over ten repeated noise seeds; one retained output per variant, not "
        "three reset-check passes; phase windows are fixed ranges in all conditions",
        groups=[
            dict(scenario=s, condition=c, variant=v, by_phase=counts)
            for (s, c, v), counts in groups.items()
        ],
        cases=cases,
        limitations=[
            "Saved labels, canonical correspondence, crossing events and receipts remain trusted.",
            "Absent public output cannot distinguish confirmation, rejection or deletion causes.",
            "Below-IoU boxes describe evaluation geometry, not detector false detections/identity.",
            "Eligible unmatched boxes may belong to another reference; no rematching is done.",
            "Common-frame means exclude misses; they are not unconditional accuracy measures.",
            "No internal association cost, gate distance or pre-update covariance was retained.",
            "Synthetic post-study exploration, not new held-out validation/population inference.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="optional NEW external JSON companion")
    args = parser.parse_args()
    try:
        result = diagnose(args.development, args.root)
        if args.output is not None:
            digest = write_output(args.output, result, [args.root, args.development.parent])
            print(canonical(dict(output=str(args.output.resolve()), sha256=digest)).decode())
        else:
            print(canonical(result).decode())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"Diagnosis refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
