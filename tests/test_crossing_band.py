"""Authored counter diagrams only: no registered scenes/noise/tracker outcomes."""

from dataclasses import FrozenInstanceError, asdict
from itertools import permutations, product
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from experiments import crossing_band
from experiments.crossing_band import Emission, count_crossings
from experiments.traffic_crossing import (
    AnchorSample,
    CrossingEvent,
    extract_crossings,
    score_crossings,
)
from experiments.traffic_protocol import ROOT


def path(ys, *, xs=None, frames=None, identifier=1):
    xs = [0.0] * len(ys) if xs is None else xs
    frames = range(len(ys)) if frames is None else frames
    return tuple(AnchorSample(f, identifier, x, y)
                 for f, x, y in zip(frames, xs, ys, strict=True))


def band(rows):
    return count_crossings(rows, counter="band")


def legacy(rows):
    return count_crossings(rows, counter="legacy")


@pytest.mark.parametrize("ys, expected", [
    ([9, 11], [(1, 0.5, 1)]),
    ([11, 9], [(-1, 0.5, 1)]),
    ([9.75, 10, 10, 10.25], [(1, 1.0, 3)]),
    ([10.25, 10, 10, 9.75], [(-1, 1.0, 3)]),
    ([9, 10.05, 9.8], []),
    ([11, 9.95, 10.2], []),
    ([9.9, 10.3], []),
    ([10.1, 9.7], []),
    ([10, 10, 11], []),
    ([10, 9], []),
    ([9, 10.1], []),
    ([11, 9.9], []),
    ([9, 11, 9, 11, 9], [(1, 0.5, 1), (-1, 1.5, 2)]),
    ([10, 11, 9], [(-1, 1.5, 2)]),
])
def test_exact_boundaries_line_dwells_unknown_origin_and_first_per_direction(ys, expected):
    result = band(path(ys))
    assert [(e.event.direction, e.event.frame_time, e.emission_frame)
            for e in result.emissions] == expected
    assert result.diagnostics["pending_arrivals"] == sum(
        value for key, value in result.diagnostics.items() if key != "pending_arrivals"
    )


@pytest.mark.parametrize("sign", [-1, 1])
def test_exact_line_then_strict_origin_return_cancels_even_inside_band(sign):
    rows = path([10 - sign, 10, 10 - sign * 0.1, 10 + sign * 0.1, 10 + sign])
    result = band(rows)
    assert len(result.emissions) == 1
    arrival = result.emissions[0]
    assert arrival.event.frame_time == 2.5
    assert arrival.emission_frame == 4
    assert arrival.event.direction == sign
    assert [r.disposition for r in result.pending_records] == ["return_to_origin", "emitted"]
    assert result.pending_records[0].event.frame_time == 1
    assert result.pending_records[0].closed_frame == 2


def test_latest_arrival_after_two_canceled_excursions_is_retained_not_first():
    result = band(path([9, 10.1, 9.9, 10, 9.9, 10.1, 10.25]))
    assert result.events == (CrossingEvent(1, 1, 4.5, 0),)
    assert result.emissions[0].emission_frame == 6
    assert result.diagnostics["return_to_origin"] == 2


@pytest.mark.parametrize("x, count", [
    (-6, 1), (np.nextafter(-6.0, -np.inf), 0),
    (np.nextafter(6.0, -np.inf), 1), (6, 0),
])
def test_segment_is_half_open_without_epsilon(x, count):
    result = band(path([9, 11], xs=[x, x]))
    assert len(result.events) == count
    assert result.diagnostics["outside_segment"] == 1 - count


@pytest.mark.parametrize("sign", [-1, 1])
def test_stable_boundary_has_no_epsilon_and_inside_origin_is_not_inferred(sign):
    boundary = 10 + sign * 0.25
    just_inside = np.nextafter(boundary, 10.0)
    assert band(path([10 - sign, just_inside])).events == ()
    assert len(band(path([10 - sign, boundary])).events) == 1
    assert band(path([just_inside, 10 - sign])).events == ()


