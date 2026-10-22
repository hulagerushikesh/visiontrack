"""New development input checks only; no new tracker or held-out comparisons."""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, fields, replace

import numpy as np
import pytest

from experiments import box_gate_scene
from experiments.box_gate_protocol import load_registration
from experiments.box_gate_scene import generate_inputs
from experiments.traffic_scene import SceneInputs, validate_boxes

CONDITIONS = ("control", "perspective_only", "box_error_only", "combined")
SCENARIOS = ("gate_dev_solo", "gate_dev_separated", "gate_dev_close")


@pytest.fixture(autouse=True)
def no_tracker_or_old_generator(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("new inputs must not execute a tracker or alter/relabel old generated inputs")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)


def _scene(condition="control", scenario="gate_dev_solo", seed=2001):
    return generate_inputs(split="development", scenario=scenario, seed=seed, condition=condition)


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("seed", range(2001, 2011))
@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_registered_development_input_without_tracking(scenario, seed, condition):
    scene = _scene(condition, scenario, seed)
    count = 1 if scenario == "gate_dev_solo" else 2
    assert scene.object_ids == tuple(range(1, count + 1))
    assert not isinstance(scene, SceneInputs)
    assert scene.protocol_id == "visiontrack.box-gate-ablation/v1"
    assert scene.world_contacts.shape == (300, count, 2)
    assert scene.observed_boxes.shape == scene.edge_draws.shape == (300, count, 4)
    np.testing.assert_array_equal(scene.frames, np.arange(300))
    np.testing.assert_array_equal(scene.timestamps, np.arange(300) / 30)
    for field in fields(scene):
        value = getattr(scene, field.name)
        if isinstance(value, np.ndarray):
            assert value.dtype == np.dtype("<f8")
            assert np.isfinite(value).all()
            assert not value.flags.writeable
    validate_boxes(scene.ideal_boxes, width=1280, height=720)
    validate_boxes(scene.observed_boxes, width=1280, height=720)
    manifest = scene.manifest()
    assert manifest["tracker_executed"] is False
    assert manifest["frame_count"] == 300
    assert manifest["detections"]["feature"] is None


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_four_conditions_are_paired_and_clean_projection_pairs_share_boxes(scenario):
    scenes = {name: _scene(name, scenario) for name in CONDITIONS}
    manifests = {name: scene.manifest() for name, scene in scenes.items()}
    for scene in scenes.values():
        np.testing.assert_array_equal(scene.world_contacts, scenes["control"].world_contacts)
        np.testing.assert_array_equal(scene.edge_draws, scenes["control"].edge_draws)
    for key in ("world_truth", "random_draws"):
        assert len({m["sha256"][key] for m in manifests.values()}) == 1
    for clean, noisy in (("control", "box_error_only"), ("perspective_only", "combined")):
        np.testing.assert_array_equal(scenes[clean].ideal_boxes, scenes[noisy].ideal_boxes)
        assert (
            manifests[clean]["sha256"]["ideal_truth"] == manifests[noisy]["sha256"]["ideal_truth"]
        )
        np.testing.assert_allclose(
            scenes[clean].observed_bottom_world, scenes[clean].world_contacts, rtol=0, atol=1e-9,
        )
    assert len({m["detections"]["detection_stream_sha256"] for m in manifests.values()}) == 4


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_scalar_oracle_checks_path_projection_rng_and_pulse_boundaries(scenario, condition):
    """Independent per-frame/object oracle, not a call to generator helpers."""
    scene = _scene(condition, scenario)
    spec, _ = load_registration()
    rng = np.random.Generator(np.random.PCG64(2001))
    selected_frames = {0, 1, 134, 135, 164, 165, 209, 210, 239, 240, 299}
    for frame in range(300):
        for column, obj in enumerate(spec["scenarios"][scenario]):
            draws = rng.uniform(-1, 1, 4)
            np.testing.assert_array_equal(scene.edge_draws[frame, column], draws)
            if frame not in selected_frames:
                continue
            start, end = obj["start"], obj["end"]
            x = start[0] + (end[0] - start[0]) * frame / 299
            y = start[1] + (end[1] - start[1]) * frame / 299
            perspective = condition in ("perspective_only", "combined")
            q = 1 + 0.05 * y if perspective else 1
            u = (60 * x + 32 * y + 640) / q if perspective else 60 * x + 640
            v = 650 / q if perspective else 650 - 16.25 * y
            width, height = 36 / q, 170 / q
            ideal = [u - width / 2, v - height, u + width / 2, v]
            expected = list(ideal)
            if condition in ("box_error_only", "combined"):
                for edge, size in enumerate((width, height, width, height)):
                    expected[edge] += 0.02 * draws[edge] * size
                if 135 <= frame < 165:
                    expected[3] -= 0.35 * height
                if 210 <= frame < 240:
                    expected[1] += 0.35 * height
            np.testing.assert_array_equal(scene.world_contacts[frame, column], [x, y])
            np.testing.assert_allclose(
                scene.pixel_contacts[frame, column], [u, v], rtol=0, atol=1e-12,
            )
            np.testing.assert_allclose(scene.ideal_boxes[frame, column], ideal, rtol=0, atol=1e-12)
            np.testing.assert_allclose(
                scene.observed_boxes[frame, column], expected, rtol=0, atol=1e-12,
            )


