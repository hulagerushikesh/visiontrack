"""Construct two observationally equivalent worlds, not an accuracy experiment.

Run with ``python -m experiments.localization_observability``. Only boxes,
scores and classes reach the unmodified tracker; hidden reference geometry
and scripted measurement errors are used afterward to describe each world.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import visiontrack
from visiontrack import ByteTracker, Detection, TrackerConfig

ROOT = Path(__file__).resolve().parents[1]
Box = tuple[int, int, int, int]


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


@dataclass(frozen=True)
class World:
    name: str
    reference: tuple[Box, ...]
    error: tuple[Box, ...]

    def observations(self) -> list[dict]:
        """A separate sensor layer; no reference labels survive this boundary."""
        return [dict(frame=frame, detections=[dict(
            xyxy=[a + b for a, b in zip(box, noise, strict=True)],
            score=0.9, class_id=0, feature=None,
        )]) for frame, (box, noise) in enumerate(zip(self.reference, self.error, strict=True))]


def witnesses() -> list[tuple[str, int, int, tuple[World, World]]]:
    """Two fixed constructions; no seed, fitted model, sweep or held-out data."""
    offset = (0, 0, 0, 0, 2, 4, 6, 8, 10, 10, 10, 10)
    translation = tuple((86 + d, 60, 106 + d, 100) for d in offset)
    # A changed lower edge can reflect a true box/anchor change OR measurement
    # bias. No physical 3D body or camera projection is asserted by this toy.
    extent = tuple((50, 60, 70, 100 + d) for d in offset)
    result = []
    for name, boxes, axis, line in (
        ("translation_or_localization_bias", translation, 0, 100),
        ("reference_extent_change_or_lower_edge_bias", extent, 1, 104),
    ):
        stationary = (boxes[0],) * len(boxes)
        errors = tuple(tuple(a - b for a, b in zip(obs, ref, strict=True))
                       for obs, ref in zip(boxes, stationary, strict=True))
        result.append((name, axis, line, (
            World("reference_changes", boxes, ((0, 0, 0, 0),) * len(boxes)),
            World("stationary_reference_with_measurement_bias", stationary, errors),
        )))
    return result


def positive_anchor_crossings(boxes: tuple[Box, ...], axis: int, line: int) -> int:
    """Toy reference only: bottom-centre anchor, previous < line <= current.

    Not the production traffic evaluator: no event matching, IDs, time windows,
    occlusions or inferred trajectories. A point exactly on the line is counted
    on arrival and not again on departure.
    """
    anchors = [((b[0] + b[2]) / 2, b[3])[axis] for b in boxes]
    return sum(a < line <= b for a, b in zip(anchors, anchors[1:], strict=False))


def replay(rows: list[dict], tracker: ByteTracker) -> list[dict]:
    """Deliberately accepts only inference rows, never a World or truth/error."""
    outputs = []
    for row in rows:
        observations = tracker.update([
            Detection(d["xyxy"], d["score"], d["class_id"])
            for d in row["detections"]
        ])
        outputs.append(dict(frame=row["frame"], observations=[dict(
            frame=int(o.frame), track_id=int(o.track_id), xyxy=o.xyxy.tolist(),
            score=float(o.score), class_id=int(o.class_id),
        ) for o in observations]))
    return outputs


def run() -> dict:
    if Path(visiontrack.__file__).resolve() != ROOT / "src/visiontrack/__init__.py":
        raise ValueError("use checkout sources (PYTHONPATH=src or editable install)")
    cases = []
    for name, axis, line, worlds in witnesses():
        inputs = [world.observations() for world in worlds]
        if encoded(inputs[0]) != encoded(inputs[1]):
            raise ValueError("witness observations differ")
        outputs = []
        for rows in inputs:
            tracker = ByteTracker()
            first = replay(rows, tracker)
            tracker.reset()
            if encoded(first) != encoded(replay(rows, tracker)):
                raise ValueError("reset changed the output")
            outputs.append(first)
        if encoded(outputs[0]) != encoded(outputs[1]):
            raise ValueError("equivalent observations produced different outputs")
        counts = [positive_anchor_crossings(w.reference, axis, line) for w in worlds]
        if counts != [1, 0]:
            raise ValueError("witness does not separate reference anchor crossings")
        cases.append(dict(
            name=name, input_sha256=digest(inputs[0]), output_sha256=digest(outputs[0]),
            observations=inputs[0], tracker_outputs=outputs[0],
            crossing_definition=dict(anchor="bottom_centre", axis=axis, line=line,
                                     positive="previous < line <= current"),
            worlds=[dict(**asdict(w), reference_positive_crossings=count)
                    for w, count in zip(worlds, counts, strict=True)],
            exact_input_agreement=True, exact_output_agreement=True,
            reset_output_agreement=True,
        ))
    # Pin the executable and all runtime bytes without pretending Git HEAD alone
    # identifies a possibly edited checkout. Paths stay repository-relative.
    files = [Path(__file__), *sorted((ROOT / "src/visiontrack").rglob("*.py"))]
    return dict(
        schema="visiontrack.localization_observability.v1", synthetic_only=True,
        accuracy_claim=False, novelty_claim=False, tracker_config=asdict(TrackerConfig()),
        environment=dict(python=platform.python_version(), numpy=np.__version__),
        claim="Current inference rows do not uniquely determine the hidden world.",
        limitation="Not a frequency estimate or a rejection of statistical noise estimation.",
        source_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in files}, cases=cases,
    )


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
