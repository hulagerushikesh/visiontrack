"""Exercise the frozen replay shape with doubles; never run the study tracker here."""
import json
from pathlib import Path

import pytest

from experiments import continuity_warning_study as study
from experiments.continuity_warning_audit import audit_frame, audit_saved
from experiments.continuity_warning_scene import load_recipe, scene
from visiontrack.tracking.tracker import TrackObservation


class PublicDouble:
    def __init__(self, *args):
        self.reset()

    def reset(self):
        self.frame_index = -1

    def update(self, detections):
        self.frame_index += 1
        assert all(det.feature is None for det in detections)
        return [TrackObservation(frame=self.frame_index, track_id=i + 1,
                                 xyxy=det.xyxy.copy(), score=det.score,
                                 class_id=det.class_id)
                for i, det in enumerate(detections)]


def test_replay_receives_only_detector_payload_and_never_mutates_truth():
    spec = load_recipe()
    inputs = scene(spec, 3, "shared_union")
    original = study.encoded(inputs)
    monitored, warnings = study.replay(PublicDouble(), inputs, monitored=True)
    unmonitored, none = study.replay(PublicDouble(), inputs, monitored=False)
    assert study.encoded(inputs) == original
    assert study.encoded(monitored) == study.encoded(unmonitored)
    assert len(warnings) == 96 and none == []
    assert len(warnings[0]["edges"]) == 0
    assert warnings[0]["assessment_opportunity"] is False
    assert not hasattr(PublicDouble, "truth")


def test_scoring_keeps_event_history_and_null_switch_fraction():
    spec = load_recipe()
    inputs = scene(spec, 3, "crossing_distinct")
    outputs, warnings = study.replay(PublicDouble(), inputs, monitored=True)
    result = study.score(inputs, outputs, warnings, spec, 3)
    assert len(result["matches"]) == 96
    assert result["metrics"]["num_frames"] == 96
    assert result["strata"]["episode"]["frame_range"] == [36, 39]
    assert result["strata"]["recovery"]["frame_range"] == [39, 96]
    assert result["opportunity_frames"] == 93
    assert result["first_episode_warning"] is None
    assert result["switch_warning_fraction"] is None


def test_decision_uses_fixed_integer_gate_and_does_not_hide_nuisance_rows():
    spec = load_recipe()
    rows = []
    for duration in (3, 9, 33):
        for family in [item["name"] for item in spec["families"]]:
            target = family in {"shared_union", "coincident_two"}
            rows.append(dict(family=family, duration=duration,
                             episode_warning_frames=[36] if target else [],
                             first_episode_warning_delay=0 if target else None,
                             warning_frames=[36] if target else [],
                             opportunity_frames=84))
    assert study.decision(rows, spec)["passed"] is True
    rows[0]["opportunity_frames"] = 83
    failed = study.decision(rows, spec)
    assert failed["passed"] is False
    assert failed["issues"] == ["benign opportunity below 90%: crossing_distinct/3"]
    rows[0]["opportunity_frames"] = 84
    rows[4]["first_episode_warning_delay"] = 3
    assert "target warning missing/late: shared_union/3" in study.decision(rows, spec)["issues"]


def test_full_mocked_grid_saves_every_cell_and_monitor_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "ByteTracker", PublicDouble)
    monkeypatch.setattr(study, "provenance", lambda spec: dict(double=True))
    output = tmp_path / "study"
    study.execute(output)
    summary = json.loads((output / "summary.json").read_text())
    assert len(summary["cells"]) == 27
    assert summary["tracker_passes"] == 108
    assert isinstance(summary["screen"]["passed"], bool)
    assert summary["independent_validation"] is False
    assert not (output / "failure.json").exists()
    for cell in summary["cells"]:
        folder = output / f'{cell["duration"]:02d}-{cell["family"]}'
        assert len(json.loads((folder / "inputs.json").read_text())) == 96
        assert len(json.loads((folder / "warnings-1.json").read_text())) == 96
        for index in range(1, 5):
            assert len(json.loads((folder / f"outputs-{index}.json").read_text())) == 96
        assert not (folder / "warnings-4.json").exists()
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest) == 2 + 27 * 9  # method, summary; 1 input+4 output+3 warning+score
    assert all(study.sha(output / relative) == record["sha256"]
               for relative, record in manifest.items())
    assert audit_saved(output)["frames_checked"] == 27 * 96


def test_independent_auditor_catches_false_component_capacity():
    spec = load_recipe()
    inputs = scene(spec, 3, "coincident_two")
    outputs, warnings = study.replay(PublicDouble(), inputs, monitored=True)
    frame = 36
    previous = sorted(outputs[frame - 1]["observations"], key=lambda row: row["track_id"])
    audit_frame(frame, previous, inputs[frame]["detections"], warnings[frame])
    warnings[frame]["components"][0]["maximum_matching_cardinality"] = 2
    with pytest.raises(ValueError, match="independent component capacity"):
        audit_frame(frame, previous, inputs[frame]["detections"], warnings[frame])


def test_output_refuses_existing_and_repo_internal_without_writing(tmp_path):
    present = tmp_path / "present"
    present.mkdir()
    with pytest.raises(ValueError, match="new non-symlink"):
        study.execute(present)
    symlink = tmp_path / "link"
    symlink.symlink_to(present)
    with pytest.raises(ValueError, match="new non-symlink"):
        study.execute(symlink)
    inside = Path(study.ROOT) / "study-should-not-exist"
    assert not inside.exists()
    with pytest.raises(ValueError, match="outside repos"):
        study.execute(inside)
    assert not inside.exists()


def test_partial_failure_has_failure_receipt_but_no_success_manifest(tmp_path, monkeypatch):
    class Broken(PublicDouble):
        def update(self, detections):
            if self.frame_index == 2:
                raise RuntimeError("intentional double failure")
            return super().update(detections)
    monkeypatch.setattr(study, "ByteTracker", Broken)
    monkeypatch.setattr(study, "provenance", lambda spec: dict(double=True))
    output = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="intentional"):
        study.execute(output)
    assert (output / "method.json").exists()
    assert (output / "failure.json").exists()
    assert not (output / "manifest.json").exists()