def test_segment_uses_interpolated_crossing_x_not_confirmation_x():
    valid = band(path([9.75, 10, 10.25], xs=[0, 0, 20]))
    invalid = band(path([9.75, 10, 10.25], xs=[20, 20, 0]))
    assert valid.events == (CrossingEvent(1, 1, 1.0, 0),)
    assert invalid.events == ()
    assert invalid.diagnostics["outside_segment"] == 1
    assert band(path([9, 11], xs=[-20, 20])).events == (CrossingEvent(1, 1, 0.5, 0),)


def test_outside_confirmation_transitions_origin_without_consuming_first_valid_ledger():
    result = band(path([9, 11, 9, 11], xs=[20, 20, 0, 0]))
    assert result.events == (CrossingEvent(1, 1, 2.5, 0),)
    assert result.diagnostics["outside_segment"] == 2
    assert result.diagnostics["emitted"] == 1


def test_duplicate_confirmation_still_transitions_and_ledger_survives_gaps():
    rows = path([9, 11, 9, 11, 9, 11, 9], frames=[0, 1, 3, 4, 5, 6, 7])
    result = band(rows)
    assert result.events == (CrossingEvent(1, 1, 0.5, 0), CrossingEvent(1, -1, 4.5, 0))
    assert result.diagnostics["already_emitted"] == 3


def test_gap_cancels_pending_and_reinitializes_from_new_row_without_interpolation():
    result = band(path([9, 10.1, 11, 9], frames=[0, 1, 3, 4]))
    assert result.events == (CrossingEvent(1, -1, 3.5, 0),)
    canceled, confirmed = result.pending_records
    assert canceled.disposition == "sample_gap" and canceled.closed_frame == 3
    assert confirmed.disposition == "emitted"
    assert band(path([9, 11], frames=[0, 2])).events == ()


def test_gap_reinitialization_inside_band_has_unknown_origin():
    result = band(path([9, 10.1, 10.1, 11, 9], frames=[0, 1, 3, 4, 5]))
    assert result.events == (CrossingEvent(1, -1, 4.5, 0),)
    assert result.diagnostics["sample_gap"] == 1


def test_end_pending_is_not_flushed_and_retains_original_arrival():
    result = band(path([9, 10, 10.1]))
    assert result.events == () and result.maximum_delay_frames is None
    assert result.diagnostics["end_unconfirmed"] == 1
    record, = result.pending_records
    assert record.event == CrossingEvent(1, 1, 1, 0)
    assert record.arrival_frame == 1 and record.closed_frame is None


def test_final_frame_can_confirm_but_never_creates_a_flush_after_grid_end():
    result = band(path([9, 10, 10.25], frames=[297, 298, 299]))
    assert result.emissions == (Emission(CrossingEvent(1, 1, 298, 0), 299),)
    unfinished = band(path([9, 10, 10.1], frames=[297, 298, 299]))
    assert not unfinished.events and unfinished.diagnostics["end_unconfirmed"] == 1


def test_ids_are_never_joined_and_empty_or_one_row_input_creates_no_events():
    rows = [AnchorSample(0, 7, 0, 9), AnchorSample(1, 12, 0, 11)]
    for samples in ([], rows, rows[:1]):
        for mode in ("band", "legacy"):
            result = count_crossings(samples, counter=mode)
            assert not result.events and not result.pending_records
            assert result.maximum_delay_frames is None


def test_input_permutations_interleaving_and_local_call_state_are_deterministic():
    rows = path([9, 11], identifier=7) + path([11, 9], identifier=12)
    expected = band(rows)
    for order in permutations(rows):
        assert band(order) == expected
    assert expected.events == (CrossingEvent(7, 1, 0.5, 0), CrossingEvent(12, -1, 0.5, 0))


def test_event_order_remains_arrival_order_even_when_confirmation_order_differs():
    rows = path([9, 10, 10.1, 10.1, 10.25], identifier=1)
    rows += path([9, 9, 9, 11], identifier=2)
    result = band(rows)
    assert [e.event.frame_time for e in result.emissions] == [1, 2.5]
    assert [e.emission_frame for e in result.emissions] == [4, 3]


