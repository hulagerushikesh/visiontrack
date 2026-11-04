"""Check the ambiguity construction independently of tracker accuracy."""
import copy
import hashlib

import pytest

from experiments import localization_observability as probe
from visiontrack import ByteTracker


def test_worlds_reconstruct_identical_inputs_but_have_different_reference_geometry():
    for _, _, _, worlds in probe.witnesses():
        changed, biased = worlds
        assert changed.reference[0] == biased.reference[0]
        assert changed.reference[-1] != biased.reference[-1]
        assert all(box == biased.reference[0] for box in biased.reference)
        assert all(noise == (0, 0, 0, 0) for noise in changed.error)
        assert max(abs(x) for noise in biased.error for x in noise) == 10
        assert changed.observations() == biased.observations()
        assert len(changed.observations()) == 12


@pytest.mark.parametrize("positions,expected", [
    ([99, 100, 101], 1), ([100, 101, 102], 0), ([101, 100, 99], 0),
    ([99, 100, 99, 100], 2), ([99, 99, 99], 0), ([], 0), ([100], 0),
])
def test_toy_crossing_boundary_convention(positions, expected):
    assert probe.positive_anchor_crossings(
        tuple((x - 1, 0, x + 1, 10) for x in positions), 0, 100) == expected
    assert probe.positive_anchor_crossings(
        tuple((0, x - 10, 2, x) for x in positions), 1, 100) == expected


def test_hidden_world_is_not_available_to_runtime(monkeypatch):
    rows = probe.witnesses()[0][3][0].observations()
    before = copy.deepcopy(rows)
    tracker = ByteTracker()
    actual = tracker.update
    calls = []

    def spy(detections):
        calls.append(detections)
        assert len(detections) == 1
        d = detections[0]
        assert d.score == .9 and d.class_id == 0 and d.feature is None
        assert not hasattr(d, "reference") and not hasattr(d, "error")
        return actual(detections)

    monkeypatch.setattr(tracker, "update", spy)
    outputs = probe.replay(rows, tracker)
    assert rows == before
    assert len(calls) == 12
    assert len(outputs) == 12
    assert sum(len(row["observations"]) for row in outputs) == 10


def test_report_retains_both_worlds_with_exact_repeatable_outputs():
    report = probe.run()
    assert report["synthetic_only"] is True
    assert report["accuracy_claim"] is report["novelty_claim"] is False
    assert "experiments/localization_observability.py" in report["source_sha256"]
    for path, expected in report["source_sha256"].items():
        assert hashlib.sha256((probe.ROOT / path).read_bytes()).hexdigest() == expected
    assert len(report["cases"]) == 2
    for case in report["cases"]:
        assert [w["reference_positive_crossings"] for w in case["worlds"]] == [1, 0]
        assert case["input_sha256"] == probe.digest(case["observations"])
        assert case["output_sha256"] == probe.digest(case["tracker_outputs"])
        assert case["exact_input_agreement"] and case["exact_output_agreement"]
        assert case["reset_output_agreement"]
    assert probe.encoded(report) == probe.encoded(probe.run())


def test_report_refuses_to_pin_checkout_sources_for_another_install(monkeypatch):
    monkeypatch.setattr(probe.visiontrack, "__file__", "/another/install/visiontrack/__init__.py")
    with pytest.raises(ValueError, match="checkout sources"):
        probe.run()
