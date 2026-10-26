"""Authored geometry/scoring and replay doubles; no actual study tracker outcomes."""
import copy
import json
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import observation_availability as study
from visiontrack.eval.geometry import metric_iou


@pytest.mark.parametrize("duration", [4, 12, 36])
def test_paired_truth_and_exact_unchanged_control(duration):
    spec = study.load_recipe()
    cells = {c: study.scene(spec, duration, c) for c in spec["conditions"]}
    assert cells["distinct"] == cells["unchanged_control"]
    for rows in cells.values():
        assert len(rows) == 32 + duration
        assert [r["frame"] for r in rows] == list(range(32 + duration))
        assert [r["truth"] for r in rows] == [r["truth"] for r in cells["distinct"]]
        for f, row in enumerate(rows):
            assert row["truth"] == [[100 + 2*f, 100, 120 + 2*f, 140],
                                    [108 + 2*f, 100, 128 + 2*f, 140]]
            if f < 12 or f >= 12 + duration:
                assert row == cells["distinct"][f]
    assert cells["missing_second"][12]["detections"] == [[124, 100, 144, 140]]
    assert cells["shared_union"][12]["detections"] == [[124, 100, 152, 140]]
    cells["distinct"][0]["detections"][0][0] = -1
    assert cells["distinct"][0]["truth"][0][0] == 100
    assert cells["unchanged_control"][0]["detections"][0][0] == 100


def test_support_patterns_by_independent_area_arithmetic():
    spec = study.load_recipe()
    expected = {"distinct": [[1, 3/7], [3/7, 1]],
                "missing_second": [[1], [3/7]], "shared_union": [[5/7], [5/7]]}
    for condition, overlaps in expected.items():
        row = study.scene(spec, 4, condition)[12]
        np.testing.assert_allclose(metric_iou(np.array(row["truth"]),
                                             np.array(row["detections"])), overlaps)


@pytest.mark.parametrize("duration,condition", [(True, "distinct"), (5, "distinct"),
                                                  (4, "tuned")])
def test_no_unregistered_grid(duration, condition):
    with pytest.raises(ValueError, match="unregistered"):
        study.scene(study.load_recipe(), duration, condition)


def hand_outputs(inputs, *, absent=(), change_after=None):
    return [dict(frame=row["frame"], observations=[
        dict(track_id=(30 if change_after is not None and i == 1 and
                       row["frame"] >= change_after else (10, 20)[i]),
             xyxy=box.copy(), score=0.9, class_id=0)
        for i, box in enumerate(row["truth"])
        if row["frame"] >= 2 and (row["frame"], i) not in absent]) for row in inputs]


def test_score_retains_startup_and_history_across_strata():
    spec = study.load_recipe()
    inputs = study.scene(spec, 4, "distinct")
    outputs = hand_outputs(inputs, absent={(f, 1) for f in range(12, 16)}, change_after=16)
    result = study.score(inputs, outputs, spec, 4)
    assert result["metrics"]["false_negatives"] == 8  # 4 startup + 4 imposed
    assert result["metrics"]["id_switches"] == result["metrics"]["fragmentations"] == 1
    assert result["strata"]["startup"]["miss"] == 4
    assert result["strata"]["episode"]["miss"] == 4
    assert result["strata"]["recovery"]["id_switch"] == 1
    assert result["strata"]["recovery"]["fragmentation"] == 1
    assert result["history"][12]["matches"] == {"1": 10, "2": None}
    assert result["recovery"]["2"] == dict(before_id=20, first_recovery_id=30,
        first_recovery_frame=16, delay_frames=0, same_id=False)
    assert result["recovery"]["1"]["same_id"] is True


def test_absent_recovery_null_is_not_zero_or_false():
    spec = study.load_recipe()
    inputs = study.scene(spec, 4, "distinct")
    outputs = hand_outputs(inputs, absent={(f, 1) for f in range(12, 36)})
    result = study.score(inputs, outputs, spec, 4)
    assert result["recovery"]["2"] == dict(before_id=20, first_recovery_id=None,
        first_recovery_frame=None, delay_frames=None, same_id=None)
    assert result["metrics"]["fragmentations"] == 0  # no resumed match


def test_recovery_latency_uses_episode_end_not_last_match():
    spec = study.load_recipe()
    inputs = study.scene(spec, 4, "distinct")
    result = study.score(inputs, hand_outputs(inputs, absent={(f, 1) for f in range(12, 19)}),
                         spec, 4)
    assert result["recovery"]["2"]["delay_frames"] == 3
    assert result["recovery"]["2"]["same_id"] is True


def test_incomplete_or_disordered_outputs_refused():
    spec = study.load_recipe()
    inputs = study.scene(spec, 4, "distinct")
    outputs = hand_outputs(inputs)
    with pytest.raises(ValueError, match="complete"):
        study.score(inputs, outputs[:-1], spec, 4)
    outputs[0]["frame"] = 99
    with pytest.raises(ValueError, match="ordered"):
        study.score(inputs, outputs, spec, 4)


class Double:
    def __init__(self, *args):
        self.reset()

    def reset(self):
        self.frame_index = -1

    def update(self, detections):
        self.frame_index += 1
        for detection in detections:
            assert {f.name for f in fields(detection)} == {"xyxy", "score", "class_id", "feature"}
            assert detection.feature is None  # no reference ID/feature/GT
        return [SimpleNamespace(track_id=i+1, xyxy=d.xyxy.copy(), score=d.score,
                                class_id=d.class_id, frame=self.frame_index)
                for i, d in enumerate(detections)]


