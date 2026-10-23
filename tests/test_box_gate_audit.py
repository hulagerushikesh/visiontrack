"""Hand-worked saved-record arithmetic tests; no experiment/tracker execution."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from experiments import box_gate_audit as audit


def variant():
    truth = {"track_id": 1, "direction": 1, "frame_time": 1.5, "x": 0.0}
    predicted = {"track_id": 4, "direction": 1, "frame_time": 2.0, "x": 0.2}
    extra = {"track_id": 9, "direction": -1, "frame_time": 3.0, "x": 0.1}
    crossing_summary = {
        "truth_count": 1,
        "predicted_count": 2,
        "matched_count": 1,
        "missed_events": 0,
        "extra_events": 1,
        "event_error": 1,
        "recall": 1.0,
        "matched_time_abs_mean_frames": 0.5,
        "matched_x_abs_mean_world": 0.2,
        "matched_wrong_window_events": 1,
        "window_count_abs_error": 3,
    }
    crossing = {
        "truth_events": [truth],
        "predicted_events": [predicted, extra],
        "matches": [{"truth": truth, "predicted": predicted}],
        "unmatched_truth": [],
        "unmatched_predictions": [extra],
        "rules": {
            "max_match_time_error_frames": 1,
            "max_match_x_error_world_units": 1,
            "count_window_frames": 2,
        },
        "counts_by_direction_window": {
            "positive": {"truth": [1, 0], "predicted": [0, 1], "predicted_minus_truth": [-1, 1]},
            "negative": {"truth": [0, 0], "predicted": [0, 1], "predicted_minus_truth": [0, 1]},
        },
        "summary": crossing_summary,
    }
    samples = [
        {
            "frame": frame,
            "object_id": 1,
            "matched_track_id": identity,
            "matched_track_error": None
            if identity is None
            else {
                anchor: {"dx": 3.0, "dy": 4.0, "distance": 5.0}
                for anchor in ("bottom_centre", "box_centre")
            },
            "observation_error": {
                anchor: {"dx": 0.0, "dy": 0.0, "distance": 0.0}
                for anchor in ("bottom_centre", "box_centre")
            },
            "id_switch": frame == 2,
            "fragmentation": False,
        }
        for frame, identity in enumerate((None, 4, 9, None))
    ]
    endpoints = {
        f"crossing.{anchor}.{name}": value
        for anchor in ("bottom_centre", "box_centre")
        for name, value in crossing_summary.items()
    }
    endpoints.update(
        {
            "tracking.true_object_frames": 4,
            "tracking.matched_object_frames": 2,
            "tracking.missed_object_frames": 2,
            "tracking.matched_object_frame_fraction": 0.5,
            "tracking.id_switches": 1,
            "tracking.fragmentations": 0,
            "tracking.false_positive_rows": 1,
        }
    )
    for name, count, distance in (
        ("observation_contact_error", 4, 0.0),
        ("matched_track_contact_error", 2, 5.0),
    ):
        for anchor in ("bottom_centre", "box_centre"):
            endpoints[f"tracking.{name}.{anchor}.sample_count"] = count
            endpoints[f"tracking.{name}.{anchor}.mean_distance_world"] = distance
    return {
        "output": [
            {"frame": 1, "track_id": 4},
            {"frame": 2, "track_id": 9},
            {"frame": 3, "track_id": 8},
        ],
        "scoring": {
            "endpoints": endpoints,
            "diagnostics": {
                "samples": samples,
                "failures": [
                    {"event_type": name}
                    for name in (
                        "miss",
                        "id_switch",
                        "miss",
                        "false_positive",
                    )
                ],
            },
            "crossing": {
                anchor: copy.deepcopy(crossing)
                for anchor in (
                    "bottom_centre",
                    "box_centre",
                )
            },
        },
    }


def test_arithmetic_reconstructs_all_37_without_mutation():
    value = variant()
    before = copy.deepcopy(value)
    result = audit.reconstruct_endpoints(value, [1], 4)
    assert len(result) == 37
    assert result["crossing.bottom_centre.window_count_abs_error"] == 3
    assert result["tracking.false_positive_rows"] == 1
    assert value == before


@pytest.mark.parametrize(
    "change",
    [
        "sample_order",
        "sample_missing",
        "duplicate_output",
        "unknown_match",
        "missing_error",
        "failure_count",
        "distance",
        "endpoint",
        "crossing_count",
        "crossing_window",
        "crossing_match",
        "crossing_extra",
        "crossing_summary",
    ],
)
def test_inconsistent_saved_arithmetic_is_rejected(change):
    value = variant()
    scoring = value["scoring"]
    samples = scoring["diagnostics"]["samples"]
    crossing = scoring["crossing"]["bottom_centre"]
    if change == "sample_order":
        samples.reverse()
    elif change == "sample_missing":
        samples.pop()
    elif change == "duplicate_output":
        value["output"].append(copy.deepcopy(value["output"][0]))
    elif change == "unknown_match":
        samples[1]["matched_track_id"] = 99
    elif change == "missing_error":
        samples[1]["matched_track_error"] = None
    elif change == "failure_count":
        scoring["diagnostics"]["failures"].pop()
    elif change == "distance":
        samples[1]["matched_track_error"]["bottom_centre"]["distance"] = 4.0
    elif change == "endpoint":
        scoring["endpoints"]["tracking.id_switches"] = 0
    elif change == "crossing_count":
        crossing["summary"]["event_error"] = 0
    elif change == "crossing_window":
        crossing["counts_by_direction_window"]["positive"]["predicted"] = [1, 0]
    elif change == "crossing_match":
        crossing["matches"] = []
    elif change == "crossing_extra":
        crossing["unmatched_predictions"] = []
    else:
        crossing["summary"]["matched_wrong_window_events"] = 0
    with pytest.raises(ValueError):
        audit.reconstruct_endpoints(value, [1], 4)


def test_nulls_are_not_zero_in_seed_summaries():
    assert audit.descriptive([{"x": None}, {"x": 2.0}, {"x": 4.0}]) == {
        "x": {"defined_seeds": 2, "undefined_seeds": 1, "mean": 3.0, "min": 2.0, "max": 4.0},
    }
    assert audit.descriptive([{"x": None}])["x"]["mean"] is None


def test_no_matches_preserves_undefined_conditional_endpoints():
    value = variant()
    value["output"] = []
    scoring = value["scoring"]
    for sample in scoring["diagnostics"]["samples"]:
        sample.update(matched_track_id=None, matched_track_error=None, id_switch=False)
    scoring["diagnostics"]["failures"] = [{"event_type": "miss"} for _ in range(4)]
    scoring["endpoints"].update(
        {
            "tracking.matched_object_frames": 0,
            "tracking.missed_object_frames": 4,
            "tracking.matched_object_frame_fraction": 0.0,
            "tracking.id_switches": 0,
            "tracking.false_positive_rows": 0,
        }
    )
    for anchor in ("bottom_centre", "box_centre"):
        crossing = scoring["crossing"][anchor]
        crossing.update(predicted_events=[], matches=[], unmatched_predictions=[])
        crossing["unmatched_truth"] = copy.deepcopy(crossing["truth_events"])
        crossing["counts_by_direction_window"] = {
            "positive": {"truth": [1, 0], "predicted": [0, 0], "predicted_minus_truth": [-1, 0]},
            "negative": {"truth": [0, 0], "predicted": [0, 0], "predicted_minus_truth": [0, 0]},
        }
        crossing["summary"].update(
            predicted_count=0,
            matched_count=0,
            missed_events=1,
            extra_events=0,
            recall=0.0,
            matched_time_abs_mean_frames=None,
            matched_x_abs_mean_world=None,
            matched_wrong_window_events=0,
            window_count_abs_error=1,
        )
        scoring["endpoints"].update(
            {f"crossing.{anchor}.{name}": item for name, item in crossing["summary"].items()}
        )
        scoring["endpoints"][f"tracking.matched_track_contact_error.{anchor}.sample_count"] = 0
        scoring["endpoints"][
            f"tracking.matched_track_contact_error.{anchor}.mean_distance_world"
        ] = None
    result = audit.reconstruct_endpoints(value, [1], 4)
    assert result["crossing.bottom_centre.matched_time_abs_mean_frames"] is None
    assert result["tracking.matched_track_contact_error.bottom_centre.sample_count"] == 0


@pytest.mark.parametrize("value", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_bad_json_is_rejected(tmp_path, value):
    path = tmp_path / "input.json"
    path.write_text(value)
    with pytest.raises(ValueError):
        audit.load(path)


def test_digest_excludes_only_its_own_field():
    value = {"x": 1}
    value["digest"] = audit.sha(audit.canonical(value))
    audit.sealed(value, "digest")
    value["x"] = 2
    with pytest.raises(ValueError):
        audit.sealed(value, "digest")


@pytest.mark.parametrize("actual,expected", [(True, 1), (0, None), ([], {}), ([1], []), (1.1, 1.0)])
def test_mismatches_fail(actual, expected):
    with pytest.raises(ValueError):
        audit.compare(actual, expected, "fixture")


def test_auditor_imports_only_standard_library():
    tree = ast.parse(Path(audit.__file__).read_text())
    imports = [
        name
        for node in ast.walk(tree)
        for name in (
            [node.module]
            if isinstance(node, ast.ImportFrom)
            else [a.name for a in node.names]
            if isinstance(node, ast.Import)
            else []
        )
    ]
    assert not any(name.startswith(("visiontrack", "experiments", "numpy")) for name in imports)


def test_canonical_json_is_stable_and_nonfinite_is_rejected():
    assert audit.canonical({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert json.loads(audit.canonical({"x": None})) == {"x": None}
    with pytest.raises(ValueError):
        audit.canonical({"x": float("nan")})
