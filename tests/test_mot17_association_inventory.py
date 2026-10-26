"""Authored saved-record examples, not a visual review or tracker comparison."""
import copy
import json

import pytest

from experiments import mot17_association_inventory as inventory


def records():
    boxes = [[0, 0, 10, 10], [20, 0, 30, 10]]
    raw = dict(source_frame=36, gt_ids=[85, 89], gt_xyxy=copy.deepcopy(boxes),
               gt_classes=[1, 1], gt_consider=[1, 1],
               detections_xyxy=boxes, detection_scores=[1.0, 0.4])
    events = [dict(source_frame=36, kind="frame_start", detections=[
        dict(row=i + 1, xyxy=b, score=raw["detection_scores"][i])
        for i, b in enumerate(boxes)])]
    for stage in ("confirmed_high", "confirmed_low_recovery", "tentative_leftover_high"):
        events.append(dict(source_frame=36, kind="_match", stage=stage,
                           tracks=[dict(track_id=19)] if stage == "confirmed_high" else [],
                           detection_rows=[1] if stage == "confirmed_high" else [2],
                           matrices=dict(ious=[[0.8]], class_mismatch=[[False]],
                                         gating_d2=[[1.0]], cost=[[0.2]]),
                           forbidden=[[False]], max_cost=0.7, gate_threshold=9.4877))
    events.extend([
        dict(source_frame=36, kind="_apply_match", before=dict(track_id=19), detection_row=1),
        dict(source_frame=36, kind="frame_end", public_ids=[19])])
    return raw, events


@pytest.mark.parametrize("supports,expected", [
    (([], []), 0), (([1], []), 1), (([], [1]), 1), (([1], [1]), 1),
    (([1], [2]), 2), (([1, 2], [1]), 2), (([1], [1, 2]), 2)])
def test_two_reference_capacity_never_reuses_a_shared_box(supports, expected):
    assert inventory.capacity(supports) == expected


def test_all_raw_rows_retained_and_low_not_offered_is_not_forbidden():
    raw, events = records()
    before = copy.deepcopy((raw, events))
    result = inventory.frame_inventory(raw, events)
    assert (raw, events) == before
    assert result["selected_row"] == 1
    assert result["selected_support"] == [85]
    assert result["pools"]["eligible"]["two_reference_capacity"] == 2
    assert result["pools"]["high"]["two_reference_capacity"] == 1
    assert result["detections"][1]["offered_to_19"] == []
    assert result["detections"][1]["assigned_track_id"] is None
    assert result["detections"][0]["offered_to_19"][0]["forbidden"] is False


def test_shared_support_not_maximum_iou_identity_winner():
    raw, events = records()
    raw["gt_xyxy"] = [[0, 0, 5, 10], [0, 0, 10, 10]]
    result = inventory.frame_inventory(raw, events)
    assert result["selected_support"] == [85, 89]  # inclusive 0.5, not argmax
    assert result["pools"]["eligible"]["reference_rows"] == [[1], [1]]
    assert result["pools"]["eligible"]["two_reference_capacity"] == 1


def test_subthreshold_rows_are_visible_but_not_eligible():
    raw, events = records()
    raw["detection_scores"][1] = events[0]["detections"][1]["score"] = 0.099
    result = inventory.frame_inventory(raw, events)
    assert len(result["detections"]) == 2
    assert result["pools"]["raw"]["two_reference_capacity"] == 2
    assert result["pools"]["eligible"]["two_reference_capacity"] == 1


@pytest.mark.parametrize("change,message", [
    (lambda r, e: e[0].update(source_frame=37), "mixed source"),
    (lambda r, e: e[0]["detections"][0].update(row=0), "one-based"),
    (lambda r, e: r.update(detection_scores=[0.3, 0.4]), "differ"),
    (lambda r, e: r.update(gt_ids=[85, 85]), "unaligned"),
    (lambda r, e: r.update(gt_ids=[85, 90]), "reference missing"),
    (lambda r, e: r.update(gt_classes=[2, 1]), "pedestrian"),
    (lambda r, e: r["gt_xyxy"][0].__setitem__(2, 0), "positive-area"),
    (lambda r, e: e[1].update(stage="wrong"), "ordered stages"),
    (lambda r, e: e[-1].update(public_ids=[]), "public track"),
    (lambda r, e: e[1].update(forbidden=[[True]]), "feasibility"),
])
def test_inconsistent_evidence_fails(change, message):
    raw, events = records()
    change(raw, events)
    with pytest.raises(ValueError, match=message):
        inventory.frame_inventory(raw, events)


def test_preview_reads_no_packets(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["association-inventory"])
    monkeypatch.setattr(inventory, "read_bundle", lambda *a: pytest.fail("data read"))
    inventory.main()
    assert json.loads(capsys.readouterr().out) == inventory.method()


def test_existing_output_refused_before_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(inventory, "read_bundle", lambda *a: pytest.fail("data read"))
    with pytest.raises(ValueError, match="new output"):
        inventory.execute(tmp_path, tmp_path, tmp_path)


def mocked_packets(monkeypatch):
    raw, events = records()
    saved = [dict(raw, source_frame=f) for f in range(1, 1051)]
    traced = [dict(e, source_frame=f) for f in range(36, 58) for e in events]
    contents = {"run-1/raw.jsonl": "\n".join(json.dumps(r) for r in saved).encode()}
    packet = {"raw.jsonl": contents["run-1/raw.jsonl"],
              "events.jsonl": "\n".join(json.dumps(e) for e in traced).encode()}
    monkeypatch.setattr(inventory, "read_bundle", lambda *a: contents)
    monkeypatch.setattr(inventory, "read_packet", lambda *a: packet)
    return contents, packet


def test_complete_execution_receipts_are_explicitly_not_tracker_results(tmp_path, monkeypatch):
    contents, packet = mocked_packets(monkeypatch)
    before = copy.deepcopy((contents, packet))
    output = tmp_path / "result"
    inventory.execute(tmp_path, tmp_path, output)
    assert (contents, packet) == before
    summary = json.loads((output / "summary.json").read_text())
    assert summary["frames"] == 22
    assert summary["eligible_capacity_counts"] == {"2": 22}
    assert summary["selected_support_counts"] == {"85": 22}
    for key in ("tracker_executed", "physical_identity_established", "intervention_tested",
                "independent_review_completed"):
        assert summary[key] is False
    manifest = json.loads((output / "manifest.json").read_text())
    assert set(manifest) == {"method.json", "frames.json", "summary.json"}


def test_partial_failure_retains_method_but_not_success_manifest(tmp_path, monkeypatch):
    _, packet = mocked_packets(monkeypatch)
    packet["events.jsonl"] = b"\n".join(packet["events.jsonl"].splitlines()[1:])
    output = tmp_path / "failure"
    with pytest.raises(ValueError, match="frame boundaries"):
        inventory.execute(tmp_path, tmp_path, output)
    assert (output / "method.json").is_file()
    assert (output / "failure.json").is_file()
    assert not (output / "manifest.json").exists()


def test_changed_input_after_analysis_is_not_certified(tmp_path, monkeypatch):
    contents, _ = mocked_packets(monkeypatch)
    calls = []

    def changing(*args):
        calls.append(True)
        return contents if len(calls) == 1 else {"changed": b"data"}

    monkeypatch.setattr(inventory, "read_bundle", changing)
    output = tmp_path / "changed"
    with pytest.raises(ValueError, match="input or implementation changed"):
        inventory.execute(tmp_path, tmp_path, output)
    assert (output / "failure.json").is_file()
    assert not (output / "manifest.json").exists()
