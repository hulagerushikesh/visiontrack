"""Protect the complete development result and the public interpretation."""
import hashlib
import itertools
import json
from pathlib import Path

from experiments.initiation_threshold import CASES, SCORES, SPEEDS, digest, scene

SUMMARY = Path(__file__).parents[1] / "experiments/initiation_threshold_v1_results.json"


def results():
    return json.loads(SUMMARY.read_text())


def test_complete_saved_result_has_fixed_method_and_all_inputs():
    assert hashlib.sha256(SUMMARY.read_bytes()).hexdigest() == (
        "fb947930ba3b1a2bf73596a5ffcdb5f76b1d56372edbb4ef47c93e7dbd20fc8d")
    summary = results()
    assert summary["method"]["revision"] == "7cf2be7dcbf0457df32417dd1dae764531c06522"
    assert summary["paired_cells"] == len(summary["cells"]) == 54
    assert summary["tracker_passes"] == 324
    selectors = {(c["case"], c["score"], c["speed"]) for c in summary["cells"]}
    assert selectors == set(itertools.product(CASES, SCORES, SPEEDS))
    for cell in summary["cells"]:
        inputs = scene(cell["case"], cell["score"], cell["speed"])
        assert digest(inputs) == cell["input_sha256"]
        assert digest([r["detections"] for r in inputs]) == cell["detector_sha256"]
        for variant in ("baseline", "candidate"):
            score = cell[variant]
            assert score["mot"]["num_gt"] == sum(len(r["truth"]) for r in inputs)
            assert score["public_boxes"] == (score["mot"]["true_positives"] +
                                               score["mot"]["false_positives"])
            assert score["mot"]["num_gt"] == (score["mot"]["true_positives"] +
                                                 score["mot"]["false_negatives"])
            assert score["births"] == score["unconfirmed_births"] + score["public_ids"]


def test_controls_are_exact_and_truth_never_changes_tracker_output():
    cells = results()["cells"]
    controls = [c for c in cells if c["score"] in (.54, .61)]
    assert len(controls) == 36
    assert all(c["output_sha256"]["baseline"] == c["output_sha256"]["candidate"]
               and c["baseline"] == c["candidate"] for c in controls)
    by_key = {(c["case"], c["score"], c["speed"]): c for c in cells}
    for confidence, speed in itertools.product(SCORES, SPEEDS):
        true = by_key["steady_true", confidence, speed]
        false = by_key["persistent_false", confidence, speed]
        assert true["detector_sha256"] == false["detector_sha256"]
        assert true["output_sha256"] == false["output_sha256"]


def test_registered_no_harm_gate_cannot_accept_candidate():
    summary = results()
    harms, recoveries = [], []
    for cell in summary["cells"]:
        base, candidate = cell["baseline"], cell["candidate"]
        if (candidate["mot"]["false_positives"] > base["mot"]["false_positives"] or
                candidate["crossings"]["fp"] > base["crossings"]["fp"] or
                candidate["mot"]["id_switches"] > base["mot"]["id_switches"] or
                candidate["extra_matched_ids"] > base["extra_matched_ids"]):
            harms.append((cell["case"], cell["score"], cell["speed"]))
        if candidate["crossings"]["tp"] > base["crossings"]["tp"]:
            recoveries.append(cell)
    assert len(harms) == 6 and len(recoveries) == 10
    assert {case for case, _, _ in harms} == {
        "persistent_false", "true_and_clutter", "long_absence"}
    assert all(confidence == .57 for _, confidence, _ in harms)
    assert summary["recommend_default_change"] is False
    assert summary["real_world_accuracy_claim"] is False


def test_confirmation_noise_and_long_absence_explanations_hold_at_both_speeds():
    for cell in results()["cells"]:
        if cell["score"] != .57:
            continue
        candidate = cell["candidate"]
        if cell["case"] in {"persistent_false", "true_and_clutter"}:
            assert candidate["mot"]["false_positives"] == 10
            assert candidate["crossings"]["fp"] == 1
        elif cell["case"] == "brief_false":
            assert candidate["births"] == candidate["unconfirmed_births"] == 1
            assert candidate["public_boxes"] == 0
        elif cell["case"] == "confirmed_gap":
            assert candidate["crossings"]["fn"] == 1
        elif cell["case"] == "long_absence":
            assert candidate["extra_matched_ids"] == candidate["mot"]["id_switches"] == 1
            assert candidate["crossings"]["tp"] == 2
        elif cell["case"] == "late_strong":
            assert cell["baseline"]["confirmation_delays"][0]["delay_frames"] == 6
            assert candidate["confirmation_delays"][0]["delay_frames"] == 2
