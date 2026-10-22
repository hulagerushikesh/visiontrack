"""Dataset-free inputs for the locked traffic mechanism protocol, not outcomes.

This experiment-only generator does not import a tracker, render people, infer
identities, or modify the existing pixel-space synthetic generator. Held-out
input geometry is not held-out tracker evaluation. No files are written.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from experiments.traffic_protocol import load_frozen_protocol


def _readonly(value: np.ndarray) -> np.ndarray:
    """Own an immutable, canonical little-endian float64 array."""
    array = np.asarray(value, dtype="<f8", order="C")
    return np.frombuffer(array.tobytes(), dtype="<f8").reshape(array.shape)


def _points(value: np.ndarray) -> np.ndarray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim < 1 or points.shape[-1] != 2 or not points.size:
        raise ValueError("points must have nonempty shape (..., 2)")
    if not np.isfinite(points).all():
        raise ValueError("points must be finite")
    return points


@dataclass(frozen=True, init=False)
class GroundProjection:
    """Validated column-vector homography with no clipping or ROI repair."""

    matrix: np.ndarray
    inverse: np.ndarray
    min_denominator: float
    roundtrip_tolerance: float

    def __init__(
        self,
        matrix: np.ndarray,
        *,
        min_abs_determinant: float = 1e-9,
        min_positive_denominator: float = 1e-6,
        roundtrip_absolute_tolerance: float = 1e-9,
    ) -> None:
        thresholds = (
            min_abs_determinant,
            min_positive_denominator,
            roundtrip_absolute_tolerance,
        )
        if any(not np.isfinite(t) or t <= 0 for t in thresholds):
            raise ValueError("projection tolerances must be finite and positive")
        matrix = np.asarray(matrix, dtype=np.float64)
        if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
            raise ValueError("projection must be a finite 3-by-3 matrix")
        determinant = np.linalg.det(matrix)
        if not np.isfinite(determinant) or abs(determinant) <= min_abs_determinant:
            raise ValueError("projection is singular or below determinant limit")
        inverse = np.linalg.inv(matrix)
        if not np.isfinite(inverse).all():
            raise ValueError("inverse projection must be finite")
        object.__setattr__(self, "matrix", _readonly(matrix))
        object.__setattr__(self, "inverse", _readonly(inverse))
        object.__setattr__(self, "min_denominator", min_positive_denominator)
        object.__setattr__(self, "roundtrip_tolerance", roundtrip_absolute_tolerance)

    def _map(self, points: np.ndarray, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        points = _points(points)
        homogeneous = np.concatenate((points, np.ones((*points.shape[:-1], 1))), axis=-1)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            mapped = homogeneous @ matrix.T
            denominator = mapped[..., 2]
            if not np.isfinite(mapped).all() or np.any(denominator <= self.min_denominator):
                raise ValueError("invalid or near-horizon homogeneous denominator")
            result = mapped[..., :2] / denominator[..., None]
        if not np.isfinite(result).all():
            raise ValueError("projected points must be finite")
        return result, denominator

    def project(self, world: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return pixels and q; reject invalid projection or inverse round trip."""
        world = _points(world)
        pixels, denominator = self._map(world, self.matrix)
        restored, _ = self._map(pixels, self.inverse)
        if not np.allclose(restored, world, rtol=0, atol=self.roundtrip_tolerance):
            raise ValueError("projection round trip exceeds absolute tolerance")
        return pixels, denominator

    def unproject(self, pixels: np.ndarray) -> np.ndarray:
        """Keep valid positions outside the world ROI; do not clamp crossings."""
        world, _ = self._map(pixels, self.inverse)
        return world


