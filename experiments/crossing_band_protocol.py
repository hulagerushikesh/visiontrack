"""Read-only prospective counting registration; no scene generation or replay.

This verifies reviewed definitions, not a future execution harness or its
results. Parent protocols are read as definitions, never as held-out evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from experiments.box_gate_protocol import INHERITED
from experiments.box_gate_protocol import load_registration as load_box_registration
from experiments.traffic_protocol import ROOT, _read_bounded, _reject_constant, _unique_pairs

ARTIFACTS = (
    "experiments/crossing_band_protocol_v1.json",
    "docs/CROSSING_BAND_PROTOCOL.md",
)
LOCK = "experiments/crossing_band_protocol_v1.sha256"
VARIANTS = [
    {"id": "legacy", "tracker_config_patch": {},
     "counter": "first_line_arrival_per_id_direction"},
    {"id": "band", "tracker_config_patch": {}, "counter": "band_confirmed_line_arrival",
     "half_width_world_units": 0.25},
]
FALSE_FLAGS = (
    "study_outcomes_observed_at_registration", "random_observations_generated_at_registration",
    "new_tracker_runs_at_registration", "implementation_harness_frozen", "tuning_allowed",
    "consumed_heldout_reuse_allowed", "production_default_change_authorized",
    "cpp_port_authorized", "real_data_claims_allowed",
)


def _validate_design(spec: dict, parent: dict) -> None:
    if spec.get("variants") != VARIANTS:
        raise ValueError("counting-only variants must leave both tracker configurations unchanged")
    rules = spec.get("candidate_rules", {})
    if (rules.get("line_world_y") != 10.0
            or rules.get("half_width_world_units") != 0.25
            or rules.get("dwell_frames") != 0
            or rules.get("smoothing") is not False
            or rules.get("truth_assistance") is not False):
        raise ValueError("registered band intervention differs")
    policy = spec.get("execution_policy", {})
    if (any(policy.get(key) is not False for key in FALSE_FLAGS)
            or policy.get("authored_unit_diagrams_allowed") is not True
            or policy.get("development_before_new_heldout_freeze") is not True):
        raise ValueError("registration scope flags differ")
    evaluation = spec.get("evaluation", {})
    if (evaluation.get("minimum_baseline_primary") != 1.0
            or evaluation.get("minimum_qualifying_scenarios_per_split") != 2
            or evaluation.get("minimum_absolute_reduction") != 0.5
            or evaluation.get("minimum_relative_reduction") != 0.25
            or evaluation.get("maximum_confirmation_delay_frames") != 15.0
            or evaluation.get("per_paired_case_nonincrease") != [
                "missed_events", "extra_events", "event_error", "absolute_window_count_error",
                "emission_window_count_error",
            ]):
        raise ValueError("registered safety/benefit margins differ")
    if spec.get("grid") != {
        "input_cases_per_split": 240,
        "counter_views_per_split": 480,
        "tracker_passes_per_input": 3,
        "tracker_passes_per_split": 720,
        "pass_order": ["fresh", "reset", "independent_fresh"],
        "counter_order": ["legacy", "band"],
        "ordering": "registered scenario, seed, condition, pass, counter order",
        "pairing": "one immutable public-row vector per tracker pass, projected identically "
                   "and consumed by both counters; not two tracker variants",
    }:
        raise ValueError("registered shared-row grid differs")
    splits = spec.get("splits", {})
    scenarios = spec.get("scenarios", {})
    if set(splits) != {"development", "heldout"} or not isinstance(scenarios, dict):
        raise ValueError("exactly two new splits required")
    used_seeds = {seed for split in parent["splits"].values() for seed in split["seeds"]}
    used_names = set(parent["scenarios"])
    new_names = set()
    for split_name, first_seed in (("development", 6001), ("heldout", 8001)):
        split = splits[split_name]
        seeds, names = split.get("seeds"), split.get("scenarios")
        if (seeds != list(range(first_seed, first_seed + 10))
                or any(type(seed) is not int for seed in seeds)
                or set(seeds) & used_seeds):
            raise ValueError("fresh disjoint registered seeds required")
        if (not isinstance(names, list) or len(names) != 6
                or any(not isinstance(name, str) for name in names)
                or len(set(names)) != 6 or set(names) & used_names):
            raise ValueError("six distinct new paths per split required")
        used_seeds.update(seeds)
        used_names.update(names)
        new_names.update(names)
        for name in names:
            waypoints = scenarios.get(name)
            if not isinstance(waypoints, list) or not 2 <= len(waypoints) <= 5:
                raise ValueError("bounded piecewise path required")
            previous_frame = -1
            for point in waypoints:
                if (not isinstance(point, list) or len(point) != 3
                        or type(point[0]) is not int
                        or not previous_frame < point[0] < 300
                        or any(type(v) not in (int, float) or not math.isfinite(v)
                               for v in point[1:])
                        or not -6 <= point[1] <= 6 or not 0 <= point[2] <= 20):
                    raise ValueError("invalid frame/coordinate in registered path")
                previous_frame = point[0]
            if waypoints[0][0] != 0 or waypoints[-1][0] != 299:
                raise ValueError("path must span the entire 300-frame grid")
    if new_names != set(scenarios):
        raise ValueError("unregistered or missing scenario")


def load_registration(root: Path = ROOT) -> tuple[dict, dict[str, str]]:
    """Accept exact locked definitions only; injectable root is for unit tests."""
    lines = _read_bounded(root / LOCK).decode("ascii").splitlines()
    if len(lines) != len(ARTIFACTS):
        raise ValueError("registration lock must contain exactly two artifacts")
    hashes, payloads = {}, {}
    for line, expected in zip(lines, ARTIFACTS, strict=True):
        digest, separator, name = line.partition("  ")
        if separator != "  " or name != expected:
            raise ValueError("unexpected registration lock path or order")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid registration SHA-256")
        data = _read_bounded(root / expected)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"registered artifact changed: {expected}")
        hashes[name], payloads[name] = digest, data
    spec = json.loads(
        payloads[ARTIFACTS[0]], object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
    )
    if not isinstance(spec, dict) or spec.get("protocol_id") != "visiontrack.crossing-band/v1":
        raise ValueError("unexpected registration ID")
    parent, parent_hashes = load_box_registration(root)
    if spec.get("parent_artifacts") != parent_hashes:
        raise ValueError("registration parent bytes differ")
    if (spec.get("baseline_revision") != parent["baseline_revision"]
            or spec.get("inherit_unchanged") != list(INHERITED)):
        raise ValueError("registration baseline/inheritance differs")
    _validate_design(spec, parent)
    return spec, {**parent_hashes, **hashes}


def main() -> int:
    try:
        spec, hashes = load_registration()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Registration integrity check failed: {exc}")
        return 2
    print(spec["protocol_id"])
    for name, digest in hashes.items():
        print(f"{digest}  {name}")
    print("Registration verified; no noisy inputs, tracker runs or research outcomes.")
    print("This preflight executes no counters and does not freeze the replay/held-out harness.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
