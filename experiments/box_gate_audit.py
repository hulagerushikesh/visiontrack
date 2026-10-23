"""Read-only saved development audit; no tracker, generator or scorer imports.

Reconstructs endpoint arithmetic from retained samples/events and compares raw
hashes, Git provenance, receipts, complete coverage, summaries and rule margins.
It does not independently establish CLEAR-MOT correspondence, raw detector
generation, ground-truth correctness, real-world accuracy or runtime execution.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def compare(actual, expected, label):
    """Tolerance only for independently summed diagnostics, never rule gates."""
    if isinstance(expected, dict):
        check(isinstance(actual, dict) and actual.keys() == expected.keys(), label + ": keys")
        for key in expected:
            compare(actual[key], expected[key], label + "." + key)
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), label + ": length")
        for index, value in enumerate(expected):
            compare(actual[index], value, f"{label}[{index}]")
    elif isinstance(expected, float):
        check(
            type(actual) in (int, float)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            label + ": numeric mismatch",
        )
    else:
        check(type(actual) is type(expected) and actual == expected, label + ": mismatch")


def sealed(value, field):
    body = {key: item for key, item in value.items() if key != field}
    check(value[field] == sha(canonical(body)), field + ": invalid digest")


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("nonfinite JSON number: " + value)

    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=nonfinite)


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=10,
    ).stdout


def reconstruct_endpoints(variant, objects, frames):
    """Arithmetic from saved correspondence, not a new correspondence solver."""
    scoring, output = variant["scoring"], variant["output"]
    diagnostics = scoring["diagnostics"]
    samples, failures = diagnostics["samples"], diagnostics["failures"]
    check(
        [(s["frame"], s["object_id"]) for s in samples]
        == [(f, identity) for f in range(frames) for identity in objects],
        "incomplete or reordered reference samples",
    )
    rows = {(row["frame"], row["track_id"]): row for row in output}
    check(len(rows) == len(output), "duplicate public output row")
    matched = [s for s in samples if s["matched_track_id"] is not None]
    match_keys = {(s["frame"], s["matched_track_id"]) for s in matched}
    check(len(match_keys) == len(matched) and match_keys <= rows.keys(), "invalid saved matches")
    for sample in samples:
        check(
            (sample["matched_track_id"] is None) == (sample["matched_track_error"] is None),
            "missing conditional error differs from missing correspondence",
        )
    types = Counter(event["event_type"] for event in failures)
    totals = {
        "true_object_frames": len(samples),
        "matched_object_frames": len(matched),
        "missed_object_frames": len(samples) - len(matched),
        "matched_object_frame_fraction": len(matched) / len(samples),
        "id_switches": sum(s["id_switch"] for s in samples),
        "fragmentations": sum(s["fragmentation"] for s in samples),
        "false_positive_rows": len(output) - len(matched),
    }
    for name, event in (
        ("missed_object_frames", "miss"),
        ("id_switches", "id_switch"),
        ("fragmentations", "fragmentation"),
        ("false_positive_rows", "false_positive"),
    ):
        check(totals[name] == types[event], "failure list disagrees with samples/public rows")
    endpoints = {"tracking." + key: value for key, value in totals.items()}
    for name, key in (
        ("observation_contact_error", "observation_error"),
        ("matched_track_contact_error", "matched_track_error"),
    ):
        for anchor in ("bottom_centre", "box_centre"):
            values = [s[key][anchor] for s in samples if s[key] is not None]
            for error in values:
                compare(error["distance"], math.hypot(error["dx"], error["dy"]), "distance")
            prefix = f"tracking.{name}.{anchor}."
            endpoints[prefix + "sample_count"] = len(values)
            endpoints[prefix + "mean_distance_world"] = (
                math.fsum(v["distance"] for v in values) / len(values) if values else None
            )
    for anchor in ("bottom_centre", "box_centre"):
        crossing = scoring["crossing"][anchor]
        truth, predicted, matches = (
            crossing["truth_events"],
            crossing["predicted_events"],
            crossing["matches"],
        )
        rules = crossing["rules"]
        # Enumerate the registered ordered objective from retained events, not
        # the scorer's selected matches. This is bounded to <=2 truth events.
        check(len(truth) <= 2 and len(predicted) <= 1200, "crossing capacity")
        choices = [
            [-1]
            + [
                index
                for index, p in enumerate(predicted)
                if t["direction"] == p["direction"]
                and abs(t["frame_time"] - p["frame_time"]) <= rules["max_match_time_error_frames"]
                and abs(t["x"] - p["x"]) <= rules["max_match_x_error_world_units"]
            ]
            for t in truth
        ]
        candidates = []
        for assignment in itertools.product(*choices):
            selected = [(ti, pi) for ti, pi in enumerate(assignment) if pi >= 0]
            if len({pi for _, pi in selected}) != len(selected):
                continue
            objective = (
                -len(selected),
                sum(
                    abs(truth[ti]["frame_time"] - predicted[pi]["frame_time"])
                    for ti, pi in selected
                ),
                sum(abs(truth[ti]["x"] - predicted[pi]["x"]) for ti, pi in selected),
                tuple(
                    sorted(
                        (truth[ti]["track_id"], predicted[pi]["track_id"]) for ti, pi in selected
                    )
                ),
            )
            candidates.append((objective, selected))
        best = min(candidates, key=lambda item: item[0])[1]
        compare(
            [[m["truth"], m["predicted"]] for m in matches],
            [[truth[ti], predicted[pi]] for ti, pi in best],
            "crossing selected matches",
        )
        compare(
            crossing["unmatched_truth"],
            [t for i, t in enumerate(truth) if i not in {ti for ti, _ in best}],
            "misses",
        )
        compare(
            crossing["unmatched_predictions"],
            [p for i, p in enumerate(predicted) if i not in {pi for _, pi in best}],
            "extras",
        )
        window_size = rules["count_window_frames"]
        window_error = 0
        for direction, label in ((1, "positive"), (-1, "negative")):
            counts = []
            for group in (truth, predicted):
                counts.append(
                    [
                        sum(
                            e["direction"] == direction and int(e["frame_time"] // window_size) == w
                            for e in group
                        )
                        for w in range(frames // window_size)
                    ]
                )
            deltas = [p - t for t, p in zip(*counts, strict=True)]
            compare(
                crossing["counts_by_direction_window"][label],
                {
                    "truth": counts[0],
                    "predicted": counts[1],
                    "predicted_minus_truth": deltas,
                },
                "window counts",
            )
            window_error += sum(map(abs, deltas))
        time_errors = [
            abs(m["truth"]["frame_time"] - m["predicted"]["frame_time"]) for m in matches
        ]
        x_errors = [abs(m["truth"]["x"] - m["predicted"]["x"]) for m in matches]
        summary = {
            "truth_count": len(truth),
            "predicted_count": len(predicted),
            "matched_count": len(matches),
            "missed_events": len(truth) - len(matches),
            "extra_events": len(predicted) - len(matches),
            "event_error": len(truth) + len(predicted) - 2 * len(matches),
            "recall": len(matches) / len(truth) if truth else None,
            "matched_time_abs_mean_frames": math.fsum(time_errors) / len(matches)
            if matches
            else None,
            "matched_x_abs_mean_world": math.fsum(x_errors) / len(matches) if matches else None,
            "matched_wrong_window_events": sum(
                int(m["truth"]["frame_time"] // window_size)
                != int(m["predicted"]["frame_time"] // window_size)
                for m in matches
            ),
            "window_count_abs_error": window_error,
        }
        compare(crossing["summary"], summary, "crossing summary")
        endpoints.update({f"crossing.{anchor}.{key}": value for key, value in summary.items()})
    check(len(endpoints) == 37, "37 endpoints required")
    compare(scoring["endpoints"], endpoints, "reconstructed endpoints")
    return scoring["endpoints"]


def descriptive(vectors):
    result = {}
    for name in vectors[0]:
        values = [v[name] for v in vectors if v[name] is not None]
        result[name] = {
            "defined_seeds": len(values),
            "undefined_seeds": len(vectors) - len(values),
            "mean": math.fsum(values) / len(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return result


def audit(bundle: Path, root: Path) -> dict:
    manifest, plan, summary = [
        load(bundle / name) for name in ("manifest.json", "plan.json", "summary.json")
    ]
    sealed(manifest, "manifest_sha256")
    check(manifest["status"] == "complete" and manifest["error"] is None, "not a complete bundle")
    check(
        [
            manifest[key]
            for key in ("planned_pairs", "attempted_pairs", "successful_pairs", "unattempted_pairs")
        ]
        == [120, 120, 120, 0],
        "incomplete pair counts",
    )
    for name, digest in manifest["files_sha256"].items():
        path = bundle / name
        check(
            not path.is_symlink() and path.resolve().is_relative_to(bundle.resolve()),
            "unsafe bundle path",
        )
        check(sha(path.read_bytes()) == digest, "saved hash mismatch: " + name)
    expected_files = {"plan.json", "attempts.jsonl", "summary.json", "summary.md"}
    spec, source, baseline = plan["registration"], plan["source"], plan["baseline_source"]
    revision = source["replay_source"]["actual_revision"]
    check(source["replay_source"]["worktree_dirty"] is False, "dirty source provenance")
    for key in ("source", "baseline_source", "environment", "protocol_id", "protocol_hashes"):
        compare(manifest[key], plan[key], "manifest-plan " + key)
    check(plan["heldout_tracking_authorized"] is False, "heldout authorization present")
    check(
        manifest["heldout_tracking_executed"] is False
        and manifest["complete_study_report"] is False,
        "invalid study claim",
    )
    for name, digest in source["harness_sha256"].items():
        check(sha(git(root, "show", f"{revision}:{name}")) == digest, "committed harness mismatch")
    for name, digest in source["replay_source"]["experiment_sha256"].items():
        check(source["harness_sha256"][name] == digest, "replay harness mismatch")
    check(baseline["revision"] == spec["baseline_revision"], "baseline revision")
    check(baseline["sha256"] == sha(canonical(baseline["files"])), "baseline map seal")
    for name, digest in baseline["files"].items():
        check(
            sha(git(root, "show", f"{baseline['revision']}:{name}")) == digest,
            "baseline object mismatch",
        )
        check(sha((root / name).read_bytes()) == digest, "current baseline differs")
    for name, digest in plan["protocol_hashes"].items():
        check(sha(git(root, "show", f"{revision}:{name}")) == digest, "protocol bytes mismatch")
    compare(
        spec,
        json.loads(git(root, "show", f"{revision}:experiments/box_gate_protocol_v1.json")),
        "registration",
    )
    parent = json.loads(git(root, "show", f"{revision}:experiments/traffic_protocol_v1.json"))
    scenarios, seeds = (
        spec["splits"]["development"]["scenarios"],
        spec["splits"]["development"]["seeds"],
    )
    conditions = [c["id"] for c in parent["conditions"]]
    grid = list(itertools.product(scenarios, seeds, conditions))
    ledger = [json.loads(line) for line in (bundle / "attempts.jsonl").read_bytes().splitlines()]
    check(len(ledger) == 480 and len(plan["inputs"]) == 120, "coverage/ledger length")
    indexed, regressions = {}, []
    safety = [
        "tracking.id_switches",
        "tracking.missed_object_frames",
        "tracking.false_positive_rows",
        "crossing.bottom_centre.event_error",
        "crossing.bottom_centre.window_count_abs_error",
    ]
    for index, (scenario, seed, condition) in enumerate(grid):
        prefix = f"pairs/{scenario}/{seed}/{condition}"
        selector = {"scenario": scenario, "seed": seed, "condition": condition}
        events = ledger[index * 4 : index * 4 + 4]
        expected_events = [{"event": "start", **selector}]
        for variant in spec["grid"]["variant_order"]:
            path = f"{prefix}/{variant}.json"
            expected_events.append(
                {
                    "event": "variant_retained",
                    **selector,
                    "variant": variant,
                    "path": path,
                    "sha256": manifest["files_sha256"][path],
                    "validated_pair": False,
                }
            )
            expected_files.add(path)
        path = f"{prefix}/pair.json"
        expected_events.append(
            {"event": "success", **selector, "path": path, "sha256": manifest["files_sha256"][path]}
        )
        expected_files.add(path)
        compare(events, expected_events, "ordered ledger")
        record = load(bundle / path)
        sealed(record, "record_sha256")
        inputs = plan["inputs"][index]
        compare(record["input"], inputs, "planned input")
        check(
            all(inputs[key] == value for key, value in selector.items())
            and inputs["split"] == "development",
            "input selector",
        )
        sealed(inputs, "input_sha256")
        sealed(inputs["detections"], "detection_stream_sha256")
        for name, expected in (
            ("source", source["replay_source"]),
            ("environment", plan["environment"]),
            ("baseline_source", baseline),
            ("protocol_hashes", plan["protocol_hashes"]),
        ):
            compare(record[name], expected, "pair " + name)
        check(
            record["heldout_tracking_executed"] is False
            and record["complete_study_report"] is False,
            "pair scope",
        )
        check([v["id"] for v in record["variants"]] == ["baseline", "gate_off"], "variant order")
        endpoints = {}
        for variant, recipe in zip(record["variants"], spec["variants"], strict=True):
            compare(load(bundle / f"{prefix}/{variant['id']}.json"), variant, "retained variant")
            settings = {**parent["tracker_config"], **recipe["config_patch"]}
            check(canonical(variant["config"]) == canonical(settings), "single-switch config")
            check(variant["config_sha256"] == sha(canonical(settings)), "config seal")
            check(variant["output_sha256"] == sha(canonical(variant["output"])), "output seal")
            compare(
                variant["replay"],
                {
                    "passes": 3,
                    "pass_order": ["fresh", "reset", "independent_fresh"],
                    "updates_per_pass": 300,
                    "reset_equal": True,
                    "fresh_equal": True,
                    "detection_receipts": [inputs["detections"]] * 3,
                },
                "replay receipts",
            )
            scoring = variant["scoring"]
            sealed(scoring, "scoring_sha256")
            compare(scoring["input"], inputs, "scoring inputs")
            compare(scoring["source"], baseline, "scoring source")
            check(scoring["public_rows_sha256"] == variant["output_sha256"], "scored output seal")
            endpoints[variant["id"]] = reconstruct_endpoints(variant, inputs["object_ids"], 300)
        delta = {
            name: None
            if endpoints["baseline"][name] is None or endpoints["gate_off"][name] is None
            else endpoints["gate_off"][name] - endpoints["baseline"][name]
            for name in endpoints["baseline"]
        }
        compare(record["candidate_minus_baseline"], delta, "paired difference")
        indexed[scenario, seed, condition] = {
            "absolute": endpoints,
            "candidate_minus_baseline": delta,
        }
        for name in safety:
            a, b = endpoints["baseline"][name], endpoints["gate_off"][name]
            if b > a:
                regressions.append(
                    {**selector, "endpoint": name, "baseline": a, "gate_off": b, "increase": b - a}
                )
    check(
        expected_files == set(manifest["files_sha256"]) and len(expected_files) == 364,
        "unexpected indexed files",
    )
    check(
        {str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()}
        == expected_files | {"manifest.json"},
        "unindexed bundle files",
    )
    for scenario in summary["scenarios"]:
        name = scenario["scenario"]
        compare(
            scenario["seeds"],
            [
                {
                    "seed": seed,
                    "conditions": {
                        condition: indexed[name, seed, condition] for condition in conditions
                    },
                }
                for seed in seeds
            ],
            "summary per seed",
        )
        for condition in conditions:
            records = [indexed[name, seed, condition] for seed in seeds]
            for variant in ("baseline", "gate_off"):
                compare(
                    scenario["conditions"][condition]["absolute"][variant],
                    descriptive([r["absolute"][variant] for r in records]),
                    "absolute summary",
                )
            compare(
                scenario["conditions"][condition]["candidate_minus_baseline"],
                descriptive([r["candidate_minus_baseline"] for r in records]),
                "difference summary",
            )
    check([s["scenario"] for s in summary["scenarios"]] == scenarios, "summary scenario coverage")
    rules = summary["numerical_rules"]
    sealed(rules, "rules_sha256")
    dev = rules["splits"][0]
    compare(dev["regressions"], regressions, "all per-case safety regressions")
    numerical = []
    for scenario in scenarios:
        objects = len(spec["scenarios"][scenario])
        records = [
            indexed[scenario, seed, condition]
            for seed in seeds
            for condition in spec["evaluation"]["error_conditions"]
        ]
        means = {
            v: Fraction(
                sum(r["absolute"][v]["tracking.id_switches"] for r in records),
                objects * len(records),
            )
            for v in ("baseline", "gate_off")
        }
        a, b = means["baseline"], means["gate_off"]
        reduction, relative = a - b, (a - b) / a if a else None
        challenged = a >= Fraction(
            str(spec["evaluation"]["minimum_baseline_id_switches_per_object"])
        )
        improved = (
            challenged
            and reduction
            >= Fraction(str(spec["evaluation"]["minimum_absolute_id_switch_reduction_per_object"]))
            and relative is not None
            and relative
            >= Fraction(str(spec["evaluation"]["minimum_relative_id_switch_reduction"]))
        )
        numerical.append(
            {
                "scenario": scenario,
                "reference_objects": objects,
                "error_cases": len(records),
                "baseline_primary": float(a),
                "gate_off_primary": float(b),
                "absolute_reduction": float(reduction),
                "relative_reduction": float(relative) if relative is not None else None,
                "adequate_challenge": challenged,
                "meets_both_improvement_margins": improved,
            }
        )
    compare(dev["scenarios"], numerical, "independent rational margins")
    check(dev["complete"] is True and dev["missing_cases"] == [], "development incomplete")
    check(
        dev["adequate_challenge"] == (sum(s["adequate_challenge"] for s in numerical) >= 2),
        "challenge rule",
    )
    check(
        dev["benefit_margin_met"]
        == (sum(s["meets_both_improvement_margins"] for s in numerical) >= 2),
        "benefit rule",
    )
    check(
        dev["all_endpoints_identical"]
        == all(r["absolute"]["baseline"] == r["absolute"]["gate_off"] for r in indexed.values()),
        "no-effect rule",
    )
    check(
        rules["classification"] == "inconclusive" and rules["invalid_evidence"] is None,
        "development cannot settle full study",
    )
    held = rules["splits"][1]
    expected_heldout = [
        list(key)
        for key in itertools.product(
            spec["splits"]["heldout"]["scenarios"], spec["splits"]["heldout"]["seeds"], conditions
        )
    ]
    check(
        held["split"] == "heldout"
        and held["complete"] is False
        and held["missing_cases"] == expected_heldout
        and held["scenarios"] == []
        and held["regressions"] == [],
        "held-out evidence unexpectedly present",
    )
    return {
        "format": "visiontrack.box-gate-development-audit/v1",
        "bundle_manifest_sha256": manifest["manifest_sha256"],
        "source_revision": revision,
        "indexed_files_verified": 364,
        "ordered_ledger_entries": 480,
        "paired_cases": 120,
        "variant_runs": 240,
        "recorded_replay_passes": 720,
        "recorded_updates_per_pass": 300,
        "endpoint_values_reconstructed": 240 * 37,
        "paired_differences_checked": 120 * 37,
        "descriptive_endpoint_groups_checked": 3 * 4 * 3 * 37,
        "harness_files_verified": len(source["harness_sha256"]),
        "baseline_files_verified": len(baseline["files"]),
        "development_primary": numerical,
        "safety_regressions": regressions,
        "study_classification": "inconclusive",
        "heldout_tracking_executed": False,
        "limitations": [
            "Read-only artifact/arithmetic audit, not independent runtime execution proof.",
            "Saved canonical CLEAR-MOT correspondence and input manifests are trusted primitives; "
            "not independently regenerated.",
            "Localization aggregates checked from retained errors, "
            "not independent geometric projection.",
            "No new tracker replay, scorer call, generator call or held-out measurements.",
            "Diagnostic arithmetic tolerance 1e-12; registered rational margins "
            "and integer safety comparisons have no tolerance.",
            "Synthetic evidence only, not consent, real accuracy "
            "or permission to change production/C++.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.bundle, args.root), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
