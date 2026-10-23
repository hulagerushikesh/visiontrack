"""Pure registered numerical rules, not provenance or permission to deploy.

Hand-worked endpoint tables test these rules without executing a tracker or
generating held-out measurements. Export validation must separately establish
that endpoints came from the pinned replay/scorer and complete input grid.
"""

from __future__ import annotations

import math
from fractions import Fraction
from numbers import Real

from experiments.box_gate_protocol import load_registration
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import CROSSING_METRICS, TRACKING_METRICS, _sha

ENDPOINTS = frozenset(
    [f"crossing.{a}.{m}" for a in ("bottom_centre", "box_centre") for m in CROSSING_METRICS]
    + [f"tracking.{m}" for m in TRACKING_METRICS]
    + [
        f"tracking.{n}.{a}.{m}"
        for n in ("observation_contact_error", "matched_track_contact_error")
        for a in ("bottom_centre", "box_centre")
        for m in ("sample_count", "mean_distance_world")
    ]
)
SAFETY = {
    "id_switches": "tracking.id_switches",
    "missed_object_frames": "tracking.missed_object_frames",
    "false_positive_rows": "tracking.false_positive_rows",
    "bottom_centre_missed_plus_extra_events": "crossing.bottom_centre.event_error",
    "bottom_centre_absolute_window_count_error": "crossing.bottom_centre.window_count_abs_error",
}


def cases(spec: dict, parent: dict, split: str) -> list[tuple[str, int, str]]:
    if split not in {"development", "heldout"}:
        raise ValueError("unknown box-gate split")
    return [
        (s, n, c["id"])
        for s in spec["splits"][split]["scenarios"]
        for n in spec["splits"][split]["seeds"]
        for c in parent["conditions"]
    ]


def validate_endpoints(values: dict) -> None:
    if not isinstance(values, dict) or set(values) != ENDPOINTS:
        raise ValueError("exactly the 37 registered endpoints are required")
    for name, value in values.items():
        nullable = name.endswith(("recall", "mean_frames", "mean_world", "mean_distance_world"))
        if value is None and nullable:
            continue
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("endpoints must be finite numbers; null only for conditional means")
        if value < 0:
            raise ValueError("absolute endpoints cannot be negative")
        count = not nullable and not name.endswith("matched_object_frame_fraction")
        if count and type(value) is not int:
            raise ValueError("count endpoints must be native integers")
        if name.endswith(("recall", "matched_object_frame_fraction")) and value > 1:
            raise ValueError("fraction endpoint exceeds one")


def _split_rules(indexed: dict, split: str, spec: dict, parent: dict) -> dict:
    policy = spec["evaluation"]
    expected = cases(spec, parent, split)
    missing = [list(key) for key in expected if (split, *key) not in indexed]
    result = {
        "split": split,
        "complete": not missing,
        "missing_cases": missing,
        "scenarios": [],
        "regressions": [],
        "all_endpoints_identical": True,
    }
    for scenario, seed, condition in expected:
        pair = indexed.get((split, scenario, seed, condition))
        if pair is None:
            continue
        baseline, candidate = pair["baseline"], pair["gate_off"]
        if baseline != candidate:
            result["all_endpoints_identical"] = False
        for label in policy["per_paired_case_nonincrease"]:
            name = SAFETY[label]
            if candidate[name] > baseline[name]:
                result["regressions"].append(
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "condition": condition,
                        "endpoint": name,
                        "baseline": baseline[name],
                        "gate_off": candidate[name],
                        "increase": candidate[name] - baseline[name],
                    }
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
        primary = {
            variant: Fraction(
                sum(p[variant]["tracking.id_switches"] for p in selected), objects * len(selected)
            )
            for variant in ("baseline", "gate_off")
        }
        baseline, candidate = primary["baseline"], primary["gate_off"]
        reduction = baseline - candidate
        relative = reduction / baseline if baseline else None
        challenged = baseline >= Fraction(str(policy["minimum_baseline_id_switches_per_object"]))
        improved = (
            challenged
            and reduction
            >= Fraction(str(policy["minimum_absolute_id_switch_reduction_per_object"]))
            and relative is not None
            and relative >= Fraction(str(policy["minimum_relative_id_switch_reduction"]))
        )
        result["scenarios"].append(
            {
                "scenario": scenario,
                "reference_objects": objects,
                "error_cases": len(selected),
                "baseline_primary": float(baseline),
                "gate_off_primary": float(candidate),
                "absolute_reduction": float(reduction),
                "relative_reduction": float(relative) if relative is not None else None,
                "adequate_challenge": challenged,
                "meets_both_improvement_margins": improved,
            }
        )
    minimum = policy["minimum_improved_scenarios_per_split"]
    result["adequate_challenge"] = (
        sum(s["adequate_challenge"] for s in result["scenarios"]) >= minimum
    )
    result["benefit_margin_met"] = (
        sum(s["meets_both_improvement_margins"] for s in result["scenarios"]) >= minimum
    )
    return result


