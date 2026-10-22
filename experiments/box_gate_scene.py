"""Input-only implementation of the separately registered box-gate ablation.

No tracker, variant, results, camera, network or file-write interface. New paths
cannot be injected into the frozen traffic v1 generator. Only its unchanged
geometry/immutable-array helpers are reused; its registered inputs stay intact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from experiments.box_gate_protocol import INHERITED, load_registration
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_scene import GroundProjection, _digest_arrays, _readonly, validate_boxes


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class BoxGateInputs:
    """Generated immutable measurements and separate reference geometry.

    Reference IDs/contacts are for later evaluation, not Detection features.
    This is not a v1 SceneInputs instance or a verified tracker-output record.
    Future adapters must revalidate provenance before executing tracking.
    """

    split: str
    scenario: str
    seed: int
    condition: str
    protocol_id: str
    protocol_hashes: tuple[tuple[str, str], ...]
    numpy_version: str
    object_ids: tuple[int, ...]
    detection_score: float
    detection_class_id: int
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

    def detection_manifest(self) -> dict:
        """Fingerprint only the intended detector stream, never reference IDs.

        Fixed column order follows the registered input order. The future
        adapter supplies boxes, constant score and class, with feature=None.
        No variant is included: both variants must receive this same stream.
        """
        manifest = {
            "format": "visiontrack.box-gate-detection-inputs/v1",
            "frame_count": len(self.frames),
            "detections_per_frame": self.observed_boxes.shape[1],
            "score": self.detection_score,
            "class_id": self.detection_class_id,
            "feature": None,
            "arrays_sha256": _digest_arrays({
                "frames": self.frames, "observed_boxes": self.observed_boxes,
            }),
        }
        manifest["detection_stream_sha256"] = _sha(manifest)
        return manifest

    def manifest(self) -> dict:
        """Fresh JSON-safe input provenance; no run or benefit claim."""
        common = {
            "object_ids": np.asarray(self.object_ids),
            "frames": self.frames,
            "timestamps": self.timestamps,
        }
        truth = {**common, "world_contacts": self.world_contacts}
        manifest = {
            "format": "visiontrack.box-gate-scene-inputs/v1",
            "protocol_id": self.protocol_id,
            "protocol_hashes": dict(self.protocol_hashes),
            "numpy_version": self.numpy_version,
            "split": self.split,
            "scenario": self.scenario,
            "seed": self.seed,
            "condition": self.condition,
            "object_ids": list(self.object_ids),
            "frame_count": len(self.frames),
            "sha256": {
                "world_truth": _digest_arrays(truth),
                "ideal_truth": _digest_arrays({
                    **truth, "pixel_contacts": self.pixel_contacts,
                    "ideal_boxes": self.ideal_boxes, "ideal_box_centres": self.ideal_box_centres,
                }),
                "random_draws": _digest_arrays({"edge_draws": self.edge_draws}),
                "observations": _digest_arrays({
                    **common, "observed_boxes": self.observed_boxes,
                    "observed_bottom_centres": self.observed_bottom_centres,
                    "observed_box_centres": self.observed_box_centres,
                    "observed_bottom_world": self.observed_bottom_world,
                    "observed_centre_world": self.observed_centre_world,
                }),
            },
            "detections": self.detection_manifest(),
            "tracker_executed": False,
            "limitations": "Toy numeric inputs, not detector outcomes or real-traffic validation.",
        }
        manifest["input_sha256"] = _sha(manifest)
        return manifest


def generate_inputs(*, split: str, scenario: str, seed: int, condition: str) -> BoxGateInputs:
    """Generate one exact registered input case, without a variant selector.

    Held-out *input* generation is allowed for a future digest freeze; this
    function cannot execute tracking on either split. No existing v1 run gate
    is opened. Unregistered selectors fail before the local RNG is constructed.
    """
    registration, hashes = load_registration()
    parent, parent_hashes = load_frozen_protocol()
    if any(hashes[name] != digest for name, digest in parent_hashes.items()):
        raise ValueError("parent recipe drift during input preflight")
    spec = {key: parent[key] for key in INHERITED}
    if split not in registration["splits"]:
        raise ValueError("unknown registered split")
    selected = registration["splits"][split]
    if scenario not in selected["scenarios"]:
        raise ValueError("scenario is not registered in this split")
    if type(seed) is not int or seed not in selected["seeds"]:
        raise ValueError("seed is not registered in this split")
    conditions = {item["id"]: item for item in spec["conditions"]}
    if condition not in conditions:
        raise ValueError("unknown registered observation condition")
    settings = conditions[condition]
    grid, model = spec["frame_grid"], spec["ideal_box"]
    objects = sorted(registration["scenarios"][scenario], key=lambda obj: obj["object_id"])
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
        min_abs_determinant=projection["min_abs_determinant"],
        min_positive_denominator=projection["min_positive_denominator"],
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
            error["edge_jitter_fraction"] * draws
            * np.stack((width, height, width, height), axis=-1)
        )
        for name, edge, sign in (("bottom_truncation", 3, -1), ("top_truncation", 1, 1)):
            pulse = error[name]
            rows = slice(pulse["start_frame"], pulse["stop_frame_exclusive"])
            observed[rows, :, edge] += sign * pulse["ideal_height_fraction"] * height[rows]
    validate_boxes(observed, width=grid["width"], height=grid["height"])
    ideal_centres = (ideal[..., :2] + ideal[..., 2:]) / 2
    centres = (observed[..., :2] + observed[..., 2:]) / 2
    bottom = np.stack((centres[..., 0], observed[..., 3]), axis=-1)
    arrays = {
        "frames": frames, "timestamps": frames / grid["fps"],
        "world_contacts": world, "pixel_contacts": pixels,
        "ideal_boxes": ideal, "ideal_box_centres": ideal_centres,
        "edge_draws": draws, "observed_boxes": observed,
        "observed_bottom_centres": bottom, "observed_box_centres": centres,
        "observed_bottom_world": transform.unproject(bottom),
        "observed_centre_world": transform.unproject(centres),
    }
    return BoxGateInputs(
        split=split, scenario=scenario, seed=seed, condition=condition,
        protocol_id=registration["protocol_id"], protocol_hashes=tuple(hashes.items()),
        numpy_version=np.__version__, object_ids=tuple(obj["object_id"] for obj in objects),
        detection_score=model["score"], detection_class_id=model["class_id"],
        **{name: _readonly(value) for name, value in arrays.items()},
    )