def validate_boxes(boxes: np.ndarray, *, width: int, height: int) -> np.ndarray:
    """Reject invalid boxes, including out-of-image edges; never silently repair."""
    boxes = np.asarray(boxes, dtype=np.float64)
    if boxes.ndim < 1 or boxes.shape[-1] != 4 or not boxes.size:
        raise ValueError("boxes must have nonempty shape (..., 4)")
    if not np.isfinite(boxes).all():
        raise ValueError("boxes must be finite")
    if not np.isfinite([width, height]).all() or width <= 0 or height <= 0:
        raise ValueError("image dimensions must be finite and positive")
    if np.any(boxes[..., 2:] <= boxes[..., :2]):
        raise ValueError("boxes must have positive width and height")
    if np.any(boxes < 0) or np.any(boxes > np.array([width, height, width, height])):
        raise ValueError("boxes must lie fully inside the image")
    return boxes


def _digest_arrays(arrays: dict[str, np.ndarray]) -> str:
    """Hash ordered names/shapes and little-endian C-order float64 bytes.

    Length-prefix each header and payload to avoid ambiguous concatenation.
    Names and array order are part of this experiment's digest format v1.
    """
    digest = hashlib.sha256(b"visiontrack.traffic-input-arrays/v1\0")
    for name, array in arrays.items():
        array = np.asarray(array, dtype="<f8", order="C")
        header = json.dumps(
            {"name": name, "shape": array.shape, "dtype": "<f8"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload = array.tobytes()
        for part in (header, payload):
            digest.update(len(part).to_bytes(8, "little"))
            digest.update(part)
    return digest.hexdigest()


@dataclass(frozen=True)
class SceneInputs:
    """Read-only inputs only; object IDs must never enter detector feature rows."""

    split: str
    scenario: str
    seed: int
    condition: str
    protocol_id: str
    protocol_hashes: tuple[tuple[str, str], ...]
    numpy_version: str
    object_ids: tuple[int, ...]
    frames: np.ndarray
    timestamps: np.ndarray
    world_contacts: np.ndarray
    pixel_contacts: np.ndarray
    ideal_boxes: np.ndarray
    ideal_box_centres: np.ndarray
    edge_draws: np.ndarray
    observed_boxes: np.ndarray
    observed_bottom_centres: np.ndarray
    observed_box_centres: np.ndarray
    observed_bottom_world: np.ndarray
    observed_centre_world: np.ndarray

    def manifest(self) -> dict:
        """Fresh JSON-safe provenance and content digests, without results."""
        common = {
            "object_ids": np.asarray(self.object_ids),
            "frames": self.frames,
            "timestamps": self.timestamps,
        }
        truth = {**common, "world_contacts": self.world_contacts}
        ideal = {
            **truth,
            "pixel_contacts": self.pixel_contacts,
            "ideal_boxes": self.ideal_boxes,
            "ideal_box_centres": self.ideal_box_centres,
        }
        observations = {
            **common,
            "observed_boxes": self.observed_boxes,
            "observed_bottom_centres": self.observed_bottom_centres,
            "observed_box_centres": self.observed_box_centres,
            "observed_bottom_world": self.observed_bottom_world,
            "observed_centre_world": self.observed_centre_world,
        }
        digests = {
            "world_truth": _digest_arrays(truth),
            "ideal_truth": _digest_arrays(ideal),
            "random_draws": _digest_arrays({"edge_draws": self.edge_draws}),
            "observations": _digest_arrays(observations),
        }
        manifest = {
            "format": "visiontrack.traffic-scene-inputs/v1",
            "protocol_id": self.protocol_id,
            "protocol_hashes": dict(self.protocol_hashes),
            "numpy_version": self.numpy_version,
            "split": self.split,
            "scenario": self.scenario,
            "seed": self.seed,
            "condition": self.condition,
            "object_ids": list(self.object_ids),
            "frame_count": len(self.frames),
            "sha256": digests,
            "tracker_executed": False,
            "limitations": (
                "Toy synthetic inputs, not measured camera/detector or traffic validation."
            ),
        }
        manifest["input_sha256"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        return manifest


def generate_scene(*, split: str, scenario: str, seed: int, condition: str) -> SceneInputs:
    """Generate only registered inputs after verifying the frozen recipe bytes.

    No default split, arbitrary seed, configuration override, tracker import or
    result export. Held-out *tracking* remains gated by the frozen protocol.
    RNG consumption is frame/object-ID/edge order, even when error is disabled.
    """
    spec, protocol_hashes = load_frozen_protocol()
    if split not in spec["splits"]:
        raise ValueError("unknown split")
    registered = spec["splits"][split]
    if scenario not in registered["scenarios"]:
        raise ValueError("scenario is not registered in this split")
    if type(seed) is not int or seed not in registered["seeds"]:
        raise ValueError("seed is not registered in this split")
    conditions = {item["id"]: item for item in spec["conditions"]}
    if condition not in conditions:
        raise ValueError("unknown observation condition")
    settings = conditions[condition]
    grid, model = spec["frame_grid"], spec["ideal_box"]
    objects = sorted(spec["scenarios"][scenario], key=lambda obj: obj["object_id"])
    frames = np.arange(grid["frames"], dtype=np.float64)
    start = np.array([obj["start"] for obj in objects], dtype=np.float64)
    end = np.array([obj["end"] for obj in objects], dtype=np.float64)
    world = start + (end - start) * frames[:, None, None] / (grid["frames"] - 1)
    for axis, name in enumerate(("x", "y")):
        lower, upper = spec["world_roi"][name]
        if np.any(world[..., axis] < lower) or np.any(world[..., axis] > upper):
            raise ValueError("true contacts must be inside the world ROI")
    projection = spec["projection"]
    transform = GroundProjection(
        projection[settings["projection"]],
        **{name: value for name, value in projection.items() if name.startswith("min_")},
        roundtrip_absolute_tolerance=projection["roundtrip_absolute_tolerance"],
    )
    pixels, denominator = transform.project(world)
    width = model["width_scale"] * model["world_width"] / denominator
    height = model["height_scale"] * model["world_height"] / denominator
    u, v = pixels[..., 0], pixels[..., 1]
    ideal = np.stack((u - width / 2, v - height, u + width / 2, v), axis=-1)
    validate_boxes(ideal, width=grid["width"], height=grid["height"])
    draws = np.random.Generator(np.random.PCG64(seed)).uniform(-1, 1, (*width.shape, 4))
    observed = ideal.copy()
    error = spec["observation_error"]
    if settings["box_error"]:
        observed += (
            error["edge_jitter_fraction"]
            * draws
            * np.stack((width, height, width, height), axis=-1)
        )
        for name, edge, sign in (("bottom_truncation", 3, -1), ("top_truncation", 1, 1)):
            pulse = error[name]
            rows = slice(pulse["start_frame"], pulse["stop_frame_exclusive"])
            observed[rows, :, edge] += sign * pulse["ideal_height_fraction"] * height[rows]
    validate_boxes(observed, width=grid["width"], height=grid["height"])
    ideal_centres = (ideal[..., :2] + ideal[..., 2:]) / 2
    observed_centres = (observed[..., :2] + observed[..., 2:]) / 2
    observed_bottom = np.stack((observed_centres[..., 0], observed[..., 3]), axis=-1)
    arrays = {
        "frames": frames,
        "timestamps": frames / grid["fps"],
        "world_contacts": world,
        "pixel_contacts": pixels,
        "ideal_boxes": ideal,
        "ideal_box_centres": ideal_centres,
        "edge_draws": draws,
        "observed_boxes": observed,
        "observed_bottom_centres": observed_bottom,
        "observed_box_centres": observed_centres,
        "observed_bottom_world": transform.unproject(observed_bottom),
        "observed_centre_world": transform.unproject(observed_centres),
    }
    return SceneInputs(
        split=split,
        scenario=scenario,
        seed=seed,
        condition=condition,
        protocol_id=spec["protocol_id"],
        protocol_hashes=tuple(protocol_hashes.items()),
        numpy_version=np.__version__,
        object_ids=tuple(obj["object_id"] for obj in objects),
        **{name: _readonly(value) for name, value in arrays.items()},
    )
