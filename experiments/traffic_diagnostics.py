"""Frozen traffic diagnostics, not a new matching algorithm.

Use the existing pinned CLEAR-MOT evaluator. Observation contact errors include
all true object-frames; tracked contact errors are conditional on its IoU match.
Strata never restart the matching history or invent a true region for a FP.
"""

from __future__ import annotations

from dataclasses import asdict
from numbers import Integral

import numpy as np

from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_scene import GroundProjection, SceneInputs, validate_boxes

ANCHORS = ("bottom_centre", "box_centre")
PHASES = ("outside_pulse_windows", "bottom_pulse_window", "top_pulse_window")
MAX_ROWS = 100_000


def _region(y: float, regions: list) -> int:
    for index, (start, stop) in enumerate(regions):
        if start <= y < stop or (index == len(regions) - 1 and y == stop):
            return index
    raise ValueError("true contact is outside the registered Y regions")


def _phase(frame: int, spec: dict) -> str:
    for prefix in ("bottom", "top"):
        pulse = spec["observation_error"][f"{prefix}_truncation"]
        if pulse["start_frame"] <= frame < pulse["stop_frame_exclusive"]:
            return f"{prefix}_pulse_window"
    return PHASES[0]


def _error(measured: np.ndarray, truth: np.ndarray) -> dict:
    dx, dy = measured - truth
    error = {"dx": float(dx), "dy": float(dy), "distance": float(np.hypot(dx, dy))}
    if not np.isfinite(list(error.values())).all():
        raise ValueError("nonfinite contact localization error")
    return error


def _world_anchors(box: np.ndarray, projection: GroundProjection) -> dict[str, np.ndarray]:
    x1, y1, x2, y2 = box
    return dict(
        zip(
            ANCHORS,
            projection.unproject(
                np.array(
                    [
                        [(x1 + x2) / 2, y2],
                        [(x1 + x2) / 2, (y1 + y2) / 2],
                    ]
                )
            ),
            strict=True,
        )
    )


def _localization(samples: list[dict], key: str) -> dict:
    result = {}
    for anchor in ANCHORS:
        errors = [sample[key][anchor] for sample in samples if sample[key] is not None]
        result[anchor] = {
            "sample_count": len(errors),
            "mean_distance_world": float(np.mean([e["distance"] for e in errors]))
            if errors
            else None,
            "mean_abs_dx_world": float(np.mean([abs(e["dx"]) for e in errors])) if errors else None,
            "mean_abs_dy_world": float(np.mean([abs(e["dy"]) for e in errors])) if errors else None,
            "mean_signed_dx_world": float(np.mean([e["dx"] for e in errors])) if errors else None,
            "mean_signed_dy_world": float(np.mean([e["dy"] for e in errors])) if errors else None,
            "max_distance_world": max(e["distance"] for e in errors) if errors else None,
        }
    return result


def _summary(samples: list[dict], false_positives: int | None) -> dict:
    total = len(samples)
    matched = sum(sample["matched_track_id"] is not None for sample in samples)
    return {
        "true_object_frames": total,
        "matched_object_frames": matched,
        "missed_object_frames": total - matched,
        "matched_object_frame_fraction": matched / total if total else None,
        "id_switches": sum(sample["id_switch"] for sample in samples),
        "fragmentations": sum(sample["fragmentation"] for sample in samples),
        "false_positive_rows": false_positives,
        "observation_contact_error": _localization(samples, "observation_error"),
        "matched_track_contact_error": _localization(samples, "matched_track_error"),
    }


def _validated_rows(rows: list[dict], spec: dict) -> dict[int, list[dict]]:
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("expected a bounded list of public output rows")
    by_frame = {frame: [] for frame in range(spec["frame_grid"]["frames"])}
    seen = set()
    grid = spec["frame_grid"]
    for row in rows:
        frame, identity = row["frame"], row["track_id"]
        if (
            isinstance(frame, bool)
            or not isinstance(frame, Integral)
            or frame not in by_frame
            or isinstance(identity, bool)
            or not isinstance(identity, Integral)
            or not 1 <= identity <= np.iinfo(np.int64).max
            or (frame, identity) in seen
        ):
            raise ValueError("invalid/duplicate public frame or track ID")
        seen.add((frame, identity))
        box = validate_boxes(row["xyxy"], width=grid["width"], height=grid["height"])
        if box.shape != (4,):
            raise ValueError("public row must have one box")
        by_frame[frame].append(row)
    return by_frame


def diagnose_development(scene: SceneInputs, rows: list[dict]) -> dict:
    """Score a registered development scene and already-returned public rows.

    Caller verifies baseline source before/after this experiment-only adapter.
    No tracker invocation, held-out entry point, gap fill or result-file writes.
    """
    return _diagnose(scene, rows, split="development")


