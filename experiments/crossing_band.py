"""Isolated registered counters on supplied anchors; no tracker or output writes.

This implements crossing-band/v1, not its future replay/evaluation harness.
Both modes consume the same typed samples. Truth, smoothing, identity joining,
parameter tuning and latency-based event suppression are deliberately absent.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from numbers import Integral

from experiments.crossing_band_protocol import load_registration
from experiments.traffic_crossing import MAX_SAMPLES, AnchorSample, CrossingEvent
from experiments.traffic_protocol import load_frozen_protocol


@dataclass(frozen=True)
class Emission:
    """Retain the interpolated arrival AND the actual integer reporting frame."""

    event: CrossingEvent
    emission_frame: int

    def __post_init__(self) -> None:
        if not isinstance(self.event, CrossingEvent):
            raise ValueError("emission needs a CrossingEvent")
        frame = self.emission_frame
        if (isinstance(frame, bool) or not isinstance(frame, Integral)
                or not 0 <= self.event.frame_time <= frame < 300):
            raise ValueError("emission frame must be an in-grid integer at/after arrival")
        object.__setattr__(self, "emission_frame", int(frame))

    @property
    def delay_frames(self) -> float:
        return self.emission_frame - self.event.frame_time


@dataclass(frozen=True)
class PendingRecord:
    """Every pending arrival's fate, including rejected and unfinished passages.

    closed_frame is None only for end-of-input pending state: no confirmation
    frame or count is invented. arrival_frame is the adjacent arrival sample,
    not ceil(interpolated time), which can round onto the preceding integer.
    """

    event: CrossingEvent
    arrival_frame: int
    closed_frame: int | None
    disposition: str


@dataclass(frozen=True)
class CountResult:
    counter: str
    emissions: tuple[Emission, ...]
    pending_records: tuple[PendingRecord, ...]

    @property
    def events(self) -> tuple[CrossingEvent, ...]:
        return tuple(item.event for item in self.emissions)

    @property
    def maximum_delay_frames(self) -> float | None:
        return max((item.delay_frames for item in self.emissions), default=None)

    @property
    def diagnostics(self) -> dict[str, int]:
        counts = Counter(item.disposition for item in self.pending_records)
        return {
            "pending_arrivals": len(self.pending_records),
            **{key: counts[key] for key in (
                "emitted", "outside_segment", "already_emitted", "return_to_origin",
                "sample_gap", "end_unconfirmed",
            )},
        }


@dataclass
class _State:
    previous: AnchorSample
    origin: int
    pending: tuple[CrossingEvent, int] | None = None


def _rows(samples, frames: int) -> list[AnchorSample]:
    rows = []
    for row in samples:
        if len(rows) == MAX_SAMPLES:
            raise ValueError("counter input exceeds bounded v1 capacity; no rows were dropped")
        if not isinstance(row, AnchorSample):
            raise ValueError("expected AnchorSample records")
        if row.frame >= frames:
            raise ValueError("sample frame is outside the registered frame grid")
        rows.append(row)
    rows.sort(key=lambda row: (row.frame, row.track_id))
    seen = set()
    for row in rows:
        key = (row.frame, row.track_id)
        if key in seen:
            raise ValueError("duplicate sample frame/track_id")
        seen.add(key)
    return rows


def _direction(prior: AnchorSample, row: AnchorSample, line: float) -> int:
    return 1 if prior.y < line <= row.y else -1 if prior.y > line >= row.y else 0


def _arrival(prior: AnchorSample, row: AnchorSample, direction: int, line: float):
    # Exact frozen arithmetic/order; only called for an adjacent line arrival.
    dy, dx = row.y - prior.y, row.x - prior.x
    if not math.isfinite(dy) or not math.isfinite(dx):
        raise ValueError("nonfinite crossing interpolation")
    fraction = (line - prior.y) / dy
    x = prior.x + fraction * dx
    time = prior.frame + fraction * (row.frame - prior.frame)
    if not all(math.isfinite(v) for v in (fraction, x, time)):
        raise ValueError("nonfinite crossing interpolation")
    return CrossingEvent(row.track_id, direction, time, x)


def count_crossings(samples, *, counter: str) -> CountResult:
    """Return immutable records without running/scoring a tracker or writing files.

    Modes are exactly 'legacy' and 'band'; no adjustable rule arguments. Samples
    may be interleaved/unsorted but must be unique, finite, in-grid typed rows.
    No ROI clipping: the interpolated crossing X alone controls segment inclusion.
    Late events are retained, NOT suppressed to pass the 15-frame safety rule.
    Consumers must evaluate that rule and actual emission-window errors separately.
    Output order is original line-arrival time, ID, direction, not emission order.
    """
    if counter not in ("legacy", "band"):
        raise ValueError("counter must be legacy or band")
    registration, _ = load_registration()
    parent, _ = load_frozen_protocol()
    rules = parent["crossing"]
    rows = _rows(samples, parent["frame_grid"]["frames"])
    line = rules["world_y"]
    half_width = registration["candidate_rules"]["half_width_world_units"]

    def stable(y):
        return -1 if y <= line - half_width else 1 if y >= line + half_width else 0

    def inside(event):
        return rules["world_x_min_inclusive"] <= event.x < rules["world_x_max_exclusive"]

    states, emitted, emissions, records = {}, set(), [], []

    def close(state, frame, disposition):
        event, arrival_frame = state.pending
        records.append(PendingRecord(event, arrival_frame, frame, disposition))
        state.pending = None

    for row in rows:
        state = states.get(row.track_id)
        if state is None:
            states[row.track_id] = _State(row, stable(row.y))
            continue
        prior = state.previous
        state.previous = row
        if row.frame - prior.frame != rules["max_sample_gap_frames"]:
            if state.pending is not None:
                close(state, row.frame, "sample_gap")
            state.origin = stable(row.y)
            continue
        direction = _direction(prior, row, line)
        if counter == "legacy":
            key = (row.track_id, direction)
            if direction and key not in emitted:
                event = _arrival(prior, row, direction, line)
                if inside(event):
                    emissions.append(Emission(event, row.frame))
                    emitted.add(key)
            continue
        if not state.origin:
            state.origin = stable(row.y)
            continue  # Unknown origin cannot infer a passage, even on this sample.
        if state.pending is not None and (row.y - line) * state.origin > 0:
            close(state, row.frame, "return_to_origin")
        if direction == -state.origin:
            # Another toward-opposite arrival requires a strict origin return
            # first, which closes the old pending state above/on an earlier row.
            if state.pending is not None:
                raise ValueError("pending arrival was not canceled before a new arrival")
            state.pending = (_arrival(prior, row, direction, line), row.frame)
        if stable(row.y) == -state.origin:
            if state.pending is None:
                raise ValueError("opposite stable side without an adjacent pending arrival")
            event, _ = state.pending
            key = (row.track_id, event.direction)
            disposition = "outside_segment" if not inside(event) else (
                "already_emitted" if key in emitted else "emitted"
            )
            if disposition == "emitted":
                emissions.append(Emission(event, row.frame))
                emitted.add(key)
            close(state, row.frame, disposition)
            state.origin = -state.origin  # Also transition after rejected confirmations.
    for state in states.values():
        if state.pending is not None:
            close(state, None, "end_unconfirmed")
    emissions.sort(key=lambda item: (
        item.event.frame_time, item.event.track_id, item.event.direction,
    ))
    records.sort(key=lambda item: (
        item.event.frame_time, item.event.track_id, item.event.direction,
    ))
    return CountResult(counter, tuple(emissions), tuple(records))
