"""Reference policy checks are not a tracker quality or visual label test."""
import copy
import sys

import numpy as np
import pytest

from experiments import mot17_preprocessing_audit as audit
from experiments.mot17_metric_crosscheck import reference_api

BOX = [0., 0., 10., 10.]


def row(classes=(1,), flags=None, boxes=None, predictions=None, ids=None, frame=1):
    boxes = boxes if boxes is not None else [BOX] * len(classes)
    predictions = predictions if predictions is not None else [BOX]
    return dict(source_frame=frame, gt_ids=list(range(1, len(classes) + 1)),
                gt_xyxy=boxes, gt_classes=list(classes),
                gt_consider=list(flags) if flags is not None else [1] * len(classes),
                track_ids=ids if ids is not None else list(range(1, len(predictions) + 1)),
                track_xyxy=predictions)


def reference(rows):
    pytest.importorskip("trackeval")
    te, iou, _ = reference_api()
    return audit.reference_rows(rows, te, iou)


@pytest.mark.parametrize("cls,removed", [(1, False), (2, True), (3, False), (4, False),
                                       (5, False), (6, False), (7, True), (8, True),
                                       (9, False), (10, False), (11, False), (12, True)])
def test_reference_removes_only_mot17_distractor_classes(cls, removed):
    original = row([cls])
    result = reference([original])[0]
    assert audit.local_row(original) == result
    assert result["track_ids"] == ([] if removed else [1])
    assert result["gt_ids"] == ([1] if cls == 1 else [])
    if cls not in (1, 2, 7, 8, 12):
        assert audit.local_row(original, policy=audit.LEGACY_MOT17_PREPROCESSING)[
            "track_ids"] == []


def test_zero_marked_pedestrian_does_not_remove_prediction_in_reference():
    original = row([1], flags=[0])
    result = reference([original])[0]
    assert result["gt_ids"] == [] and result["track_ids"] == [1]
    assert audit.local_row(original) == result
    assert audit.local_row(original, policy=audit.LEGACY_MOT17_PREPROCESSING)["track_ids"] == []


def test_dense_reference_ids_recover_original_lineage_even_for_identical_boxes():
    rows = [row(predictions=[BOX, BOX], ids=[901, 5]),
            row(predictions=[BOX], ids=[901], frame=2)]
    rows[0]["gt_ids"] = [78]
    rows[1]["gt_ids"] = [78]
    saved = copy.deepcopy(rows)
    result = reference(rows)
    assert [r["track_ids"] for r in result] == [[901, 5], [901]]
    assert [r["gt_ids"] for r in result] == [[78], [78]]
    assert rows == saved


@pytest.mark.parametrize("original", [row([], predictions=[]), row([], predictions=[BOX]),
                                      row([1], predictions=[])])
def test_empty_sides_are_retained(original):
    assert reference([original])[0] == audit.local_row(original)


def test_comparison_preserves_all_disagreements_and_inputs():
    raw = [row([3]), row([1], frame=2)]
    saved = [audit.local_row(r, policy=audit.LEGACY_MOT17_PREPROCESSING) for r in raw]
    ref = reference(raw)
    snapshot = copy.deepcopy((raw, saved, ref))
    result = audit.compare(raw, saved, ref, policy=audit.LEGACY_MOT17_PREPROCESSING)
    assert result["all_frames_agree"] is False
    assert result["disagreement_frames"] == 1
    assert result["prediction_counts"] == dict(raw=2, saved=1, reference=2)
    assert result["frame_changes"][0]["reference_only_ids"] == [1]
    assert (raw, saved, ref) == snapshot


def test_mismatched_saved_preprocessing_is_not_accepted():
    raw = [row()]
    saved = [audit.local_row(raw[0])]
    saved[0]["track_ids"] = [99]
    with pytest.raises(ValueError, match="not reproduced"):
        audit.compare(raw, saved, reference(raw))


@pytest.mark.parametrize("kind", ["duplicate", "nonfinite", "flags", "alignment", "order",
                                 "fractional_id", "boolean_id"])
def test_invalid_adapter_input_fails(kind):
    original = row()
    if kind == "duplicate":
        original.update(track_ids=[1, 1], track_xyxy=[BOX, BOX])
    elif kind == "nonfinite":
        original["gt_xyxy"] = [[np.nan, 0, 10, 10]]
    elif kind == "flags":
        original["gt_consider"] = [0.5]
    elif kind == "alignment":
        original["track_ids"] = []
    elif kind == "order":
        original["source_frame"] = 2
    else:
        original["track_ids"] = [1.5 if kind == "fractional_id" else True]
    with pytest.raises(ValueError):
        reference([original])


def test_cli_disagreement_is_nonzero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["audit", "--baseline", "b", "--cache", "c",
                                      "--labels", "l", "--output", "o"])
    monkeypatch.setattr(audit, "execute", lambda *args: False)
    with pytest.raises(SystemExit) as error:
        audit.main()
    assert error.value.code == 2


def test_existing_output_refused_before_reading(tmp_path):
    with pytest.raises(ValueError, match="new output"):
        audit.execute(tmp_path / "b", tmp_path / "c", tmp_path / "l", tmp_path)