def evaluate_rules(evidence: list[dict]) -> dict:
    """Evaluate endpoint tables; no supplied table is proof of tracker execution.

    Both complete splits are needed for the numerical study classification.
    Incomplete/invalid evidence or inadequate challenge takes precedence over
    regressions. All safety violations remain visible, including clean controls.
    Threshold comparisons use exact rational arithmetic, with no epsilon/tuning.
    """
    spec, hashes = load_registration()
    parent, _ = load_frozen_protocol()
    indexed, invalid = {}, None
    try:
        if not isinstance(evidence, list) or len(evidence) > 240:
            raise ValueError("expected at most 240 paired endpoint entries")
        expected = {
            (split, *key)
            for split in ("development", "heldout")
            for key in cases(spec, parent, split)
        }
        for row in evidence:
            if (
                not isinstance(row, dict)
                or set(row)
                != {
                    "split",
                    "scenario",
                    "seed",
                    "condition",
                    "endpoints",
                }
                or type(row["seed"]) is not int
            ):
                raise ValueError("invalid endpoint entry fields or seed")
            key = (row["split"], row["scenario"], row["seed"], row["condition"])
            if key not in expected or key in indexed:
                raise ValueError("unexpected or duplicate paired endpoint entry")
            if not isinstance(row["endpoints"], dict) or set(row["endpoints"]) != {
                "baseline",
                "gate_off",
            }:
                raise ValueError("both fixed variants are required")
            for values in row["endpoints"].values():
                validate_endpoints(values)
            indexed[key] = row["endpoints"]
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        invalid = str(exc)
    splits = [_split_rules(indexed, split, spec, parent) for split in ("development", "heldout")]
    if invalid or any(not s["complete"] or not s["adequate_challenge"] for s in splits):
        classification, reason = (
            "inconclusive",
            "invalid/incomplete evidence or inadequate challenge",
        )
    elif any(s["regressions"] for s in splits):
        classification, reason = "failure", "at least one per-case non-regression gate failed"
    elif all(s["all_endpoints_identical"] for s in splits):
        classification, reason = "no_effect", "all 37 endpoints identical in every paired case"
    elif any(not s["benefit_margin_met"] for s in splits):
        classification, reason = "failure", "nonzero effect does not meet both improvement margins"
    else:
        classification, reason = "pass", "both splits meet the registered numerical screening rules"
    result = {
        "format": "visiontrack.box-gate-numerical-rules/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "classification": classification,
        "reason": reason,
        "invalid_evidence": invalid,
        "splits": splits,
        "provenance_verified_by_rules": False,
        "tracker_execution_established_by_rules": False,
        "production_change_authorized": False,
        "cpp_port_authorized": False,
        "limitations": [
            "Caller-supplied endpoints only; replay/source/input evidence is verified separately.",
            "Pass is a bounded synthetic numerical screen, not real-world accuracy "
            "or deployment approval.",
            "Seed means describe repeated noise, not independent camera sites "
            "or confidence intervals.",
        ],
    }
    result["rules_sha256"] = _sha(result)
    return result
