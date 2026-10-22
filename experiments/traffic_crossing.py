"""Frozen v1 crossing extraction/scoring, without tracker execution.

This is a bounded synthetic mechanism scorer, not a traffic-flow evaluator.
The registered paths produce at most two truth events. Exhaustive matching is
intentional: it preserves the exact ordered objectives without weighted-cost
approximations, greedy assignment or a new optimization dependency.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass
from numbers import Integral, Real

from experiments.traffic_protocol import load_frozen_protocol

MAX_SAMPLES = 100_000
MAX_TRUTH_EVENTS = 2
MAX_PREDICTED_EVENTS = 1_200


def _integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return int(value)


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class AnchorSample:
    """One measured world-coordinate anchor for a local ID at an integer frame."""

    frame: int
    track_id: int
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame", _integer(self.frame, "frame"))
        object.__setattr__(self, "track_id", _integer(self.track_id, "track_id"))
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))


@dataclass(frozen=True)
class CrossingEvent:
    """One line arrival, with unrounded time in frame units (not seconds)."""

    track_id: int
    direction: int
    frame_time: float
    x: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _integer(self.track_id, "track_id"))
        if isinstance(self.direction, bool) or not isinstance(self.direction, Integral):
            raise ValueError("direction must be +1 or -1")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be +1 or -1")
        object.__setattr__(self, "direction", int(self.direction))
        object.__setattr__(self, "frame_time", _finite(self.frame_time, "frame_time"))
        object.__setattr__(self, "x", _finite(self.x, "x"))


def _bounded(items, limit: int, expected: type) -> list:
    result = []
    for item in items:
        if len(result) == limit:
            raise ValueError("scorer input exceeds bounded v1 capacity; no rows were dropped")
        if not isinstance(item, expected):
            raise ValueError(f"expected {expected.__name__} records")
        result.append(item)
    return result


def extract_crossings(samples) -> tuple[CrossingEvent, ...]:
    """Sort unique frame/ID samples, preserve gaps, emit first arrival/ID/direction.

    No filtering by truth, gap filling, epsilon, rounding or identity recovery.
    World anchors outside the ROI are valid; only the interpolated crossing X
    decides whether an event lies on the line segment. Invalid arithmetic fails.
    """
    spec, _ = load_frozen_protocol()
    rules, frames = spec["crossing"], spec["frame_grid"]["frames"]
    rows = sorted(_bounded(samples, MAX_SAMPLES, AnchorSample), key=lambda r: (r.frame, r.track_id))
    previous = {}
    emitted = set()
    events = []
    for row in rows:
        if row.frame >= frames:
            raise ValueError("sample frame is outside the registered frame grid")
        prior = previous.get(row.track_id)
        previous[row.track_id] = row
        if prior is None:
            continue
        gap = row.frame - prior.frame
        if gap == 0:
            raise ValueError("duplicate sample frame/track_id")
        if gap != rules["max_sample_gap_frames"]:
            continue
        line = rules["world_y"]
        direction = 1 if prior.y < line <= row.y else -1 if prior.y > line >= row.y else 0
        if not direction or (row.track_id, direction) in emitted:
            continue
        dy, dx = row.y - prior.y, row.x - prior.x
        if not math.isfinite(dy) or not math.isfinite(dx):
            raise ValueError("nonfinite crossing interpolation")
        fraction = (line - prior.y) / dy
        x = prior.x + fraction * dx
        frame_time = prior.frame + fraction * gap
        if not all(math.isfinite(v) for v in (fraction, x, frame_time)):
            raise ValueError("nonfinite crossing interpolation")
        if rules["world_x_min_inclusive"] <= x < rules["world_x_max_exclusive"]:
            events.append(CrossingEvent(row.track_id, direction, frame_time, x))
            emitted.add((row.track_id, direction))
    return tuple(
        sorted(events, key=lambda event: (event.frame_time, event.track_id, event.direction))
    )


def _validated_events(items, limit: int, rules: dict, frames: int) -> list[CrossingEvent]:
    events = _bounded(items, limit, CrossingEvent)
    seen = set()
    for event in events:
        key = (event.track_id, event.direction)
        if key in seen:
            raise ValueError("duplicate event ID/direction; extract first crossings before scoring")
        seen.add(key)
        if not 0 <= event.frame_time < frames:
            raise ValueError("event time is outside the registered frame grid")
        if not rules["world_x_min_inclusive"] <= event.x < rules["world_x_max_exclusive"]:
            raise ValueError("event X is outside the crossing line segment")
    return sorted(events, key=lambda e: (e.track_id, e.direction))


def _match(truth: list[CrossingEvent], predicted: list[CrossingEvent], rules: dict) -> tuple:
    """Exact enumeration for <=2 truth events; reject larger inputs upstream.

    Objective: maximum cardinality, then minimum total float64 absolute time,
    then total absolute X, then lexicographically sorted truth/predicted ID
    pairs. Do not combine objectives with a finite penalty or require equal IDs.
    Canonical input ordering makes any otherwise indistinguishable tie stable.
    """
    options, errors = [], {}
    for ti, true in enumerate(truth):
        candidates = [-1]  # Unmatched is always a valid option.
        for pi, pred in enumerate(predicted):
            dt, dx = abs(true.frame_time - pred.frame_time), abs(true.x - pred.x)
            if (
                true.direction == pred.direction
                and dt <= rules["max_match_time_error_frames"]
                and dx <= rules["max_match_x_error_world_units"]
            ):
                candidates.append(pi)
                errors[ti, pi] = (dt, dx)
        options.append(candidates)
    best_key, best_pairs = None, ()
    for assignment in itertools.product(*options):
        pairs = tuple((ti, pi) for ti, pi in enumerate(assignment) if pi != -1)
        if len({pi for _, pi in pairs}) != len(pairs):
            continue
        key = (
            -len(pairs),
            sum((errors[pair][0] for pair in pairs), 0.0),
            sum((errors[pair][1] for pair in pairs), 0.0),
            tuple(sorted((truth[ti].track_id, predicted[pi].track_id) for ti, pi in pairs)),
        )
        if best_key is None or key < best_key:
            best_key, best_pairs = key, pairs
    return best_pairs


def score_crossings(truth_events, predicted_events) -> dict:
    """JSON-safe matched/unmatched events and non-cancelling window errors.

    Limited to the registered v1 scope: <=2 truth and <=1200 predicted events.
    Capacity/validation failures raise; they never become flattering metrics.
    No tracker, detector, dataset, renderer or result-file write is involved.
    """
    spec, protocol_hashes = load_frozen_protocol()
    rules, frames = spec["crossing"], spec["frame_grid"]["frames"]
    truth = _validated_events(truth_events, MAX_TRUTH_EVENTS, rules, frames)
    predicted = _validated_events(predicted_events, MAX_PREDICTED_EVENTS, rules, frames)
    pairs = _match(truth, predicted, rules)
    window_size = rules["count_window_frames"]
    window_count = frames // window_size

    def window(event):
        return int(event.frame_time // window_size)

    counts = {}
    for direction, name in ((1, "positive"), (-1, "negative")):
        true_counts, pred_counts = [0] * window_count, [0] * window_count
        for events, target in ((truth, true_counts), (predicted, pred_counts)):
            for event in events:
                if event.direction == direction:
                    target[window(event)] += 1
        counts[name] = {
            "truth": true_counts,
            "predicted": pred_counts,
            "predicted_minus_truth": [p - t for t, p in zip(true_counts, pred_counts, strict=True)],
        }
    matches = [
        {
            "truth": asdict(truth[ti]),
            "predicted": asdict(predicted[pi]),
            "abs_time_error_frames": abs(truth[ti].frame_time - predicted[pi].frame_time),
            "abs_x_error_world": abs(truth[ti].x - predicted[pi].x),
            "truth_window": window(truth[ti]),
            "predicted_window": window(predicted[pi]),
        }
        for ti, pi in pairs
    ]
    matched_truth, matched_pred = {ti for ti, _ in pairs}, {pi for _, pi in pairs}
    misses = [asdict(event) for i, event in enumerate(truth) if i not in matched_truth]
    extras = [asdict(event) for i, event in enumerate(predicted) if i not in matched_pred]
    return {
        "format": "visiontrack.traffic-crossing-score/v1",
        "protocol_id": spec["protocol_id"],
        "protocol_hashes": protocol_hashes,
        "rules": rules,
        "frame_count": frames,
        "truth_events": [asdict(event) for event in truth],
        "predicted_events": [asdict(event) for event in predicted],
        "matches": matches,
        "unmatched_truth": misses,
        "unmatched_predictions": extras,
        "counts_by_direction_window": counts,
        "summary": {
            "truth_count": len(truth),
            "predicted_count": len(predicted),
            "matched_count": len(pairs),
            "missed_events": len(misses),
            "extra_events": len(extras),
            "event_error": len(misses) + len(extras),
            "recall": len(pairs) / len(truth) if truth else None,
            "matched_time_abs_mean_frames": (
                sum(m["abs_time_error_frames"] for m in matches) / len(matches) if matches else None
            ),
            "matched_x_abs_mean_world": (
                sum(m["abs_x_error_world"] for m in matches) / len(matches) if matches else None
            ),
            "matched_wrong_window_events": sum(
                m["truth_window"] != m["predicted_window"] for m in matches
            ),
            "window_count_abs_error": sum(
                abs(delta) for group in counts.values() for delta in group["predicted_minus_truth"]
            ),
        },
        "limitations": "Synthetic directed line crossings, not origin/destination flow validation.",
    }