def test_interpolation_and_reporting_times_preserve_float64_arithmetic():
    rows = path([9, 12], xs=[-2, 4], frames=[29, 30])
    for result in (legacy(rows), band(rows)):
        assert result.events == (CrossingEvent(1, 1, 29 + 1 / 3, 0),)
        assert result.emissions[0].emission_frame == 30
        assert result.maximum_delay_frames == 30 - (29 + 1 / 3)


def test_arrival_frame_is_not_ceil_of_rounded_interpolated_time():
    rows = path([np.nextafter(10.0, -np.inf), 1e308], frames=[29, 30])
    result = legacy(rows)
    assert result.events[0].frame_time == 29.0  # Tiny positive fraction rounds away.
    assert result.emissions[0].emission_frame == 30  # Not ceil(29.0)!


def test_excessive_confirmation_delay_is_retained_not_hidden_by_suppression():
    rows = path([9, 10] + [10.1] * 17 + [10.25])
    result = band(rows)
    assert result.events == (CrossingEvent(1, 1, 1, 0),)
    assert result.emissions[0].emission_frame == 19
    assert result.maximum_delay_frames == 18 > 15
    assert legacy(rows).maximum_delay_frames == 0


def test_backdating_does_not_hide_reporting_in_a_different_count_window():
    rows = path([9.75, 10.1, 10.25], frames=[28, 29, 30])
    candidate, baseline = band(rows), legacy(rows)
    assert candidate.events == baseline.events
    assert candidate.emissions[0].event.frame_time < 30
    assert baseline.emissions[0].emission_frame // 30 == 0
    assert candidate.emissions[0].emission_frame // 30 == 1


@pytest.mark.parametrize("ys", [[9, 10.1, 9], [9.9, 11], [9, 10.1]])
def test_genuine_short_start_and_end_passages_remain_misses_not_redefined_truth(ys):
    rows = path(ys)
    truth = extract_crossings(rows)
    assert truth and legacy(rows).events == truth
    assert band(rows).events == ()
    result = score_crossings(truth, band(rows).events)
    assert result["summary"]["missed_events"] == len(truth)
    assert result["summary"]["matched_time_abs_mean_frames"] is None


def test_authored_line_jitter_can_be_suppressed_but_does_not_prove_accuracy():
    rows = path([9.7, 10.05, 9.8])
    assert len(legacy(rows).events) == 2
    assert not band(rows).events
    assert band(rows).diagnostics["return_to_origin"] == 1
    # These exact observations can also describe genuine shallow movement.
    # The counter has no truth input and cannot distinguish the two explanations.


def test_legacy_matches_frozen_extractor_on_exhaustive_small_authored_diagrams(monkeypatch):
    # Avoid thousands of repeated disk reads; these are exact already-verified
    # definitions, not a substitute for the real loader checks in other tests.
    registration = crossing_band.load_registration()
    parent = crossing_band.load_frozen_protocol()
    monkeypatch.setattr(crossing_band, "load_registration", lambda: registration)
    monkeypatch.setattr(crossing_band, "load_frozen_protocol", lambda: parent)
    with patch("experiments.traffic_crossing.load_frozen_protocol", return_value=parent):
        for ys in product([9.5, 9.9, 10, 10.1, 10.5], repeat=4):
            rows = path(ys, xs=[-8, 0, 8, 0])
            assert legacy(rows).events == extract_crossings(rows)
            candidate = band(rows)
            assert len({(e.track_id, e.direction) for e in candidate.events}) == len(
                candidate.events
            )
            assert len(candidate.pending_records) <= len(rows) - 1
            for emission in candidate.emissions:
                event = emission.event
                assert emission.delay_frames >= 0
                # Actual reporting row must be on the opposite stable side.
                assert event.direction * (rows[emission.emission_frame].y - 10) >= 0.25
                assert -6 <= event.x < 6


