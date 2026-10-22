"""Input-only mechanism checks. No tracker replay or held-out outcome access."""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, fields

import numpy as np
import pytest

from experiments import traffic_scene
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_scene import (
    GroundProjection,
    _digest_arrays,
    generate_scene,
    validate_boxes,
)

CONDITIONS = ("control", "perspective_only", "box_error_only", "combined")


def _scene(condition="control", scenario="opposing", seed=101):
    return generate_scene(split="development", scenario=scenario, seed=seed, condition=condition)


@pytest.mark.parametrize("scenario", ["solo", "opposing", "converging"])
@pytest.mark.parametrize("seed", range(101, 111))
@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_development_input_is_valid_without_tracking(scenario, seed, condition) -> None:
    scene = _scene(condition, scenario, seed)
    count = 1 if scenario == "solo" else 2
    assert scene.object_ids == tuple(range(1, count + 1))
    assert scene.world_contacts.shape == (300, count, 2)
    assert scene.observed_boxes.shape == (300, count, 4)
    assert scene.edge_draws.shape == (300, count, 4)
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


def test_generation_never_constructs_tracker_or_touches_global_rng(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("input generator cannot construct a tracker or use global RNG")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr(np.random, "seed", forbidden)
    monkeypatch.setattr(np.random, "uniform", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    before = np.random.get_state()
    _scene("combined")
    after = np.random.get_state()
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]


def test_all_four_conditions_share_exact_world_truth_and_draws() -> None:
    scenes = {condition: _scene(condition) for condition in CONDITIONS}
    base = scenes["control"]
    manifests = {name: scene.manifest() for name, scene in scenes.items()}
    for scene in scenes.values():
        np.testing.assert_array_equal(scene.world_contacts, base.world_contacts)
        np.testing.assert_array_equal(scene.edge_draws, base.edge_draws)
    for key in ("world_truth", "random_draws"):
        assert len({m["sha256"][key] for m in manifests.values()}) == 1
    for clean, noisy in (("control", "box_error_only"), ("perspective_only", "combined")):
        np.testing.assert_array_equal(scenes[clean].ideal_boxes, scenes[noisy].ideal_boxes)
        assert (
            manifests[clean]["sha256"]["ideal_truth"] == manifests[noisy]["sha256"]["ideal_truth"]
        )
    assert len({m["sha256"]["observations"] for m in manifests.values()}) == 4
    assert len({m["input_sha256"] for m in manifests.values()}) == 4


def test_noise_changes_measurements_not_truth() -> None:
    first, second = _scene("combined", seed=101), _scene("combined", seed=102)
    np.testing.assert_array_equal(first.ideal_boxes, second.ideal_boxes)
    np.testing.assert_array_equal(first.world_contacts, second.world_contacts)
    assert not np.array_equal(first.edge_draws, second.edge_draws)
    assert not np.array_equal(first.observed_boxes, second.observed_boxes)
    assert first.manifest()["sha256"]["world_truth"] == second.manifest()["sha256"]["world_truth"]


def test_draw_order_is_frame_then_object_id_then_edge_even_in_clean_condition() -> None:
    scene = _scene()
    rng = np.random.Generator(np.random.PCG64(101))
    expected = np.empty((300, 2, 4))
    for frame in range(300):
        for obj in range(2):
            expected[frame, obj] = rng.uniform(-1, 1, 4)
    np.testing.assert_array_equal(scene.edge_draws, expected)
    assert np.all((scene.edge_draws >= -1) & (scene.edge_draws < 1))


@pytest.mark.parametrize("condition", ["control", "perspective_only"])
def test_clean_observations_and_unperturbed_bottom_contact_agree(condition) -> None:
    scene = _scene(condition)
    np.testing.assert_array_equal(scene.observed_boxes, scene.ideal_boxes)
    np.testing.assert_allclose(
        scene.observed_bottom_centres, scene.pixel_contacts, rtol=0, atol=1e-12
    )
    np.testing.assert_allclose(scene.observed_bottom_world, scene.world_contacts, rtol=0, atol=1e-9)
    assert not np.allclose(scene.ideal_box_centres, scene.pixel_contacts)
    assert not np.allclose(scene.observed_centre_world, scene.world_contacts)


@pytest.mark.parametrize("condition", ["box_error_only", "combined"])
def test_box_errors_use_ideal_dimensions_and_exact_half_open_pulses(condition) -> None:
    scene = _scene(condition)
    # Use the specified ideal dimensions, not a subtract/reconstruct of rounded
    # box edges (which introduces sub-ULP discrepancies in the residual check).
    q = 1 + 0.05 * scene.world_contacts[..., 1] if condition == "combined" else 1
    size = np.empty_like(scene.world_contacts)
    size[..., 0], size[..., 1] = 36 / q, 170 / q
    jitter = 0.02 * scene.edge_draws * np.concatenate((size, size), axis=-1)
    # Oracle is edge-by-edge, independently of the generator's slice operation.
    expected = scene.ideal_boxes + jitter
    for frame in range(300):
        for obj in range(2):
            if 135 <= frame < 165:
                expected[frame, obj, 3] -= 0.35 * size[frame, obj, 1]
            if 210 <= frame < 240:
                expected[frame, obj, 1] += 0.35 * size[frame, obj, 1]
    np.testing.assert_array_equal(scene.observed_boxes, expected)
    residual = scene.observed_boxes - (scene.ideal_boxes + jitter)
    np.testing.assert_allclose(residual[:, :, [0, 2]], 0, rtol=0, atol=2e-13)
    assert np.count_nonzero(residual[:, :, 3]) == 30 * 2
    assert np.count_nonzero(residual[:, :, 1]) == 30 * 2
    assert np.all(residual[135:165, :, 3] < 0)
    assert np.all(residual[210:240, :, 1] > 0)
    assert np.max(np.abs(scene.observed_bottom_world - scene.world_contacts)) > 0.1


def test_projection_changes_pixel_speed_not_the_constant_world_path() -> None:
    affine, perspective = _scene("control", "solo"), _scene("perspective_only", "solo")
    world_delta = np.diff(affine.world_contacts[:, 0, 1])
    affine_delta = np.diff(affine.pixel_contacts[:, 0, 1])
    perspective_delta = np.diff(perspective.pixel_contacts[:, 0, 1])
    np.testing.assert_allclose(world_delta, 16 / 299, rtol=0, atol=1e-14)
    np.testing.assert_allclose(affine_delta, -260 / 299, rtol=0, atol=2e-13)
    assert abs(perspective_delta[0]) > abs(perspective_delta[-1])
    assert not np.allclose(perspective_delta, perspective_delta[0])
    np.testing.assert_array_equal(affine.world_contacts, perspective.world_contacts)


def test_bottom_and_top_truncation_move_different_anchors() -> None:
    scene = _scene("box_error_only", "solo")
    size = np.broadcast_to([36, 170, 36, 170], scene.ideal_boxes.shape)
    jitter_only = scene.ideal_boxes + 0.02 * scene.edge_draws * size
    jitter_centres = (jitter_only[..., :2] + jitter_only[..., 2:]) / 2
    # Bottom loss moves the bottom anchor by the full pulse, centre by half.
    np.testing.assert_allclose(
        scene.observed_bottom_centres[135:165, :, 1] - jitter_only[135:165, :, 3],
        -0.35 * 170,
        rtol=0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        scene.observed_box_centres[135:165, :, 1] - jitter_centres[135:165, :, 1],
        -0.35 * 170 / 2,
        rtol=0,
        atol=1e-12,
    )
    # Top loss moves the centre but leaves the bottom anchor's jitter unchanged.
    np.testing.assert_array_equal(
        scene.observed_bottom_centres[210:240, :, 1], jitter_only[210:240, :, 3]
    )
    np.testing.assert_allclose(
        scene.observed_box_centres[210:240, :, 1] - jitter_centres[210:240, :, 1],
        0.35 * 170 / 2,
        rtol=0,
        atol=1e-12,
    )


def test_path_endpoints_sprite_formula_and_projection_are_independent_oracles() -> None:
    scene = _scene("perspective_only", "solo")
    for frame in (0, 1, 134, 135, 164, 165, 209, 210, 239, 240, 299):
        y = 2 + 16 * frame / 299
        q = 1 + 0.05 * y
        u, v = (640 + 32 * y) / q, 650 / q
        width, height = 36 / q, 170 / q
        np.testing.assert_array_equal(scene.world_contacts[frame, 0], [0, y])
        np.testing.assert_allclose(scene.pixel_contacts[frame, 0], [u, v], rtol=0, atol=1e-12)
        np.testing.assert_allclose(
            scene.ideal_boxes[frame, 0],
            [u - width / 2, v - height, u + width / 2, v],
            rtol=0,
            atol=1e-12,
        )


@pytest.mark.parametrize("projection", ["affine", "perspective"])
def test_projection_inverse_and_input_ownership(projection) -> None:
    spec, _ = load_frozen_protocol()
    matrix = np.asarray(spec["projection"][projection], dtype=float)
    transform = GroundProjection(matrix)
    matrix[:] = 0  # Caller cannot change the validated transform afterwards.
    points = np.array([[0, 0], [-6, 10], [6, 20], [-2.5, 7.3]])
    pixels, q = transform.project(points)
    assert np.all(q > 1e-6)
    np.testing.assert_allclose(transform.unproject(pixels), points, rtol=0, atol=1e-9)
    with pytest.raises(ValueError):
        transform.matrix.setflags(write=True)


def test_valid_inverse_anchor_outside_roi_is_not_clamped() -> None:
    transform = GroundProjection(np.eye(3))
    np.testing.assert_array_equal(transform.unproject(np.array([[42, -17]])), [[42, -17]])


@pytest.mark.parametrize("matrix", [np.zeros((3, 3)), np.eye(2), np.eye(3) * np.nan])
def test_invalid_projection_matrix_is_rejected(matrix) -> None:
    with pytest.raises(ValueError, match="projection"):
        GroundProjection(matrix)


def test_determinant_limit_and_forward_inverse_horizons_are_rejected() -> None:
    with pytest.raises(ValueError, match="determinant"):
        GroundProjection(np.diag([1, 1, 1e-10]))
    transform = GroundProjection(np.array([[1, 0, 0], [0, 1, 0], [0, 1, 1]]))
    for y in (-1, -2, -1 + 1e-7):
        with pytest.raises(ValueError, match="denominator"):
            transform.project(np.array([[0, y]]))
    for y in (1, 2, 1 - 1e-7):
        with pytest.raises(ValueError, match="denominator"):
            transform.unproject(np.array([[0, y]]))


@pytest.mark.parametrize("value", [np.empty((0, 2)), [1, 2, 3], [[0, np.nan]], [[np.inf, 0]]])
def test_invalid_points_are_rejected_in_both_directions(value) -> None:
    transform = GroundProjection(np.eye(3))
    for operation in (transform.project, transform.unproject):
        with pytest.raises(ValueError, match="points"):
            operation(value)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_projection_tolerance_is_rejected(value) -> None:
    with pytest.raises(ValueError, match="tolerances"):
        GroundProjection(np.eye(3), min_positive_denominator=value)


def test_roundtrip_failure_is_not_ignored(monkeypatch) -> None:
    transform = GroundProjection(np.eye(3))
    monkeypatch.setattr(np, "allclose", lambda *args, **kwargs: False)
    with pytest.raises(ValueError, match="round trip"):
        transform.project(np.array([[1, 2]]))


@pytest.mark.parametrize(
    "boxes",
    [
        [],
        [[0, 1, 2]],
        [[1, 1, 1, 2]],
        [[1, 2, 2, 1]],
        [[-1, 0, 2, 2]],
        [[0, 0, 1281, 720]],
        [[0, 0, 1280, 721]],
        [[0, 0, np.nan, 3]],
    ],
)
def test_invalid_boxes_are_rejected_without_repair(boxes) -> None:
    with pytest.raises(ValueError, match="boxes"):
        validate_boxes(boxes, width=1280, height=720)


def test_image_boundaries_are_inclusive_but_dimensions_must_be_valid() -> None:
    boxes = np.array([[0, 0, 1280, 720]], dtype=float)
    np.testing.assert_array_equal(validate_boxes(boxes, width=1280, height=720), boxes)
    for width in (0, -1, float("inf")):
        with pytest.raises(ValueError, match="dimensions"):
            validate_boxes(boxes, width=width, height=720)


@pytest.mark.parametrize(
    "override, message",
    [
        ({"split": "other"}, "split"),
        ({"scenario": "offcentre"}, "scenario"),
        ({"seed": 1001}, "seed"),
        ({"seed": True}, "seed"),
        ({"seed": 101.0}, "seed"),
        ({"condition": "tuned"}, "condition"),
    ],
)
def test_only_frozen_split_scenario_seed_and_condition_can_be_generated(override, message) -> None:
    kwargs = dict(split="development", scenario="solo", seed=101, condition="control")
    with pytest.raises(ValueError, match=message):
        generate_scene(**(kwargs | override))


def test_recipe_integrity_failure_stops_generation_before_rng(monkeypatch) -> None:
    def changed():
        raise ValueError("frozen artifact changed")

    def forbidden(*args, **kwargs):
        pytest.fail("RNG constructed despite failed integrity check")

    monkeypatch.setattr(traffic_scene, "load_frozen_protocol", changed)
    monkeypatch.setattr(np.random, "PCG64", forbidden)
    with pytest.raises(ValueError, match="frozen artifact changed"):
        _scene()


def test_input_arrays_are_immutable_and_manifest_is_detached() -> None:
    scene = _scene()
    with pytest.raises(FrozenInstanceError):
        scene.seed = 102
    for field in fields(scene):
        value = getattr(scene, field.name)
        if isinstance(value, np.ndarray):
            with pytest.raises(ValueError):
                value.setflags(write=True)
    manifest = scene.manifest()
    manifest["sha256"]["world_truth"] = "changed"
    manifest["object_ids"].append(42)
    assert scene.manifest()["sha256"]["world_truth"] != "changed"
    assert scene.object_ids == (1, 2)


def test_replay_is_byte_identical_and_manifest_binds_run_provenance() -> None:
    first, second = _scene("combined"), _scene("combined")
    for field in fields(first):
        value = getattr(first, field.name)
        if isinstance(value, np.ndarray):
            assert value.tobytes() == getattr(second, field.name).tobytes()
    manifest = first.manifest()
    assert manifest == second.manifest()
    assert manifest["numpy_version"] == np.__version__
    _, hashes = load_frozen_protocol()
    assert manifest["protocol_hashes"] == hashes
    assert manifest["tracker_executed"] is False
    digest = manifest.pop("input_sha256")
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert digest == hashlib.sha256(encoded).hexdigest()
    assert "results" not in manifest


def test_array_digest_is_endian_layout_stable_and_binds_names_shapes_values() -> None:
    array = np.arange(6, dtype=float).reshape(2, 3)
    expected = _digest_arrays({"sample": array})
    assert _digest_arrays({"sample": np.asfortranarray(array)}) == expected
    assert _digest_arrays({"sample": array.astype(">f8")}) == expected
    assert _digest_arrays({"other": array}) != expected
    assert _digest_arrays({"sample": array.reshape(3, 2)}) != expected
    assert _digest_arrays({"sample": array + 1}) != expected
