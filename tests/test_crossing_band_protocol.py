"""Prospective definitions/ideal geometry only, not noisy tracking outcomes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pytest

from experiments import crossing_band_protocol as registration
from experiments.box_gate_protocol import ARTIFACTS as BOX_ARTIFACTS
from experiments.box_gate_protocol import LOCK as BOX_LOCK
from experiments.box_gate_protocol import load_registration as load_box_registration
from experiments.traffic_crossing import AnchorSample, extract_crossings
from experiments.traffic_protocol import ARTIFACTS as TRAFFIC_ARTIFACTS
from experiments.traffic_protocol import MAX_BYTES, ROOT, load_frozen_protocol
from visiontrack.tracking.config import TrackerConfig


def _points(waypoints):
    """Deterministic ideal interpolation, not generated observation inputs."""
    frames = np.arange(300)
    knots = np.array(waypoints, dtype=np.float64)
    return np.column_stack([
        np.interp(frames, knots[:, 0], knots[:, 1]),
        np.interp(frames, knots[:, 0], knots[:, 2]),
    ])


def test_preflight_never_generates_noise_runs_tracker_or_writes(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("preflight must not generate observations, run a tracker or write")

    monkeypatch.setattr(np.random, "PCG64", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    from pathlib import Path

    original_open = Path.open
    seen = set()
    allowed = {
        *TRAFFIC_ARTIFACTS, "experiments/traffic_protocol_v1.sha256",
        *BOX_ARTIFACTS, BOX_LOCK, *registration.ARTIFACTS, registration.LOCK,
    }

    def readonly_definitions(path, mode="r", *args, **kwargs):
        assert mode == "rb", "preflight may only read registered definition bytes"
        name = path.relative_to(ROOT).as_posix()
        assert name in allowed, "must not read raw outcomes or held-out evidence"
        seen.add(name)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", readonly_definitions)
    assert registration.main() == 0
    assert seen == allowed
    assert "no noisy inputs, tracker runs or research outcomes" in capsys.readouterr().out


def test_shared_rows_unchanged_tracker_and_independent_future_scope():
    spec, hashes = registration.load_registration()
    parent, parent_hashes = load_box_registration()
    traffic, _ = load_frozen_protocol()
    assert set(hashes) == set(parent_hashes) | set(registration.ARTIFACTS)
    assert spec["parent_artifacts"] == parent_hashes
    assert spec["baseline_revision"] == parent["baseline_revision"]
    config = traffic["tracker_config"]
    assert asdict(TrackerConfig(**config)) == config
    assert config["use_mahalanobis_gating"] is True
    for variant in spec["variants"]:
        assert variant["tracker_config_patch"] == {}
        assert asdict(TrackerConfig(**{**config, **variant["tracker_config_patch"]})) == config
    assert all(spec["execution_policy"][key] is False for key in registration.FALSE_FLAGS)
    assert "results" not in spec
    assert spec["candidate_rules"]["half_width_world_units"] == 0.25
    assert spec["evaluation"]["maximum_confirmation_delay_frames"] == 15.0
    assert spec["evaluation"]["decision_order"][1] == "any_safety_or_delay_regression:failure"


def test_fresh_full_grid_and_paths_not_just_new_noise_seeds():
    spec, _ = registration.load_registration()
    parents = [load_frozen_protocol()[0], load_box_registration()[0]]
    used_seeds = {
        seed for parent in parents for split in parent["splits"].values() for seed in split["seeds"]
    }
    used_paths = [
        np.column_stack([
            np.linspace(obj["start"][axis], obj["end"][axis], 300) for axis in (0, 1)
        ])
        for parent in parents for objects in parent["scenarios"].values() for obj in objects
    ]
    all_paths = []
    for split in spec["splits"].values():
        assert len(split["seeds"]) == 10 and len(split["scenarios"]) == 6
        assert not used_seeds.intersection(split["seeds"])
        used_seeds.update(split["seeds"])
        cases = len(split["seeds"]) * len(split["scenarios"]) * 4
        assert cases == spec["grid"]["input_cases_per_split"] == 240
        assert cases * 2 == spec["grid"]["counter_views_per_split"] == 480
        assert cases * 3 == spec["grid"]["tracker_passes_per_split"] == 720
        for name in split["scenarios"]:
            points = _points(spec["scenarios"][name])
            assert not any(np.array_equal(points, old) for old in used_paths + all_paths)
            all_paths.append(points)


@pytest.mark.parametrize("projection", ["affine", "perspective"])
def test_every_ideal_path_and_worst_edge_bounds_fit_both_projections(projection):
    spec, _ = registration.load_registration()
    parent, _ = load_frozen_protocol()
    matrix = np.array(parent["projection"][projection], dtype=np.float64)
    inverse = np.linalg.inv(matrix)
    for waypoints in spec["scenarios"].values():
        points = _points(waypoints)
        assert np.all((points[:, 0] >= -6) & (points[:, 0] <= 6))
        assert np.all((points[:, 1] >= 0) & (points[:, 1] <= 20))
        mapped = np.column_stack((points, np.ones(300))) @ matrix.T
        q = mapped[:, 2]
        assert np.all(q > parent["projection"]["min_positive_denominator"])
        uv = mapped[:, :2] / q[:, None]
        back = np.column_stack((uv, np.ones(300))) @ inverse.T
        np.testing.assert_allclose(back[:, :2] / back[:, 2, None], points, atol=1e-9, rtol=0)
        width, height = 36 / q, 170 / q
        # Pulses shrink boxes inward; these bound the larger, jittered ideal boxes.
        assert np.all(uv[:, 0] - 0.52 * width > 0)
        assert np.all(uv[:, 0] + 0.52 * width < 1280)
        assert np.all(uv[:, 1] - 1.02 * height > 0)
        assert np.all(uv[:, 1] + 0.02 * height < 720)


@pytest.mark.parametrize("split_name", ["development", "heldout"])
def test_truth_keeps_genuine_shallow_start_end_passages_and_no_crossing_controls(split_name):
    """Ideal truth is defined before outcomes; never filter it through the band."""
    spec, _ = registration.load_registration()
    names = spec["splits"][split_name]["scenarios"]
    expected_counts = [1, 0, 2, 2, 1, 1]
    for name, expected in zip(names, expected_counts, strict=True):
        points = _points(spec["scenarios"][name])
        samples = [AnchorSample(frame, 1, *point) for frame, point in enumerate(points)]
        events = extract_crossings(samples)
        assert len(events) == expected <= 2
        assert all(0 < event.frame_time < 299 and -6 <= event.x < 6 for event in events)
    start, end = _points(spec["scenarios"][names[4]]), _points(spec["scenarios"][names[5]])
    assert 9.75 < start[0, 1] < 10.25
    assert 9.75 < end[-1, 1] < 10.25
    shallow = _points(spec["scenarios"][names[2]])[:, 1]
    assert (shallow.max() < 10.25 if split_name == "development" else shallow.min() > 9.75)


def _copy_registration(destination):
    for name in (
        *TRAFFIC_ARTIFACTS, "experiments/traffic_protocol_v1.sha256",
        *BOX_ARTIFACTS, BOX_LOCK, *registration.ARTIFACTS, registration.LOCK,
    ):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())


def _replace_json(destination, data):
    path = destination / registration.ARTIFACTS[0]
    path.write_bytes(data)
    lock = destination / registration.LOCK
    lines = lock.read_text().splitlines()
    lines[0] = hashlib.sha256(data).hexdigest() + "  " + registration.ARTIFACTS[0]
    lock.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("name", (*registration.ARTIFACTS, *TRAFFIC_ARTIFACTS, *BOX_ARTIFACTS))
def test_artifact_drift_does_not_amend_parent_protocols(tmp_path, name):
    _copy_registration(tmp_path)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact changed"):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize("data", [b"{}", b"[]", b'{"a":1,"a":2}', b'{"a":NaN}'])
def test_invalid_json_is_rejected_even_if_new_artifact_is_resigned(tmp_path, data):
    _copy_registration(tmp_path)
    _replace_json(tmp_path, data)
    with pytest.raises(ValueError):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize("mutation", [
    lambda s: s["variants"][1]["tracker_config_patch"].update(use_mahalanobis_gating=False),
    lambda s: s["candidate_rules"].update(half_width_world_units=0.5),
    lambda s: s["execution_policy"].update(consumed_heldout_reuse_allowed=True),
    lambda s: s["evaluation"].update(maximum_confirmation_delay_frames=30),
    lambda s: s["grid"].update(tracker_passes_per_split=1440),
    lambda s: s["splits"]["development"]["seeds"].__setitem__(0, 1001),
    lambda s: s["splits"]["heldout"]["scenarios"].__setitem__(0, "band_dev_through"),
    lambda s: s["scenarios"]["band_dev_through"][0].__setitem__(0, True),
    lambda s: s["scenarios"]["band_dev_through"][0].__setitem__(1, float("inf")),
    lambda s: s["scenarios"]["band_dev_through"][-1].__setitem__(0, 298),
    lambda s: s["scenarios"].update(extra=[[0, 0, 1], [299, 0, 19]]),
    lambda s: s["parent_artifacts"].clear(),
    lambda s: s.update(baseline_revision="0" * 40),
])
def test_scope_and_shape_drift_is_rejected_even_after_resigning(tmp_path, mutation):
    _copy_registration(tmp_path)
    spec = json.loads((ROOT / registration.ARTIFACTS[0]).read_bytes())
    mutation(spec)
    _replace_json(tmp_path, json.dumps(spec).encode())
    with pytest.raises(ValueError):
        registration.load_registration(tmp_path)


@pytest.mark.parametrize("content", ["", "bad\n", "0" * 64 + "  ../other\n" + "bad\n"])
def test_incomplete_or_unexpected_lock_is_rejected(tmp_path, content):
    _copy_registration(tmp_path)
    (tmp_path / registration.LOCK).write_text(content)
    with pytest.raises(ValueError):
        registration.load_registration(tmp_path)


def test_oversized_definition_and_cli_failure_are_visible(tmp_path, monkeypatch, capsys):
    _copy_registration(tmp_path)
    (tmp_path / registration.ARTIFACTS[0]).write_bytes(b" " * (MAX_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        registration.load_registration(tmp_path)

    def invalid():
        raise ValueError("injected integrity failure")

    monkeypatch.setattr(registration, "load_registration", invalid)
    assert registration.main() == 2
    assert "injected integrity failure" in capsys.readouterr().out