def test_replay_uses_copies_and_refuses_warm_start():
    spec = study.load_recipe()
    inputs = study.scene(spec, 4, "shared_union")
    before = copy.deepcopy(inputs)
    tracker = Double()
    assert len(study.replay(tracker, inputs, spec)) == 36
    assert inputs == before
    with pytest.raises(ValueError, match="cold start"):
        study.replay(tracker, inputs, spec)


def test_nonfinite_outputs_fail():
    class Invalid(Double):
        def update(self, detections):
            result = super().update(detections)
            result[0].xyxy[0] = np.nan
            return result
    spec = study.load_recipe()
    with pytest.raises(ValueError, match="invalid public"):
        study.replay(Invalid(), study.scene(spec, 4, "distinct"), spec)


@pytest.mark.parametrize("field,value", [("track_id", True), ("track_id", 1.5),
                                        ("class_id", 0.5), ("frame", 99)])
def test_public_metadata_is_not_silently_coerced(field, value):
    class Invalid(Double):
        def update(self, detections):
            result = super().update(detections)
            setattr(result[0], field, value)
            return result
    spec = study.load_recipe()
    with pytest.raises(ValueError, match="metadata mismatch"):
        study.replay(Invalid(), study.scene(spec, 4, "distinct"), spec)


def doubles(monkeypatch):
    monkeypatch.setattr(study, "ByteTracker", Double)
    monkeypatch.setattr(study, "provenance", lambda spec: dict(explicit_test_double=True))


def test_complete_mocked_grid_has_all_inputs_passes_and_receipts(tmp_path, monkeypatch):
    doubles(monkeypatch)
    output = tmp_path / "study"
    study.execute(output)
    summary = json.loads((output / "summary.json").read_text())
    assert len(summary["cells"]) == 12 and summary["passes"] == 36
    assert summary["tracker_changed"] is summary["real_data_validation"] is False
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest) == 62  # method/summary + 12 * (input,3 outputs,score)
    for path, record in manifest.items():
        assert study.sha(output / path) == record["sha256"]
    for row in summary["cells"]:
        if row["condition"] in {"distinct", "unchanged_control"}:
            assert set(row["delta_from_distinct"].values()) == {0}


def test_reset_mismatch_retains_partial_passes_not_success(tmp_path, monkeypatch):
    doubles(monkeypatch)
    class BadReset(Double):
        def reset(self):
            self.frame_index = -1
            self.offset = getattr(self, "offset", 0) + 1

        def update(self, detections):
            result = super().update(detections)
            for row in result:
                row.track_id += self.offset
            return result
    monkeypatch.setattr(study, "ByteTracker", BadReset)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="fresh/reset"):
        study.execute(output)
    assert (output / "04-distinct/outputs-3.json").exists()
    assert (output / "failure.json").exists()
    assert not (output / "manifest.json").exists()


def test_recipe_and_provenance_drift_fail(tmp_path, monkeypatch):
    fake = tmp_path / "recipe.json"
    fake.write_text("{}")
    monkeypatch.setattr(study, "RECIPE", fake)
    with pytest.raises(ValueError, match="recipe drift"):
        study.load_recipe()


def test_source_must_be_committed(monkeypatch):
    monkeypatch.setattr(study, "_git", lambda *args: b"uncommitted")
    with pytest.raises(ValueError, match="commit study sources"):
        study.provenance(study.load_recipe())


@pytest.mark.parametrize("target", ["existing", "symlink", "repo", "cpp"])
def test_unsafe_output_refused_before_provenance(tmp_path, monkeypatch, target):
    monkeypatch.setattr(study, "provenance", lambda *a: pytest.fail("provenance read"))
    output = tmp_path
    if target == "symlink":
        output = tmp_path / "link"
        output.symlink_to(tmp_path / "absent")
    elif target == "repo":
        output = study.ROOT / "observation-unsafe-output"
    elif target == "cpp":
        output = study.ROOT.parent / "visiontrack-cpp/observation-unsafe-output"
    with pytest.raises(ValueError, match="new output|external"):
        study.execute(output)


def test_preview_never_constructs_tracker(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["observation-study"])
    monkeypatch.setattr(study, "ByteTracker", lambda *a: pytest.fail("tracker constructed"))
    study.main()
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == "visiontrack.observation-availability/v1"


def test_source_drift_after_all_mock_cells_is_not_certified(tmp_path, monkeypatch):
    doubles(monkeypatch)
    calls = []

    def drift(spec):
        calls.append(True)
        return dict(version=len(calls))

    monkeypatch.setattr(study, "provenance", drift)
    output = tmp_path / "drift"
    with pytest.raises(ValueError, match="drift"):
        study.execute(output)
    assert len(list(output.glob("*/scored.json"))) == 12
    assert (output / "failure.json").exists()
    assert not (output / "manifest.json").exists()


def test_unchanged_control_mismatch_retained_not_skipped(tmp_path, monkeypatch):
    doubles(monkeypatch)
    real_scene = study.scene

    def changed(spec, duration, condition):
        rows = real_scene(spec, duration, condition)
        if condition == "unchanged_control":
            rows[0]["detections"][0][0] += 1
        return rows

    monkeypatch.setattr(study, "scene", changed)
    output = tmp_path / "control"
    with pytest.raises(ValueError, match="unchanged control"):
        study.execute(output)
    assert (output / "04-unchanged_control/scored.json").exists()
    assert not (output / "manifest.json").exists()
