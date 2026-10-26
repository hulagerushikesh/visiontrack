"""Author the frozen continuity-warning v1 scene grid without running a tracker."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from visiontrack.tracking.config import TrackerConfig

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "experiments/continuity_warning_v1.json"
RECIPE_SHA = "a6faf550f080834edf324698c59c7426ecad6824bf7f7f083e24dde0aadaa67f"


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def load_recipe() -> dict:
    if hashlib.sha256(RECIPE.read_bytes()).hexdigest() != RECIPE_SHA:
        raise ValueError("frozen recipe drift")
    spec = json.loads(RECIPE.read_text())
    if asdict(TrackerConfig()) != spec["tracker_config"]:
        raise ValueError("default tracker configuration drift")
    return spec


def _box(x: float, y: float, width: float, height: float) -> list[float]:
    return [x - width / 2, y - height / 2, x + width / 2, y + height / 2]


def _det(box: list[float], spec: dict) -> dict:
    return dict(xyxy=box.copy(), score=spec["scene"]["score"],
                class_id=spec["scene"]["class_id"])


def scene(spec: dict, duration: int, family: str) -> list[dict]:
    g = spec["scene"]
    if type(duration) is not int or duration not in g["durations"]:
        raise ValueError("unregistered duration")
    if family not in [row["name"] for row in spec["families"]]:
        raise ValueError("unregistered family")
    frames = []
    start = g["episode_start"]
    for frame in range(g["frames"]):
        episode = start <= frame < start + duration
        a = _box(g["first_center_at_zero"][0] + g["first_velocity"][0] * frame,
                 g["first_center_at_zero"][1], g["width"], g["height"])
        b = _box(g["second_center_at_zero"][0] + g["second_velocity"][0] * frame,
                 g["second_center_at_zero"][1], g["width"], g["height"])
        if family in {"scale_pulse_pair", "motion_turn_pair"}:
            if family == "scale_pulse_pair":
                x = g["first_center_at_zero"][0] + g["first_velocity"][0] * frame
                scale = g["scale_pulse"] if episode else 1
            else:
                displacement = min(max(frame - start, 0), duration)
                x = g["first_center_at_zero"][0] + g["first_velocity"][0] * (
                    frame - 2 * displacement)
                scale = 1
            a = _box(x, g["separated_control_y"][0],
                     g["width"] * scale, g["height"] * scale)
            b = _box(x, g["separated_control_y"][1],
                     g["width"] * scale, g["height"] * scale)
        if family in {"coincident_two", "duplicate_single"}:
            b = a.copy()

        truth = [dict(reference_id=1, xyxy=a.copy())]
        if family != "duplicate_single" and not (
            family == "exit_new_entrant" and episode
        ):
            second_id = 3 if family == "exit_new_entrant" and frame >= start + duration else 2
            truth.append(dict(reference_id=second_id, xyxy=b.copy()))

        if episode and family == "shared_union":
            union = [min(a[0], b[0]), min(a[1], b[1]),
                     max(a[2], b[2]), max(a[3], b[3])]
            detections = [_det(union, spec)]
        elif episode and family in {"missing_second", "exit_new_entrant",
                                         "coincident_two", "duplicate_single"}:
            detections = [_det(a, spec)]
        else:
            detections = [_det(a, spec), _det(b, spec)]
        frames.append(dict(frame=frame, detections=detections, truth=truth))
    return frames


def detector_payload(rows: list[dict]) -> bytes:
    return encoded([dict(frame=row["frame"], detections=row["detections"]) for row in rows])


def validate_grid(spec: dict) -> dict:
    """Validate authored inputs and semantic pairs, with no tracker execution."""
    grid = {(duration, family["name"]): scene(spec, duration, family["name"])
            for duration in spec["scene"]["durations"] for family in spec["families"]}
    if len(grid) != spec["execution"]["cells"]:
        raise ValueError("cell count mismatch")
    for (duration, family), frames in grid.items():
        if [row["frame"] for row in frames] != list(range(spec["scene"]["frames"])):
            raise ValueError("frame sequence mismatch")
        for row in frames:
            frame = row["frame"]
            for det in row["detections"]:
                box = det["xyxy"]
                if (len(box) != 4 or not all(isinstance(x, (int, float)) and
                       abs(x) < float("inf") for x in box) or
                       box[2] <= box[0] or box[3] <= box[1]):
                    raise ValueError("invalid scene detection box")
                if det["score"] != spec["scene"]["score"] or det["class_id"] != 0:
                    raise ValueError("invalid scene detection metadata")
            if frame < spec["scene"]["episode_start"] or frame >= (
                spec["scene"]["episode_start"] + duration
            ):
                if len(row["detections"]) != 2:
                    raise ValueError(f"non-episode detector count: {family}")
            elif len(row["detections"]) != (2 if family in {
                "crossing_distinct", "unchanged_control", "scale_pulse_pair",
                "motion_turn_pair"} else 1):
                raise ValueError(f"episode detector count: {family}")
        for left, right in (("crossing_distinct", "unchanged_control"),
                            ("missing_second", "exit_new_entrant"),
                            ("coincident_two", "duplicate_single")):
            if detector_payload(grid[duration, left]) != detector_payload(grid[duration, right]):
                raise ValueError("semantic/control detector payload mismatch")
        if encoded(grid[duration, "crossing_distinct"]) != encoded(
            grid[duration, "unchanged_control"]
        ):
            raise ValueError("unchanged control truth/input mismatch")
        for left, right in (("missing_second", "exit_new_entrant"),
                            ("coincident_two", "duplicate_single")):
            if encoded([r["truth"] for r in grid[duration, left]]) == encoded(
                [r["truth"] for r in grid[duration, right]]
            ):
                raise ValueError("semantic pair truth should differ")
    unique = len({detector_payload(rows) for rows in grid.values()})
    if unique != 16:
        raise ValueError(f"expected 16 unique complete detector payloads, got {unique}")
    return dict(cells=len(grid), unique_detector_payloads=unique,
                frames_per_cell=spec["scene"]["frames"])