@pytest.mark.parametrize("mode", ["band", "legacy"])
@pytest.mark.parametrize("rows, message", [
    ([{}], "AnchorSample"),
    (path([9, 11], frames=[0, 300]), "frame grid"),
    (path([9, 11], frames=[1, 1]), "duplicate"),
])
def test_invalid_supplied_records_fail_instead_of_being_dropped(mode, rows, message):
    with pytest.raises(ValueError, match=message):
        count_crossings(rows, counter=mode)


@pytest.mark.parametrize("mode", ["band", "legacy"])
def test_bounded_input_stops_without_silent_truncation(mode, monkeypatch):
    monkeypatch.setattr(crossing_band, "MAX_SAMPLES", 2)
    assert count_crossings(path([9, 11]), counter=mode).events
    with pytest.raises(ValueError, match="capacity"):
        count_crossings(iter(path([9, 11, 9])), counter=mode)


@pytest.mark.parametrize("ys, xs", [([1e308, -1e308], [0, 0]), ([9, 11], [-1e308, 1e308])])
@pytest.mark.parametrize("mode", ["band", "legacy"])
def test_nonfinite_interpolation_arithmetic_fails_explicitly(ys, xs, mode):
    with pytest.raises(ValueError, match="nonfinite"):
        count_crossings(path(ys, xs=xs), counter=mode)


def test_registration_integrity_is_required_without_tracker_noise_or_writes(monkeypatch):
    def fail():
        raise ValueError("registration drift")

    monkeypatch.setattr(crossing_band, "load_registration", fail)
    with pytest.raises(ValueError, match="registration drift"):
        band(path([9, 11]))


def test_counter_reads_definitions_only_and_never_generates_noise_or_runs_tracker(monkeypatch):
    reads = set()
    original_open = Path.open

    def checked_open(self, mode="r", *args, **kwargs):
        assert mode in ("r", "rb"), "counter must not write files"
        reads.add(self.relative_to(ROOT).as_posix())
        return original_open(self, mode, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("no tracker or random observations in this unit step")

    monkeypatch.setattr(Path, "open", checked_open)
    monkeypatch.setattr(np.random, "PCG64", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    assert band(path([9, 11])).events == legacy(path([9, 11])).events
    assert reads == {
        f"experiments/{prefix}_protocol_v1.{extension}"
        for prefix in ("traffic", "box_gate", "crossing_band")
        for extension in ("json", "sha256")
    } | {
        "docs/TRAFFIC_RELIABILITY_PROTOCOL.md", "docs/BOX_GATE_ABLATION_PROTOCOL.md",
        "docs/CROSSING_BAND_PROTOCOL.md",
    }


def test_no_parameter_sweep_mode_or_truth_argument():
    with pytest.raises(ValueError, match="legacy or band"):
        count_crossings([], counter="tuned")
    with pytest.raises(TypeError):
        count_crossings([], counter="band", half_width=0.1)
    with pytest.raises(TypeError):
        count_crossings([], counter="band", truth=[])


def test_input_and_result_records_are_immutable_and_calls_have_no_hidden_ledger():
    rows = list(path([9, 10, 10.25]))
    snapshot = tuple(asdict(r) for r in rows)
    first = band(iter(rows))
    assert tuple(asdict(r) for r in rows) == snapshot
    assert band(rows) == first
    with pytest.raises(FrozenInstanceError):
        first.emissions[0].emission_frame = 2
    with pytest.raises(FrozenInstanceError):
        first.pending_records[0].disposition = "end_unconfirmed"
    altered = first.diagnostics
    altered["pending_arrivals"] = -1
    assert first.diagnostics["pending_arrivals"] == 1


@pytest.mark.parametrize("frame", [-1, True, 1.5, 300, 0])
def test_emission_rejects_invalid_or_backdated_reporting_frames(frame):
    with pytest.raises(ValueError, match="emission frame"):
        Emission(CrossingEvent(1, 1, 0.5, 0), frame)


def test_emission_requires_a_typed_event():
    with pytest.raises(ValueError, match="CrossingEvent"):
        Emission({}, 1)