def _diagnose(scene: SceneInputs, rows: list[dict], *, split: str) -> dict:
    """Internal shared scorer; held-out execution is gated by traffic_holdout."""
    spec, hashes = load_frozen_protocol()
    if (
        split not in {"development", "heldout"}
        or scene.split != split
        or scene.scenario not in spec["splits"][split]["scenarios"]
        or type(scene.seed) is not int
        or scene.seed not in spec["splits"][split]["seeds"]
        or scene.protocol_id != spec["protocol_id"]
        or dict(scene.protocol_hashes) != hashes
        or scene.condition not in {condition["id"] for condition in spec["conditions"]}
    ):
        raise ValueError(f"diagnostics require registered {split} inputs")
    if scene.object_ids != tuple(obj["object_id"] for obj in spec["scenarios"][scene.scenario]):
        raise ValueError("unexpected true object IDs")
    grid = spec["frame_grid"]
    shape = (grid["frames"], len(scene.object_ids))
    if (
        scene.ideal_boxes.shape != (*shape, 4)
        or scene.observed_boxes.shape != (*shape, 4)
        or scene.world_contacts.shape != (*shape, 2)
    ):
        raise ValueError("incomplete scene geometry")
    validate_boxes(scene.ideal_boxes, width=grid["width"], height=grid["height"])
    validate_boxes(scene.observed_boxes, width=grid["width"], height=grid["height"])
    if not np.isfinite(scene.world_contacts).all():
        raise ValueError("nonfinite true contacts")
    by_frame = _validated_rows(rows, spec)
    projection_name = next(
        c["projection"] for c in spec["conditions"] if c["id"] == scene.condition
    )
    projection = GroundProjection(np.array(spec["projection"][projection_name]))
    from visiontrack.eval.mot import MotAccumulator

    accumulator = MotAccumulator(iou_threshold=spec["diagnostics"]["gt_match_iou"])
    gt_ids = np.array(scene.object_ids, dtype=np.int64)
    samples, failures = [], []
    phase_fp = dict.fromkeys(PHASES, 0)
    regions = spec["diagnostics"]["regions_y"]
    for frame in range(grid["frames"]):
        public = by_frame[frame]
        hyp_ids = np.array([row["track_id"] for row in public], dtype=np.int64)
        hyp_boxes = np.array([row["xyxy"] for row in public], dtype=np.float64).reshape(-1, 4)
        events = accumulator.update(gt_ids, scene.ideal_boxes[frame], hyp_ids, hyp_boxes)
        failures.extend(asdict(event) for event in events)
        phase = _phase(frame, spec)
        phase_fp[phase] += sum(event.event_type == "false_positive" for event in events)
        misses = {event.gt_id for event in events if event.event_type == "miss"}
        switches = {event.gt_id for event in events if event.event_type == "id_switch"}
        fragments = {event.gt_id for event in events if event.event_type == "fragmentation"}
        lookup = {row["track_id"]: row for row in public}
        public_anchors = {
            identity: _world_anchors(np.array(row["xyxy"]), projection)
            for identity, row in lookup.items()
        }
        used = set()
        for index, identity in enumerate(scene.object_ids):
            truth = scene.world_contacts[frame, index]
            measured = _world_anchors(scene.observed_boxes[frame, index], projection)
            match = None
            tracked_error = None
            if identity not in misses:
                # Read the canonical evaluator's current correspondence rather
                # than independently re-solving assignment (which can alter ties).
                # This private, pinned v1 adapter is tested against its public totals.
                match = int(accumulator._last_hyp[identity])
                if match not in lookup or match in used:
                    raise ValueError("invalid canonical evaluator correspondence")
                used.add(match)
                anchors = public_anchors[match]
                tracked_error = {name: _error(anchors[name], truth) for name in ANCHORS}
            samples.append(
                {
                    "frame": frame,
                    "object_id": identity,
                    "region": _region(float(truth[1]), regions),
                    "phase": phase,
                    "matched_track_id": match,
                    "id_switch": identity in switches,
                    "fragmentation": identity in fragments,
                    "observation_error": {name: _error(measured[name], truth) for name in ANCHORS},
                    "matched_track_error": tracked_error,
                }
            )
    metrics = accumulator.result()
    overall = _summary(samples, metrics.false_positives)
    if (
        overall["matched_object_frames"] != metrics.true_positives
        or overall["missed_object_frames"] != metrics.false_negatives
        or overall["id_switches"] != metrics.id_switches
        or overall["fragmentations"] != metrics.fragmentations
        or sum(phase_fp.values()) != metrics.false_positives
    ):
        raise ValueError("diagnostic strata disagree with canonical evaluator")
    return {
        "format": f"visiontrack.traffic-{split}-diagnostics/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": hashes,
        "condition": scene.condition,
        "input_sha256": scene.manifest()["input_sha256"],
        "iou_threshold": spec["diagnostics"]["gt_match_iou"],
        "frame_count": metrics.num_frames,
        "overall": overall,
        "mean_matched_box_iou": metrics.motp if metrics.true_positives else None,
        "by_phase": {
            phase: _summary([s for s in samples if s["phase"] == phase], phase_fp[phase])
            for phase in PHASES
        },
        "by_true_region": [
            {
                "region": index,
                "y_bounds": bounds,
                "upper_inclusive": index == len(regions) - 1,
                "summary": _summary([s for s in samples if s["region"] == index], None),
                "by_phase": {
                    phase: _summary(
                        [s for s in samples if s["region"] == index and s["phase"] == phase], None
                    )
                    for phase in PHASES
                },
            }
            for index, bounds in enumerate(regions)
        ],
        "samples": samples,
        "failures": failures,
        "heldout_tracking_executed": split == "heldout",
        "limitations": [
            "Toy ground units, exact projection and imposed box errors, not measured traffic.",
            "Tracked localization is conditional on IoU matches; misses have no position estimate.",
            "Observation localization includes all true object-frames, independently of tracking.",
            "False positives have no true Y region; regional FP is null, not zero.",
            "Scheduled pulse windows also label controls, even when perturbation is disabled.",
            "Single canonical matching pass retains history across strata; no per-stratum rematch.",
        ],
    }
