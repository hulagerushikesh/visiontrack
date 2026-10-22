"""Prospective design validation only; no ablation outputs or random inputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pytest

from experiments import box_gate_protocol as registration
from experiments.traffic_protocol import ARTIFACTS as PARENT_ARTIFACTS
from experiments.traffic_protocol import MAX_BYTES, ROOT, load_frozen_protocol
from visiontrack.tracking.config import TrackerConfig


def test_registration_preflight_does_not_execute_inputs_or_tracker(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("registration must not construct random inputs or a tracker")

    monkeypatch.setattr(np.random, "PCG64", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    assert registration.main() == 0
    output = capsys.readouterr().out
    assert "no new random inputs, tracker runs or results" in output
    assert "not yet frozen" in output


def test_exact_one_switch_parent_and_registered_decision_margins():
    spec, hashes = registration.load_registration()
    parent, parent_hashes = load_frozen_protocol()
    assert spec["parent_artifacts"] == parent_hashes
    assert set(hashes) == set(PARENT_ARTIFACTS + registration.ARTIFACTS)
    baseline = asdict(TrackerConfig(**parent["tracker_config"]))
    assert baseline == parent["tracker_config"]
    candidate = asdict(TrackerConfig(**{**baseline, **spec["variants"][1]["config_patch"]}))
    assert {key for key in baseline if baseline[key] != candidate[key]} == {
        "use_mahalanobis_gating"
    }
    assert baseline["use_mahalanobis_gating"] is True
    assert candidate["use_mahalanobis_gating"] is False
    evaluation = spec["evaluation"]
    assert evaluation["minimum_baseline_id_switches_per_object"] == 0.5
    assert evaluation["minimum_relative_id_switch_reduction"] == 0.25
    assert evaluation["minimum_absolute_id_switch_reduction_per_object"] == 0.5
    assert evaluation["minimum_improved_scenarios_per_split"] == 2
    assert evaluation["per_paired_case_nonincrease"] == [
        "id_switches", "missed_object_frames", "false_positive_rows",
        "bottom_centre_missed_plus_extra_events", "bottom_centre_absolute_window_count_error",
    ]
    assert evaluation["decision_precedence"] == ["inconclusive", "failure", "no_effect", "pass"]
    assert evaluation["retain_all_parent_37_endpoints"] is True
    policy = spec["execution_policy"]
    for key in (
        "comparative_outcomes_observed_at_registration",
        "random_observation_inputs_generated_at_registration",
        "new_tracker_runs_at_registration", "implementation_harness_frozen", "tuning_allowed",
        "old_v1_heldout_reuse_as_untouched_allowed", "real_data_claims_allowed",
        "production_default_change_authorized", "cpp_port_authorized",
    ):
        assert policy[key] is False
    assert "results" not in spec


def test_new_splits_and_case_counts_are_disjoint_from_opened_v1():
    spec, _ = registration.load_registration()
    parent, _ = load_frozen_protocol()
    old_seeds = {seed for split in parent["splits"].values() for seed in split["seeds"]}
    old_paths = {
        json.dumps(objects, sort_keys=True) for objects in parent["scenarios"].values()
    }
    used_seeds, used_scenarios, new_paths = set(), set(), set()
    for split in spec["splits"].values():
        seeds, scenarios = split["seeds"], split["scenarios"]
        assert len(seeds) == len(set(seeds)) == 10
        assert len(scenarios) == len(set(scenarios)) == 3
        assert not used_seeds.intersection(seeds) and not old_seeds.intersection(seeds)
        assert not used_scenarios.intersection(scenarios)
        assert not set(parent["scenarios"]).intersection(scenarios)
        used_seeds.update(seeds)
        used_scenarios.update(scenarios)
        cases = len(seeds) * len(scenarios) * len(parent["conditions"])
        assert cases == spec["grid"]["paired_cases_per_split"] == 120
        assert cases * len(spec["variants"]) == spec["grid"]["variant_runs_per_split"] == 240
        for name in scenarios:
            path = json.dumps(spec["scenarios"][name], sort_keys=True)
            assert path not in old_paths and path not in new_paths
            new_paths.add(path)
    assert used_scenarios == set(spec["scenarios"])
    assert spec["grid"]["passes_per_variant"] == 3
    assert spec["grid"]["variant_order"] == ["baseline", "gate_off"]


@pytest.mark.parametrize("projection_name", ["affine", "perspective"])
def test_new_deterministic_geometry_is_valid_without_random_generation(projection_name):
    """Analytic bounds, not generated SceneInputs or tracking outcomes."""
    spec, _ = registration.load_registration()
    parent, _ = load_frozen_protocol()
    grid, ideal = parent["frame_grid"], parent["ideal_box"]
    matrix = np.array(parent["projection"][projection_name], dtype=float)
    inverse = np.linalg.inv(matrix)
    fractions = np.arange(grid["frames"]) / (grid["frames"] - 1)
    phases = {"development": set(), "heldout": set()}
    for split_name, split in spec["splits"].items():
        for name in split["scenarios"]:
            objects = spec["scenarios"][name]
            assert 1 <= len(objects) <= 2  # existing bounded crossing matcher capacity
            assert [obj["object_id"] for obj in objects] == list(range(1, len(objects) + 1))
            for obj in objects:
                start, end = np.array(obj["start"]), np.array(obj["end"])
                points = start + fractions[:, None] * (end - start)
                assert np.all(np.abs(points[:, 0]) <= 6)
                assert np.all((points[:, 1] >= 0) & (points[:, 1] <= 20))
                mapped = np.column_stack((points, np.ones(grid["frames"]))) @ matrix.T
                q = mapped[:, 2]
                assert np.all(q > parent["projection"]["min_positive_denominator"])
                uv = mapped[:, :2] / q[:, None]
                back = np.column_stack((uv, np.ones(grid["frames"]))) @ inverse.T
                np.testing.assert_allclose(
                    back[:, :2] / back[:, 2, None], points, atol=1e-9, rtol=0,
                )
                w = ideal["width_scale"] * ideal["world_width"] / q
                h = ideal["height_scale"] * ideal["world_height"] / q
                jitter = parent["observation_error"]["edge_jitter_fraction"]
                assert np.all(uv[:, 0] - (0.5 + jitter) * w > 0)
                assert np.all(uv[:, 0] + (0.5 + jitter) * w < grid["width"])
                assert np.all(uv[:, 1] - (1 + jitter) * h > 0)
                assert np.all(uv[:, 1] + jitter * h < grid["height"])
                crossing = (10 - start[1]) / (end[1] - start[1]) * (grid["frames"] - 1)
                assert 0 < crossing < 299
                phases[split_name].add("before" if crossing < 135 else
                                       "during" if crossing < 165 else "after")
    assert all(values == {"before", "during", "after"} for values in phases.values())


def _copy_registration(destination):
    for name in (
        *PARENT_ARTIFACTS, "experiments/traffic_protocol_v1.sha256",
        *registration.ARTIFACTS, registration.LOCK,
    ):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())


def _replace_json(destination, payload):
    path = destination / registration.ARTIFACTS[0]
    path.write_bytes(payload)
    lock = destination / registration.LOCK
    lines = lock.read_text().splitlines()
    lines[0] = hashlib.sha256(payload).hexdigest() + "  " + registration.ARTIFACTS[0]
    lock.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("name", (*registration.ARTIFACTS, *PARENT_ARTIFACTS))
def test_new_and_parent_artifact_drift_is_rejected(tmp_path, name):
    _copy_registration(tmp_path)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact changed"):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize("content", ["", "bad\n", "0" * 64 + "  ../other\n" + "bad\n"])
def test_lock_cannot_redirect_paths(tmp_path, content):
    _copy_registration(tmp_path)
    (tmp_path / registration.LOCK).write_text(content)
    with pytest.raises(ValueError, match="lock"):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize(
    "payload, message",
    [(b'{"a":1,"a":2}', "duplicate"), (b'{"a":NaN}', "nonfinite"),
     (b"[]", "registration ID"), (b"{", "property name")],
)
def test_invalid_json_is_rejected_even_with_updated_checksum(tmp_path, payload, message):
    _copy_registration(tmp_path)
    _replace_json(tmp_path, payload)
    with pytest.raises(ValueError, match=message):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize(
    "field, replacement, message",
    [("parent_artifacts", {}, "parent bytes"), ("baseline_revision", "other", "baseline"),
     ("inherit_unchanged", [], "inheritance"), ("variants", [], "one gate")],
)
def test_registration_cannot_silently_broaden_comparator(tmp_path, field, replacement, message):
    _copy_registration(tmp_path)
    spec, _ = registration.load_registration()
    spec[field] = replacement
    _replace_json(tmp_path, json.dumps(spec).encode())
    with pytest.raises(ValueError, match=message):
        registration.load_registration(tmp_path)


def test_bounded_reads_and_cli_failure(tmp_path, monkeypatch, capsys):
    _copy_registration(tmp_path)
    (tmp_path / registration.ARTIFACTS[0]).write_bytes(b" " * (MAX_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        registration.load_registration(tmp_path)

    def invalid_registration():
        raise ValueError("invalid frozen registration")

    monkeypatch.setattr(registration, "load_registration", invalid_registration)
    assert registration.main() == 2
    assert "integrity check failed" in capsys.readouterr().out