def test_same_input_for_both_future_variants_and_immutable_ownership():
    baseline_input, candidate_input = _scene("combined"), _scene("combined")
    assert baseline_input.manifest() == candidate_input.manifest()
    assert baseline_input.detection_manifest() == candidate_input.detection_manifest()
    assert not np.shares_memory(baseline_input.observed_boxes, candidate_input.observed_boxes)
    for field in fields(baseline_input):
        value = getattr(baseline_input, field.name)
        if isinstance(value, np.ndarray):
            with pytest.raises(ValueError):
                value.setflags(write=True)
            with pytest.raises(ValueError):
                value.flat[0] = 0
    with pytest.raises(FrozenInstanceError):
        baseline_input.seed = 4001
    with pytest.raises(TypeError, match="variant"):
        generate_inputs(split="development", scenario=SCENARIOS[0], seed=2001,
                        condition="control", variant="gate_off")


def test_detector_fingerprint_excludes_reference_labels_but_binds_real_inputs():
    scene = _scene("combined", "gate_dev_close")
    receipt = scene.detection_manifest()
    assert set(receipt) == {
        "format", "frame_count", "detections_per_frame", "score", "class_id",
        "feature", "arrays_sha256", "detection_stream_sha256",
    }
    assert receipt["score"] == 0.9 and receipt["class_id"] == 0 and receipt["feature"] is None
    relabelled = replace(scene, object_ids=(200, 300), world_contacts=scene.world_contacts + 1)
    assert relabelled.detection_manifest() == receipt
    assert (
        relabelled.manifest()["sha256"]["world_truth"] != scene.manifest()["sha256"]["world_truth"]
    )
    for altered in (
        replace(scene, detection_score=0.8), replace(scene, detection_class_id=1),
        replace(scene, observed_boxes=scene.observed_boxes + 0.01),
        replace(scene, frames=scene.frames + 1),
    ):
        assert (
            altered.detection_manifest()["detection_stream_sha256"]
            != receipt["detection_stream_sha256"]
        )


def _json_digest_without(payload, key):
    return hashlib.sha256(json.dumps(
        {name: value for name, value in payload.items() if name != key},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def test_manifest_hashes_are_self_excluding_and_fresh():
    scene = _scene("combined")
    manifest = scene.manifest()
    assert manifest["input_sha256"] == _json_digest_without(manifest, "input_sha256")
    detections = manifest["detections"]
    assert detections["detection_stream_sha256"] == _json_digest_without(
        detections, "detection_stream_sha256",
    )
    original = scene.manifest()
    manifest["object_ids"].append(100)
    manifest["sha256"].clear()
    manifest["protocol_hashes"].clear()
    manifest["detections"].clear()
    assert scene.manifest() == original


def test_local_noise_does_not_touch_global_random_state_or_truth(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("generator must use only its local registered PCG64 stream")

    monkeypatch.setattr(np.random, "seed", forbidden)
    monkeypatch.setattr(np.random, "uniform", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    before = np.random.get_state()
    first, second = _scene("combined"), _scene("combined", seed=2002)
    after = np.random.get_state()
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])
    np.testing.assert_array_equal(first.world_contacts, second.world_contacts)
    np.testing.assert_array_equal(first.ideal_boxes, second.ideal_boxes)
    assert not np.array_equal(first.edge_draws, second.edge_draws)
    assert not np.array_equal(first.observed_boxes, second.observed_boxes)


@pytest.mark.parametrize("override", [
    {"split": "unknown"}, {"scenario": "solo"}, {"scenario": "gate_test_solo"},
    {"seed": 101}, {"seed": 1001}, {"seed": 4001}, {"seed": True}, {"seed": 2001.0},
    {"seed": np.int64(2001)}, {"condition": "unknown"},
    {"split": "heldout", "scenario": "gate_test_solo", "seed": 2001},
])
def test_unregistered_selectors_fail_before_rng(override, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid selector must fail before generating any observations")

    monkeypatch.setattr(np.random, "PCG64", forbidden)
    selectors = dict(split="development", scenario=SCENARIOS[0], seed=2001, condition="control")
    with pytest.raises(ValueError, match="registered"):
        generate_inputs(**{**selectors, **override})


def test_parent_preflight_drift_is_not_silently_used(monkeypatch):
    original = box_gate_scene.load_frozen_protocol

    def changed_parent():
        spec, hashes = original()
        return spec, dict.fromkeys(hashes, "0" * 64)

    monkeypatch.setattr(box_gate_scene, "load_frozen_protocol", changed_parent)
    with pytest.raises(ValueError, match="parent recipe drift"):
        _scene()


def test_registration_failure_precedes_random_input_generation(monkeypatch):
    def invalid():
        raise ValueError("registered artifact changed")

    def forbidden(*args, **kwargs):
        pytest.fail("registration failure must stop before RNG")

    monkeypatch.setattr(box_gate_scene, "load_registration", invalid)
    monkeypatch.setattr(np.random, "PCG64", forbidden)
    with pytest.raises(ValueError, match="artifact changed"):
        _scene()
