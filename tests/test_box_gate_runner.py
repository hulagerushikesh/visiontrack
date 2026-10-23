"""Replay plumbing with test doubles only, not new ablation tracker outcomes."""

import copy
import json
from dataclasses import asdict, fields, replace
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import box_gate_runner as runner
from experiments.box_gate_scene import generate_inputs
from experiments.traffic_protocol import load_frozen_protocol
from experiments.traffic_report import _sha
from visiontrack.detection.base import Detection
from visiontrack.tracking.config import TrackerConfig


@pytest.fixture(autouse=True)
def forbid_actual_tracker(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("replay adapter tests must not construct the actual tracker or old scenes")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr("experiments.traffic_scene.generate_scene", forbidden)


class Double:
    """Echo the detector boxes under ordered local IDs, not tracking logic."""

    def __init__(self, settings):
        self.cfg = TrackerConfig(**settings)
        self.frame_index = -1
        self.reset_count = 0
        self.handoffs = []

    def update(self, detections):
        self.frame_index += 1
        self.handoffs.append([
            {"box": d.xyxy.copy(), "score": d.score, "class_id": d.class_id,
             "feature": d.feature, "fields": {f.name for f in fields(d)},
             "writable": d.xyxy.flags.writeable}
            for d in detections
        ])
        return [SimpleNamespace(
            frame=self.frame_index, track_id=index + 20, xyxy=d.xyxy.copy(),
            score=d.score, class_id=d.class_id,
        ) for index, d in enumerate(detections)]

    def reset(self):
        self.frame_index = -1
        self.reset_count += 1


@pytest.fixture
def doubles(monkeypatch):
    instances = []

    def construct(settings):
        instance = Double(settings)
        instances.append(instance)
        return instance

    monkeypatch.setattr(runner, "_construct", construct)
    return instances


def run(**overrides):
    return runner.run_development(**{
        "scenario": "gate_dev_solo", "seed": 2001, "condition": "control", **overrides,
    })


@pytest.mark.parametrize("scenario", ["gate_dev_solo", "gate_dev_separated", "gate_dev_close"])
@pytest.mark.parametrize("condition", ["control", "perspective_only", "box_error_only", "combined"])
def test_paired_handoff_config_isolation_replay_and_scoring(doubles, scenario, condition):
    result = run(scenario=scenario, condition=condition)
    scene = generate_inputs(split="development", scenario=scenario, seed=2001, condition=condition)
    parent, _ = load_frozen_protocol()
    assert [v["id"] for v in result["variants"]] == ["baseline", "gate_off"]
    assert len(doubles) == len({id(t) for t in doubles}) == 4
    assert len({id(t.cfg) for t in doubles}) == 4
    assert [t.reset_count for t in doubles] == [1, 0, 1, 0]
    assert [len(t.handoffs) for t in doubles] == [600, 300, 600, 300]
    assert [t.cfg.use_mahalanobis_gating for t in doubles] == [True, True, False, False]
    for instance in doubles:
        for index, received in enumerate(instance.handoffs):
            frame = index % 300
            assert len(received) == len(scene.object_ids)
            for column, d in enumerate(received):
                np.testing.assert_array_equal(d["box"], scene.observed_boxes[frame, column])
                assert d["fields"] == {"xyxy", "score", "class_id", "feature"}
                assert d["score"] == .9 and d["class_id"] == 0 and d["feature"] is None
                assert d["writable"]
    for variant in result["variants"]:
        expected = {**parent["tracker_config"]}
        if variant["id"] == "gate_off":
            expected["use_mahalanobis_gating"] = False
        assert variant["config"] == expected
        assert variant["config_sha256"] == _sha(expected)
        replay = variant["replay"]
        assert replay["pass_order"] == ["fresh", "reset", "independent_fresh"]
        assert replay["passes"] == 3 and replay["updates_per_pass"] == 300
        assert replay["reset_equal"] and replay["fresh_equal"]
        assert replay["detection_receipts"] == [scene.detection_manifest()] * 3
        assert variant["output_sha256"] == _sha(variant["output"])
        assert variant["scoring"]["public_rows_sha256"] == variant["output_sha256"]
        assert variant["scoring"]["input"] == result["input"] == scene.manifest()
        assert len(variant["scoring"]["endpoints"]) == 37
    assert set(result["candidate_minus_baseline"].values()) <= {0, None}
    assert result["heldout_tracking_executed"] is result["complete_study_report"] is False
    assert "decision" not in result
    assert result["environment"]["numpy"] == np.__version__
    assert result["source"]["actual_revision"]
    assert "experiments/box_gate_runner.py" in result["source"]["experiment_sha256"]
    payload = json.loads(json.dumps(result, allow_nan=False))
    digest = payload.pop("record_sha256")
    assert digest == _sha(payload)


@pytest.mark.parametrize("selectors", [
    {"scenario": "gate_test_solo", "seed": 4001}, {"seed": 101}, {"seed": True},
    {"seed": 2001.}, {"scenario": "solo"}, {"condition": "unknown"},
])
def test_unregistered_selectors_fail_before_construction(doubles, selectors):
    with pytest.raises(ValueError):
        run(**selectors)
    assert doubles == []


@pytest.mark.parametrize("override", [
    {"split": "heldout"}, {"variant": "gate_off"},
    {"config": {}}, {"use_mahalanobis_gating": False},
])
def test_no_split_or_arbitrary_config_override(doubles, override):
    with pytest.raises(TypeError):
        run(**override)
    assert doubles == []


def test_reset_failure_is_not_repaired(doubles, monkeypatch):
    monkeypatch.setattr(Double, "reset", lambda self: None)
    with pytest.raises(ValueError, match="start at frame"):
        run()


def test_fresh_instance_and_config_aliases_fail(doubles, monkeypatch):
    original = runner._construct
    cached = []

    def reused(settings):
        if not cached:
            cached.append(original(settings))
        return cached[0]

    monkeypatch.setattr(runner, "_construct", reused)
    with pytest.raises(ValueError, match="independent tracker"):
        run()
    monkeypatch.setattr(runner, "_construct", original)
    first = []

    def shared_config(settings):
        instance = original(settings)
        if first:
            instance.cfg = first[0].cfg
        else:
            first.append(instance)
        return instance

    monkeypatch.setattr(runner, "_construct", shared_config)
    with pytest.raises(ValueError, match="independent tracker/config"):
        run()


def test_candidate_cannot_reuse_any_baseline_instance(doubles, monkeypatch):
    original = runner._construct

    def reused(settings):
        return original(settings) if len(doubles) < 2 else doubles[0]

    monkeypatch.setattr(runner, "_construct", reused)
    with pytest.raises(ValueError, match="isolated tracker/config"):
        run()


def test_reset_output_difference_fails(doubles, monkeypatch):
    original = Double.update

    def changed(self, detections):
        observations = original(self, detections)
        if self.reset_count:
            for row in observations:
                row.track_id += 1
        return observations

    monkeypatch.setattr(Double, "update", changed)
    with pytest.raises(ValueError, match="output mismatch"):
        run()


def test_fresh_output_difference_fails(doubles, monkeypatch):
    original = Double.update

    def changed(self, detections):
        observations = original(self, detections)
        if len(doubles) >= 2 and self is doubles[1]:
            for row in observations:
                row.track_id += 1
        return observations

    monkeypatch.setattr(Double, "update", changed)
    with pytest.raises(ValueError, match="output mismatch"):
        run()


def test_box_mutation_is_isolated_between_all_passes(doubles, monkeypatch):
    original = Double.update

    def mutate(self, detections):
        observations = original(self, detections)
        for d in detections:
            d.xyxy[:] = 0
        return observations

    monkeypatch.setattr(Double, "update", mutate)
    result = run()
    assert result["variants"][0]["output_sha256"] == result["variants"][1]["output_sha256"]
    assert all(np.all(t.handoffs[0][0]["box"] > 0) for t in doubles)


@pytest.mark.parametrize("fault", ["frame", "duplicate", "box", "score", "class", "id"])
def test_invalid_observations_fail_closed(doubles, monkeypatch, fault):
    original = Double.update

    def broken(self, detections):
        rows = original(self, detections)
        if fault == "frame":
            rows[0].frame = True
        elif fault == "duplicate":
            rows.append(copy.deepcopy(rows[0]))
        elif fault == "box":
            rows[0].xyxy[:] = np.nan
        elif fault == "score":
            rows[0].score = True
        elif fault == "class":
            rows[0].class_id = True
        else:
            rows[0].track_id = 2**63
        return rows

    monkeypatch.setattr(Double, "update", broken)
    with pytest.raises(ValueError):
        run()


@pytest.mark.parametrize("fault", ["advance", "config", "start"])
def test_frame_and_config_state_changes_fail(doubles, monkeypatch, fault):
    original = Double.update

    def changed(self, detections):
        rows = original(self, detections)
        if fault == "advance":
            self.frame_index += 1
        else:
            self.cfg.n_init = 99
        return rows

    if fault == "start":
        original_construct = runner._construct

        def started(settings):
            instance = original_construct(settings)
            instance.frame_index = 0
            return instance

        monkeypatch.setattr(runner, "_construct", started)
    else:
        monkeypatch.setattr(Double, "update", changed)
    with pytest.raises(ValueError):
        run()


def test_detection_payload_tampering_is_detected(doubles, monkeypatch):
    original = Detection.__post_init__

    def changed(self):
        original(self)
        self.xyxy += .01

    monkeypatch.setattr(Detection, "__post_init__", changed)
    with pytest.raises(ValueError, match="actual Detection stream"):
        run()


@pytest.mark.parametrize("field,value", [
    ("score", .8), ("class_id", 1), ("feature", np.zeros(2)),
])
def test_detection_metadata_drift_fails_before_update(doubles, monkeypatch, field, value):
    original = Detection.__post_init__

    def changed(self):
        original(self)
        setattr(self, field, value)

    monkeypatch.setattr(Detection, "__post_init__", changed)
    with pytest.raises(ValueError, match="Detection handoff"):
        run()
    assert len(doubles) == 1 and doubles[0].handoffs == []


def test_input_regeneration_cannot_be_bypassed(doubles, monkeypatch):
    scene = generate_inputs(
        split="development", scenario="gate_dev_solo", seed=2001, condition="control",
    )
    boxes = scene.observed_boxes.copy()
    boxes[0, 0, 0] += 1
    forged = replace(scene, observed_boxes=boxes)
    monkeypatch.setattr(runner, "generate_inputs", lambda **kwargs: forged)
    with pytest.raises(ValueError, match="input differs"):
        run()
    assert doubles == []


def test_import_origin_rejected_before_construction(doubles, monkeypatch):
    def fail():
        raise ValueError("wrong import")

    monkeypatch.setattr(runner, "_check_import_origins", fail)
    with pytest.raises(ValueError, match="wrong import"):
        run()
    assert doubles == []


def test_wrong_initial_config_fails_before_update(doubles, monkeypatch):
    original = runner._construct

    def changed(settings):
        instance = original(settings)
        instance.cfg.n_init = 9
        return instance

    monkeypatch.setattr(runner, "_construct", changed)
    with pytest.raises(ValueError, match="configuration changed"):
        run()
    assert len(doubles) == 1 and doubles[0].handoffs == []


def test_registration_drift_at_completion_is_detected(doubles, monkeypatch):
    registration, _ = runner.load_registration()
    monkeypatch.setattr(runner, "load_registration", lambda: (registration, {"changed": "hash"}))
    with pytest.raises(ValueError, match="source, inputs or registration changed"):
        run()


def test_source_drift_before_any_construction(doubles, monkeypatch):
    def fail(*args):
        raise ValueError("baseline drift")

    monkeypatch.setattr(runner, "_verify_tree", fail)
    with pytest.raises(ValueError, match="baseline drift"):
        run()
    assert doubles == []


def test_harness_drift_at_completion_is_detected(doubles, monkeypatch):
    snapshots = iter([{"revision": "before"}, {"revision": "after"}])
    monkeypatch.setattr(runner, "_snapshot", lambda: next(snapshots))
    with pytest.raises(ValueError, match="source, inputs or registration changed"):
        run()


def test_scoring_output_lineage_mismatch_fails(doubles, monkeypatch):
    original = runner.score_development

    def changed(*args):
        result = original(*args)
        result["public_rows_sha256"] = "wrong"
        return result

    monkeypatch.setattr(runner, "score_development", changed)
    with pytest.raises(ValueError, match="scorer lineage"):
        run()


def test_real_factory_constructs_only_explicit_config_without_running_tracker(monkeypatch):
    parent, _ = load_frozen_protocol()
    calls = []

    def inspect(config):
        calls.append(asdict(config))
        return SimpleNamespace(cfg=config)

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker", inspect)
    result = runner._construct(parent["tracker_config"])
    assert calls == [parent["tracker_config"]] == [asdict(result.cfg)]
    with pytest.raises(ValueError, match="fields differ"):
        runner._construct({})
