"""Authored geometric examples, not independent scene/identity annotations."""
import copy
import json
from pathlib import Path

import pytest

from experiments import mot17_prior_context as prior


def saved(rows=None):
    base = dict(track_ids=[19], track_xyxy=[[0, 0, 10, 10]],
                gt_ids=[85, 89], gt_xyxy=[[0, 0, 10, 10], [20, 0, 30, 10]],
                gt_classes=[1, 1], gt_consider=[1, 1], gt_visibility=[1, 0.5])
    values = [dict(copy.deepcopy(base), source_frame=f) for f in range(1, 1051)]
    for index, change in (rows or {}).items():
        values[index].update(change)
    return {"run-1/raw.jsonl": "\n".join(json.dumps(r) for r in values).encode()}


def test_fixed_prefix_and_original_coordinates_without_mutation():
    contents = saved()
    before = copy.deepcopy(contents)
    rows, summary = prior.analyze(contents)
    assert contents == before
    assert [r["source_frame"] for r in rows] == list(range(1, 36))
    assert rows[0]["track_box"] == [0, 0, 10, 10]
    assert rows[0]["references"][0]["track_iou"] == 1
    assert rows[0]["references"][1]["track_iou"] == 0
    assert summary["state_counts"] == {"85": 35}
    assert summary["runs"] == [dict(first_frame=1, last_frame=35, state="85",
                                   present_reference_ids=[85, 89])]
    assert summary["first_public_19"] == 1
    for key in ("physical_identity_established", "independent_review_completed",
                "new_image_acquisition", "intervention_justified"):
        assert summary[key] is False


def test_both_supports_retained_no_maximum_iou_winner_and_inclusive_boundary():
    rows, _ = prior.analyze(saved({0: {"gt_xyxy": [[0, 0, 5, 10], [0, 0, 10, 10]]}}))
    assert rows[0]["references"][0]["track_iou"] == 0.5
    assert rows[0]["supported_reference_ids"] == [85, 89]
    assert rows[0]["state"] == "85+89"
    assert rows[0]["reference_pair_iou"] == 0.5


def test_missing_is_null_not_zero_and_presence_breaks_runs():
    rows, summary = prior.analyze(saved({
        0: {"track_ids": [], "track_xyxy": []},
        2: {"gt_ids": [85], "gt_xyxy": [[0, 0, 10, 10]], "gt_classes": [1],
            "gt_consider": [1], "gt_visibility": [1]}}))
    assert rows[0]["references"][0]["track_iou"] is None
    assert rows[0]["track_box"] is None
    assert rows[2]["references"][1] == dict(id=89, present=False, box=None,
                                            visibility=None, track_iou=None)
    assert rows[2]["reference_pair_iou"] is None
    assert summary["first_public_19"] == 2
    assert len(summary["runs"]) == 4


def test_no_overlap_is_not_missing_and_no_public_has_no_first_frame():
    rows, _ = prior.analyze(saved({0: {"track_xyxy": [[100, 100, 110, 110]]}}))
    assert rows[0]["state"] == "no_supported_reference"
    assert [r["track_iou"] for r in rows[0]["references"]] == [0, 0]
    absent = {i: dict(track_ids=[], track_xyxy=[]) for i in range(35)}
    _, summary = prior.analyze(saved(absent))
    assert summary["first_public_19"] is None


@pytest.mark.parametrize("change,message", [
    ({"track_ids": [19, 19], "track_xyxy": [[0, 0, 1, 1]] * 2}, "unique public"),
    ({"gt_ids": [85, 85]}, "unique references"),
    ({"gt_visibility": [1]}, "unique references"),
    ({"gt_classes": [2, 1]}, "scored pedestrian"),
    ({"gt_visibility": [2, 1]}, "visibility"),
    ({"track_xyxy": [[0, 0, 0, 1]]}, "positive-area"),
])
def test_malformed_or_unscored_input_refused(change, message):
    with pytest.raises(ValueError, match=message):
        prior.analyze(saved({0: change}))


def test_incomplete_or_unordered_sequence_refused():
    with pytest.raises(ValueError, match="ordered saved sequence"):
        prior.analyze(saved({3: {"source_frame": 3}}))
    contents = saved()
    contents["run-1/raw.jsonl"] = b"\n".join(contents["run-1/raw.jsonl"].splitlines()[:-1])
    with pytest.raises(ValueError, match="ordered saved sequence"):
        prior.analyze(contents)


def test_preview_does_not_read_data(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["prior-context"])
    monkeypatch.setattr(prior, "read_bundle", lambda *a: pytest.fail("preview read files"))
    prior.main()
    assert json.loads(capsys.readouterr().out) == prior.method()


def test_new_external_output_required_before_reading(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        prior.execute(tmp_path, tmp_path)
    with pytest.raises(ValueError, match="external output"):
        prior.execute(tmp_path, Path(__file__).parent / "private-context")


def test_receipt_and_failure_without_success_manifest(monkeypatch, tmp_path):
    contents = saved()
    monkeypatch.setattr(prior, "read_bundle", lambda *a: contents)
    output = tmp_path / "good"
    prior.execute(tmp_path, output)
    assert set(json.loads((output / "manifest.json").read_text())) == {
        "method.json", "frames.json", "summary.json"}
    assert json.loads((output / "summary.json").read_text())["frames"] == 35
    bad = tmp_path / "bad"
    monkeypatch.setattr(prior, "analyze", lambda *a: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError, match="bad"):
        prior.execute(tmp_path, bad)
    assert (bad / "method.json").is_file() and (bad / "failure.json").is_file()
    assert not (bad / "manifest.json").exists()
