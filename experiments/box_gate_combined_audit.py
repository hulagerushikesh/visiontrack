"""Read-only saved-record audit of the closed box-gate study, not a replay.

Uses the unchanged development auditor's arithmetic helpers, independently of
the scorer. Checks decision priority/margins separately from box_gate_decision.
Trusts saved input manifests, CLEAR-MOT correspondence and recorded execution
receipts; does not independently establish geometry, labels or execution.
The original indices, bundles, freeze and consumed opening are never rewritten.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

from experiments.box_gate_audit import (
    audit as development_audit,
)
from experiments.box_gate_audit import (
    canonical,
    check,
    compare,
    descriptive,
    git,
    reconstruct_endpoints,
    sealed,
    sha,
)

EVIDENCE_REVISION = "8df9cff159c2f2b37c965721a03c280f2e1fe2d8"
MAX_BYTES = 4 * 1024 * 1024
SAFETY = (
    "tracking.id_switches",
    "tracking.missed_object_frames",
    "tracking.false_positive_rows",
    "crossing.bottom_centre.event_error",
    "crossing.bottom_centre.window_count_abs_error",
)
SPLITS = ("development", "heldout")
VARIANTS = ("baseline", "gate_off")


def read(path):
    check(path.is_file() and not path.is_symlink(), "expected regular evidence file")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    check(len(data) <= MAX_BYTES, "oversized evidence file")
    return data


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        check(math.isfinite(result), "nonfinite JSON number")
        return result

    return json.loads(data, object_pairs_hook=pairs, parse_float=number, parse_constant=number)


def same(actual, expected, label):
    check(canonical(actual) == canonical(expected), label)


def grid(spec, parent, split):
    return list(
        itertools.product(
            spec["splits"][split]["scenarios"],
            spec["splits"][split]["seeds"],
            [c["id"] for c in parent["conditions"]],
        )
    )


def validate_values(values):
    """Reject invalid numbers before exact integer/rational decision gates."""
    crossing = (
        "truth_count",
        "predicted_count",
        "matched_count",
        "missed_events",
        "extra_events",
        "event_error",
        "recall",
        "matched_time_abs_mean_frames",
        "matched_x_abs_mean_world",
        "matched_wrong_window_events",
        "window_count_abs_error",
    )
    expected = {f"crossing.{a}.{n}" for a in ("bottom_centre", "box_centre") for n in crossing}
    expected.update(
        f"tracking.{n}"
        for n in (
            "true_object_frames",
            "matched_object_frames",
            "missed_object_frames",
            "matched_object_frame_fraction",
            "id_switches",
            "fragmentations",
            "false_positive_rows",
        )
    )
    expected.update(
        f"tracking.{n}.{a}.{m}"
        for n in ("observation_contact_error", "matched_track_contact_error")
        for a in ("bottom_centre", "box_centre")
        for m in ("sample_count", "mean_distance_world")
    )
    check(isinstance(values, dict) and set(values) == expected, "exact 37 endpoints required")
    for name, value in values.items():
        nullable = name.endswith(("recall", "mean_frames", "mean_world", "mean_distance_world"))
        if value is None and nullable:
            continue
        check(
            type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "invalid absolute endpoint",
        )
        if not nullable and not name.endswith("matched_object_frame_fraction"):
            check(type(value) is int, "count endpoint must be an integer")
        if name.endswith(("recall", "matched_object_frame_fraction")):
            check(value <= 1, "fraction exceeds one")


def decision(entries, spec, parent):
    """Separate implementation of registered priorities; invalid tables refuse.

    Fractions are formed from integer IDSW totals, not rounded reported means.
    Incomplete or inadequately challenged splits take precedence over failure.
    """
    expected = {(split, *key) for split in SPLITS for key in grid(spec, parent, split)}
    check(isinstance(entries, list) and len(entries) <= len(expected), "invalid evidence length")
    indexed = {}
    for entry in entries:
        check(
            set(entry) == {"split", "scenario", "seed", "condition", "endpoints"},
            "invalid evidence fields",
        )
        check(type(entry["seed"]) is int, "invalid seed")
        key = tuple(entry[k] for k in ("split", "scenario", "seed", "condition"))
        check(key in expected and key not in indexed, "unexpected/duplicate paired case")
        check(set(entry["endpoints"]) == set(VARIANTS), "both variants required")
        for values in entry["endpoints"].values():
            validate_values(values)
        indexed[key] = entry["endpoints"]
    policy = spec["evaluation"]
    results = []
    for split in SPLITS:
        keys = grid(spec, parent, split)
        missing = [list(key) for key in keys if (split, *key) not in indexed]
        result = dict(
            split=split,
            complete=not missing,
            missing_cases=missing,
            scenarios=[],
            regressions=[],
            all_endpoints_identical=True,
        )
        for scenario, seed, condition in keys:
            pair = indexed.get((split, scenario, seed, condition))
            if pair is None:
                continue
            a, b = (pair[v] for v in VARIANTS)
            result["all_endpoints_identical"] &= a == b
            for endpoint in SAFETY:
                if b[endpoint] > a[endpoint]:
                    result["regressions"].append(
                        dict(
                            scenario=scenario,
                            seed=seed,
                            condition=condition,
                            endpoint=endpoint,
                            baseline=a[endpoint],
                            gate_off=b[endpoint],
                            increase=b[endpoint] - a[endpoint],
                        )
                    )
        for scenario in spec["splits"][split]["scenarios"]:
            selected = [
                indexed.get((split, scenario, seed, condition))
                for seed in spec["splits"][split]["seeds"]
                for condition in policy["error_conditions"]
            ]
            if any(pair is None for pair in selected):
                continue
            objects = len(spec["scenarios"][scenario])
            a, b = [
                Fraction(
                    sum(p[v]["tracking.id_switches"] for p in selected), objects * len(selected)
                )
                for v in VARIANTS
            ]
            reduction = a - b
            relative = reduction / a if a else None
            challenged = a >= Fraction(str(policy["minimum_baseline_id_switches_per_object"]))
            improved = (
                challenged
                and relative is not None
                and reduction
                >= Fraction(str(policy["minimum_absolute_id_switch_reduction_per_object"]))
                and relative >= Fraction(str(policy["minimum_relative_id_switch_reduction"]))
            )
            result["scenarios"].append(
                dict(
                    scenario=scenario,
                    reference_objects=objects,
                    error_cases=len(selected),
                    baseline_primary=float(a),
                    gate_off_primary=float(b),
                    absolute_reduction=float(reduction),
                    relative_reduction=float(relative) if relative is not None else None,
                    adequate_challenge=challenged,
                    meets_both_improvement_margins=improved,
                )
            )
        minimum = policy["minimum_improved_scenarios_per_split"]
        result["adequate_challenge"] = (
            sum(s["adequate_challenge"] for s in result["scenarios"]) >= minimum
        )
        result["benefit_margin_met"] = (
            sum(s["meets_both_improvement_margins"] for s in result["scenarios"]) >= minimum
        )
        results.append(result)
    if any(not r["complete"] or not r["adequate_challenge"] for r in results):
        classification = "inconclusive"
    elif any(r["regressions"] for r in results):
        classification = "failure"
    elif all(r["all_endpoints_identical"] for r in results):
        classification = "no_effect"
    elif any(not r["benefit_margin_met"] for r in results):
        classification = "failure"
    else:
        classification = "pass"
    return dict(classification=classification, splits=results)


class Evidence:
    """Bounded read set; final rehash detects changes during this local audit."""

    def __init__(self):
        self.hashes = {}
        self.bundles = []

    def bytes(self, path):
        value = read(path)
        digest = sha(value)
        if path in self.hashes:
            same(digest, self.hashes[path], "evidence changed during audit")
        self.hashes[path] = digest
        return value

    def load(self, path):
        return decode(self.bytes(path))

    def index(self, root, split):
        name = f"experiments/box_gate_{split}_v1_evidence.json"
        raw = self.bytes(root / name)
        same(
            raw.hex(),
            git(root, "show", f"{EVIDENCE_REVISION}:{name}").hex(),
            "index differs from original reviewed snapshot",
        )
        return decode(raw)

    def bundle(self, path, index, spec, parent, split):
        check(not path.is_symlink() and path.is_dir(), "expected original bundle directory")
        manifest = self.load(path / "manifest.json")
        expected = {"plan.json", "attempts.jsonl", "summary.json", "summary.md"}
        for scenario, seed, condition in grid(spec, parent, split):
            expected.update(
                f"pairs/{scenario}/{seed}/{condition}/{v}.json" for v in (*VARIANTS, "pair")
            )
        same(sorted(manifest["files_sha256"]), sorted(expected), "exact indexed coverage")
        self.bundles.append((path, expected | {"manifest.json"}))
        self.coverage(path, expected | {"manifest.json"})
        raw_sha = index.get("manifest_raw_sha256", index["artifact_sha256"].get("manifest.json"))
        same(self.hashes[path / "manifest.json"], raw_sha, "original manifest bytes")
        sealed(manifest, "manifest_sha256")
        same(manifest["manifest_sha256"], index["bundle_manifest_sha256"], "original manifest seal")
        for name, digest in manifest["files_sha256"].items():
            same(sha(self.bytes(path / name)), digest, "indexed file hash: " + name)
        for name, digest in index["artifact_sha256"].items():
            same(self.hashes[path / name], digest, "reviewed artifact: " + name)
        same(
            [
                manifest[k]
                for k in (
                    "planned_pairs",
                    "attempted_pairs",
                    "successful_pairs",
                    "unattempted_pairs",
                )
            ],
            [120, 120, 120, 0],
            "complete counts",
        )
        check(manifest["status"] == "complete" and manifest["error"] is None, "incomplete run")
        plan = self.load(path / "plan.json")
        same(plan["registration"], spec, "unchanged registration")
        for key in ("protocol_id", "protocol_hashes", "source", "baseline_source", "environment"):
            same(manifest[key], plan[key], "manifest-plan " + key)
        same(plan["protocol_hashes"], index["protocol_hashes"], "reviewed protocol hashes")
        same(
            plan["source"]["replay_source"]["actual_revision"],
            index["source_revision"],
            "run source",
        )
        same(plan["source"]["replay_source"]["worktree_dirty"], False, "recorded clean source")
        same(plan["environment"], index["environment"], "recorded environment")
        held = split == "heldout"
        same(plan["heldout_tracking_authorized"], held, "authorization scope")
        same(manifest["heldout_tracking_executed"], held, "recorded run scope")
        same(manifest["complete_study_report"], False, "historical split scope")
        return manifest, plan

    @staticmethod
    def coverage(path, expected):
        paths = list(path.rglob("*"))
        check(not any(p.is_symlink() for p in paths), "bundle contains symlink")
        same(
            sorted(str(p.relative_to(path)) for p in paths if p.is_file()),
            sorted(expected),
            "exact bundle coverage",
        )

    def unchanged(self):
        for path, digest in self.hashes.items():
            same(sha(read(path)), digest, "evidence changed during audit: " + str(path))
        for path, expected in self.bundles:
            self.coverage(path, expected)


def audit_records(evidence, bundle, manifest, plan, spec, parent, split):
    """Check retained configuration/receipts and reconstruct the saved arithmetic."""
    summary = evidence.load(bundle / "summary.json")
    ledger = [decode(line) for line in evidence.bytes(bundle / "attempts.jsonl").splitlines()]
    keys = grid(spec, parent, split)
    same(len(ledger), 480, "complete ledger")
    same(len(plan["inputs"]), 120, "complete planned input grid")
    entries, indexed = [], {}
    for index, (scenario, seed, condition) in enumerate(keys):
        selector = dict(scenario=scenario, seed=seed, condition=condition)
        prefix = f"pairs/{scenario}/{seed}/{condition}"
        pair = evidence.load(bundle / f"{prefix}/pair.json")
        sealed(pair, "record_sha256")
        inputs = plan["inputs"][index]
        same(pair["input"], inputs, "planned pair input")
        same({k: inputs[k] for k in selector}, selector, "input selector")
        same(inputs["split"], split, "input split")
        same(
            inputs["object_ids"],
            [o["object_id"] for o in spec["scenarios"][scenario]],
            "reference object IDs",
        )
        sealed(inputs, "input_sha256")
        sealed(inputs["detections"], "detection_stream_sha256")
        same(pair["source"], plan["source"]["replay_source"], "pair source")
        for name in ("protocol_id", "protocol_hashes", "baseline_source", "environment"):
            same(pair[name], plan[name], "pair " + name)
        same(pair["heldout_tracking_executed"], split == "heldout", "pair run scope")
        same(pair["complete_study_report"], False, "pair historical scope")
        same([v["id"] for v in pair["variants"]], list(VARIANTS), "variant order")
        events = [dict(event="start", **selector)]
        endpoints = {}
        for variant, recipe in zip(pair["variants"], spec["variants"], strict=True):
            variant_path = f"{prefix}/{variant['id']}.json"
            same(evidence.load(bundle / variant_path), variant, "retained raw variant")
            settings = {**parent["tracker_config"], **recipe["config_patch"]}
            same(variant["config"], settings, "exact one-switch settings")
            same(variant["config_sha256"], sha(canonical(settings)), "config seal")
            same(variant["output_sha256"], sha(canonical(variant["output"])), "output seal")
            same(
                variant["replay"],
                dict(
                    passes=3,
                    pass_order=["fresh", "reset", "independent_fresh"],
                    updates_per_pass=300,
                    reset_equal=True,
                    fresh_equal=True,
                    detection_receipts=[inputs["detections"]] * 3,
                ),
                "all replay receipts",
            )
            scoring = variant["scoring"]
            sealed(scoring, "scoring_sha256")
            same(scoring["input"], inputs, "scoring input")
            same(scoring["source"], plan["baseline_source"], "scoring baseline")
            same(scoring["public_rows_sha256"], variant["output_sha256"], "scored output seal")
            for name in ("protocol_id", "protocol_hashes"):
                same(scoring[name], plan[name], "scoring " + name)
            for anchor in ("bottom_centre", "box_centre"):
                same(scoring["crossing"][anchor]["rules"], parent["crossing"], "crossing recipe")
            validate_values(scoring["endpoints"])
            endpoints[variant["id"]] = reconstruct_endpoints(variant, inputs["object_ids"], 300)
            events.append(
                dict(
                    event="variant_retained",
                    **selector,
                    variant=variant["id"],
                    path=variant_path,
                    sha256=manifest["files_sha256"][variant_path],
                    validated_pair=False,
                )
            )
        name = f"{prefix}/pair.json"
        events.append(
            dict(event="success", **selector, path=name, sha256=manifest["files_sha256"][name])
        )
        same(ledger[index * 4 : index * 4 + 4], events, "ordered retained attempts")
        a, b = (endpoints[v] for v in VARIANTS)
        delta = {k: None if a[k] is None or b[k] is None else b[k] - a[k] for k in a}
        compare(pair["candidate_minus_baseline"], delta, "paired contrasts")
        indexed[scenario, seed, condition] = dict(
            absolute=endpoints, candidate_minus_baseline=delta
        )
        entries.append(dict(split=split, **selector, endpoints=endpoints))
    same(
        [s["scenario"] for s in summary["scenarios"]],
        spec["splits"][split]["scenarios"],
        "summary scenario coverage",
    )
    for group in summary["scenarios"]:
        scenario = group["scenario"]
        seeds = spec["splits"][split]["seeds"]
        conditions = [c["id"] for c in parent["conditions"]]
        compare(
            group["seeds"],
            [
                dict(seed=seed, conditions={c: indexed[scenario, seed, c] for c in conditions})
                for seed in seeds
            ],
            "per-seed values",
        )
        for condition in conditions:
            values = [indexed[scenario, seed, condition] for seed in seeds]
            expected = dict(
                absolute={v: descriptive([r["absolute"][v] for r in values]) for v in VARIANTS},
                candidate_minus_baseline=descriptive(
                    [r["candidate_minus_baseline"] for r in values]
                ),
            )
            compare(group["conditions"][condition], expected, "seed summaries and null counts")
    saved_rules = summary["numerical_rules"]
    sealed(saved_rules, "rules_sha256")
    independent = decision(entries, spec, parent)
    same(saved_rules["classification"], independent["classification"], "split-only verdict")
    same(saved_rules["invalid_evidence"], None, "split evidence validity")
    compare(saved_rules["splits"], independent["splits"], "independently checked split rules")
    return entries


def audit(development, heldout, freeze_path, root):
    evidence = Evidence()
    audit_script_digest = sha(evidence.bytes(Path(__file__)))
    root = root.resolve()
    check(all(not p.is_symlink() for p in (development, heldout, freeze_path)), "symlink input")
    development, heldout, freeze_path = [p.resolve() for p in (development, heldout, freeze_path)]
    check(
        development != heldout
        and not development.is_relative_to(heldout)
        and not heldout.is_relative_to(development),
        "split bundles overlap",
    )
    indices = {split: evidence.index(root, split) for split in SPLITS}
    spec = evidence.load(root / "experiments/box_gate_protocol_v1.json")
    parent = evidence.load(root / "experiments/traffic_protocol_v1.json")
    bundles = dict(zip(SPLITS, (development, heldout), strict=True))
    checked = {
        split: evidence.bundle(bundles[split], indices[split], spec, parent, split)
        for split in SPLITS
    }
    for split, (_manifest, plan) in checked.items():
        source = plan["source"]
        revision = indices[split]["source_revision"]
        for name, digest in source["harness_sha256"].items():
            same(sha(git(root, "show", f"{revision}:{name}")), digest, "historical harness")
        for name, digest in source["replay_source"]["experiment_sha256"].items():
            same(source["harness_sha256"][name], digest, "recorded replay source")
        baseline = plan["baseline_source"]
        same(baseline["revision"], spec["baseline_revision"], "baseline revision")
        same(baseline["sha256"], sha(canonical(baseline["files"])), "baseline map seal")
        for name, digest in baseline["files"].items():
            same(
                sha(git(root, "show", f"{baseline['revision']}:{name}")),
                digest,
                "historical baseline",
            )
            same(sha(evidence.bytes(root / name)), digest, "unchanged current tracker")
        for name, digest in plan["protocol_hashes"].items():
            same(sha(git(root, "show", f"{revision}:{name}")), digest, "historical protocol")
            same(sha(evidence.bytes(root / name)), digest, "unchanged current protocol")
    dev_manifest, dev_plan = checked["development"]
    manifest, plan = checked["heldout"]
    for name in (
        "protocol_id",
        "protocol_hashes",
        "baseline_source",
        "environment",
        "registration",
    ):
        same(plan[name], dev_plan[name], "cross-split " + name)
    held_index, dev_index = indices["heldout"], indices["development"]
    freeze = evidence.load(freeze_path)
    opening_path = freeze_path.parent / "opening.json"
    opening = evidence.load(opening_path)
    for value, name in ((freeze, "freeze_sha256"), (opening, "opening_sha256")):
        sealed(value, name)
    pinned = held_index["freeze"]
    same(evidence.hashes[freeze_path], pinned["raw_sha256"], "original freeze bytes")
    same(
        evidence.hashes[opening_path],
        pinned["opening_raw_sha256"],
        "original consumed opening bytes",
    )
    same(freeze["freeze_sha256"], pinned["content_sha256"], "freeze content seal")
    same(opening["opening_sha256"], pinned["opening_content_sha256"], "opening content seal")
    same(opening["output"], str(heldout), "original opening output")
    same(opening["source_revision"], held_index["source_revision"], "opening revision")
    same(opening["freeze_raw_sha256"], pinned["raw_sha256"], "opening freeze binding")
    same(opening["freeze_sha256"], freeze["freeze_sha256"], "opening freeze seal")
    same(opening["execution_policy"], freeze["execution_policy"], "opening policy")
    same(opening["inputs_sha256"], sha(canonical(freeze["inputs"])), "input seal")
    same(opening["inputs_sha256"], freeze["inputs_sha256"], "frozen input seal")
    same(plan["inputs"], freeze["inputs"], "full frozen inputs")
    for name in (
        "source",
        "baseline_source",
        "environment",
        "protocol_id",
        "protocol_hashes",
        "development_evidence",
        "freeze_sha256",
    ):
        same(plan[name], freeze[name], "plan freeze lineage")
        same(manifest[name], freeze[name], "manifest freeze lineage")
    same(freeze["registration"], spec, "frozen registration")
    same(freeze["development_bundle"], str(development), "original development location")
    same(
        freeze["configurations"],
        [
            dict(id=v["id"], settings={**parent["tracker_config"], **v["config_patch"]})
            for v in spec["variants"]
        ],
        "frozen settings",
    )
    for value in (plan, manifest):
        same(value["opening"], opening, "original opening record")
    for flag in ("opening_consumed", "heldout_replay_attempted", "heldout_tracking_executed"):
        same(manifest[flag], True, "consumed complete run")
    for flag in (
        "complete_study_report",
        "candidate_accepted",
        "production_change_authorized",
        "cpp_port_authorized",
    ):
        same(manifest[flag], False, "historical adoption scope")
    # Original development auditor and result remain byte-pinned and DEV-only.
    dev_audit_info = dev_index["audit"]
    same(
        sha(evidence.bytes(root / dev_audit_info["script"])),
        dev_audit_info["script_sha256"],
        "unchanged pinned development auditor",
    )
    old_audit_path = development.parent / "audit.json"
    reviewed = evidence.load(old_audit_path)
    same(
        evidence.hashes[old_audit_path],
        dev_audit_info["output_sha256"],
        "original development audit bytes",
    )
    recalculated = development_audit(development, root)
    compare(reviewed, recalculated, "unchanged development audit")
    check(reviewed == recalculated, "development audit exact values differ")
    same(
        freeze["development_evidence"],
        dict(
            index_sha256=evidence.hashes[
                root / "experiments/box_gate_development_v1_evidence.json"
            ],
            source_revision=dev_index["source_revision"],
            bundle_manifest_sha256=dev_manifest["manifest_sha256"],
            files_sha256={
                **dev_manifest["files_sha256"],
                "manifest.json": dev_index["manifest_raw_sha256"],
            },
            audit_output_sha256=dev_audit_info["output_sha256"],
            environment=dev_plan["environment"],
            paired_cases=120,
            safety_endpoint_violations=len(reviewed["safety_regressions"]),
            candidate_accepted=False,
        ),
        "frozen binding to all development evidence",
    )
    entries = []
    for split in SPLITS:
        entries.extend(
            audit_records(evidence, bundles[split], *checked[split], spec, parent, split)
        )
    rules = decision(entries, spec, parent)
    reports = []
    for split, result in zip(SPLITS, rules["splits"], strict=True):
        selected = [e for e in entries if e["split"] == split]
        regressions = result["regressions"]
        reports.append(
            dict(
                **result,
                safety_endpoint_violations=len(regressions),
                distinct_paired_cases_affected=len(
                    {(r["scenario"], r["seed"], r["condition"]) for r in regressions}
                ),
                safety_comparisons={
                    name: dict(
                        Counter(
                            "worse"
                            if e["endpoints"]["gate_off"][name] > e["endpoints"]["baseline"][name]
                            else "better"
                            if e["endpoints"]["gate_off"][name] < e["endpoints"]["baseline"][name]
                            else "equal"
                            for e in selected
                        )
                    )
                    for name in SAFETY
                },
                control_pairs_identical_all_37_endpoints=sum(
                    e["condition"] in spec["evaluation"]["control_conditions"]
                    and e["endpoints"]["baseline"] == e["endpoints"]["gate_off"]
                    for e in selected
                ),
            )
        )
    evidence.unchanged()
    return dict(
        format="visiontrack.box-gate-combined-audit/v1",
        protocol_id=spec["protocol_id"],
        protocol_hashes=indices["heldout"]["protocol_hashes"],
        original_indices_revision=EVIDENCE_REVISION,
        audit_script_sha256=audit_script_digest,
        arithmetic_helper_sha256=dev_audit_info["script_sha256"],
        inputs={
            split: dict(
                source_revision=indices[split]["source_revision"],
                bundle_manifest_sha256=indices[split]["bundle_manifest_sha256"],
                index_sha256=evidence.hashes[
                    root / f"experiments/box_gate_{split}_v1_evidence.json"
                ],
            )
            for split in SPLITS
        },
        consumed_opening_raw_sha256=pinned["opening_raw_sha256"],
        paired_cases=240,
        variant_runs=480,
        recorded_replay_passes=1440,
        bundle_files_verified=730,
        ordered_ledger_entries_verified=960,
        endpoint_values_reconstructed=17760,
        paired_differences_checked=8880,
        descriptive_endpoint_groups_checked=2664,
        classification=rules["classification"],
        splits=reports,
        safety_endpoint_violations=sum(r["safety_endpoint_violations"] for r in reports),
        distinct_paired_cases_affected=sum(r["distinct_paired_cases_affected"] for r in reports),
        complete_study_report=True,
        new_tracker_runs=0,
        candidate_tuned=False,
        candidate_accepted=False,
        production_change_authorized=False,
        cpp_port_authorized=False,
        real_data_validated=False,
        limitations=[
            "Post-run read-only audit, not independently witnessed execution "
            "or external preregistration.",
            "Uses unchanged development arithmetic helpers independently of scorer, "
            "not a second implementation of those helpers.",
            "Saved input manifests, canonical CLEAR-MOT correspondence, labels "
            "and execution receipts remain trusted primitives.",
            "Does not regenerate projection, detections, truth "
            "or crossing events from tracker rows.",
            "Diagnostic arithmetic tolerance 1e-12 only; integer safety "
            "and rational decision gates have no tolerance.",
            "Synthetic paths/noise repeats are not independent real camera sites, "
            "population estimates or deployment validation.",
        ],
    )


def write_output(path, result, protected):
    """Optional new companion artifact; never write inside any input evidence."""
    check(not path.is_symlink() and not path.exists(), "audit output already exists")
    resolved = path.resolve()
    check(
        not any(resolved.is_relative_to(p.resolve()) for p in protected),
        "keep audit output outside repository, bundles and freeze directory",
    )
    raw = json.dumps(result, indent=2, allow_nan=False).encode() + b"\n"
    with resolved.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True, type=Path)
    parser.add_argument("--heldout", required=True, type=Path)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path, help="optional NEW external companion JSON, never overwrite evidence"
    )
    args = parser.parse_args()
    try:
        result = audit(args.development, args.heldout, args.freeze, args.root)
        if args.output is not None:
            digest = write_output(
                args.output, result, [args.root, args.development, args.heldout, args.freeze.parent]
            )
            print(
                json.dumps(
                    dict(
                        output=str(args.output.resolve()),
                        sha256=digest,
                        classification=result["classification"],
                        safety_endpoint_violations=result["safety_endpoint_violations"],
                    )
                )
            )
            return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Audit refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
