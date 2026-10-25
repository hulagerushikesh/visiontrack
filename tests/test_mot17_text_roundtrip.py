"""Authored file-loader regressions; not scene labels or accuracy evidence."""
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from experiments import mot17_text_roundtrip as check
from experiments.mot17_metric_crosscheck import reference_api
from experiments.mot17_preprocessing_audit import local_row
from visiontrack.eval.hota import compute_hota, compute_identity
from visiontrack.eval.mot import MotAccumulator


def rows():
    result = []
    for frame in range(1, 5):
        result.append(dict(
            source_frame=frame, gt_ids=[78, 99, 105],
            gt_xyxy=[[10, 20, 30, 60], [100, 20, 120, 60], [200, 20, 220, 60]],
            gt_classes=[1, 7, 1], gt_consider=[1, 1, 0],
            track_ids=[901, 5, 808] if frame > 1 else [],
            track_xyxy=[[10.125, 20.25, 30.125, 60.25],
                        [100, 20, 120, 60], [200, 20, 220, 60]] if frame > 1 else []))
    return result


def load(tmp_path, raw):
    pytest.importorskip("trackeval")
    te, _, _ = reference_api()
    gt = tmp_path / "gt" / check.SEQUENCE / "gt/gt.txt"
    tr = tmp_path / "trackers/saved/data" / f"{check.SEQUENCE}.txt"
    gt.parent.mkdir(parents=True)
    tr.parent.mkdir(parents=True)
    lines = []
    for row in raw:
        for identity, box, cls, flag in zip(row["gt_ids"], check.xywh(row["gt_xyxy"]),
                                            row["gt_classes"], row["gt_consider"], strict=True):
            lines.append(",".join(map(str, [row["source_frame"], identity, *box, flag, cls, 1])))
    gt.write_text("\n".join(lines) + "\n")
    tr.write_bytes(check.tracker_text(raw))
    dataset = check.dataset(te, tmp_path, len(raw))
    return te, dataset, dataset.get_raw_seq_data("saved", check.SEQUENCE)


def test_actual_text_loader_preprocessing_and_all_metrics_without_tracker(tmp_path, monkeypatch):
    from visiontrack.tracking.tracker import ByteTracker

    def forbidden(*args, **kwargs):
        pytest.fail("saved-output check must not instantiate a tracker")
    monkeypatch.setattr(ByteTracker, "__init__", forbidden)
    raw = rows()
    before = copy.deepcopy(raw)
    te, dataset, loaded = load(tmp_path, raw)
    check.verify_loaded(raw, loaded)
    processed = dataset.get_preprocessed_seq_data(loaded, "pedestrian")
    scored = [local_row(row) for row in raw]
    check.verify_processed(scored, processed)
    # Class 7 removes its matched prediction; a zero-marked class-1 GT does not.
    assert scored[1]["track_ids"] == [901, 808]
    assert raw == before
    frames = [(np.asarray(r["gt_ids"], dtype=int), np.asarray(r["gt_xyxy"]).reshape(-1, 4),
               np.asarray(r["track_ids"], dtype=int), np.asarray(r["track_xyxy"]).reshape(-1, 4))
              for r in scored]
    accumulator = MotAccumulator()
    for frame in frames:
        accumulator.update(*frame)
    hota = asdict(compute_hota(frames))
    hota["per_alpha"] = hota["per_alpha"].tolist()
    saved = dict(clear=asdict(accumulator.result()), identity=asdict(compute_identity(frames)),
                 hota=hota)
    result = check.metric_checks(saved, processed, te)
    assert result["num_checks"] == 45 and result["all_checks_agree"] is True
    saved["clear"]["id_switches"] += 1
    result = check.metric_checks(saved, processed, te)
    assert result["all_checks_agree"] is False
    assert result["checks"]["clear"]["IDSW"]["tolerance"] == 0
    assert result["checks"]["clear"]["MOTA"]["tolerance"] == 1e-10


def test_export_17_digit_float_roundtrip_and_empty_frame_preservation(tmp_path):
    raw = rows()
    raw[1]["track_xyxy"][0] = [0.12345678901234566, 1.2345678901234567,
                                   17.87654321098765, 42.123456789012344]
    _, _, loaded = load(tmp_path, raw)
    check.verify_loaded(raw, loaded)
    text = check.tracker_text(raw).decode()
    assert not text.startswith("1,")
    assert len(loaded["tracker_ids"]) == 4 and len(loaded["tracker_ids"][0]) == 0
    assert all(len(line.split(",")) == 10 for line in text.splitlines())
    assert all(line.endswith(",1,-1,-1,-1") for line in text.splitlines())


@pytest.mark.parametrize("change", ["id", "geometry", "class", "flag", "confidence", "length"])
def test_loaded_tampering_is_rejected(tmp_path, change):
    raw = rows()
    _, _, loaded = load(tmp_path, raw)
    if change == "id":
        loaded["tracker_ids"][1][0] = 17
    elif change == "geometry":
        loaded["tracker_dets"][1][0, 0] += 0.01
    elif change == "class":
        loaded["gt_classes"][1][0] = 2
    elif change == "flag":
        loaded["gt_extras"][1]["zero_marked"][0] = 0
    elif change == "confidence":
        loaded["tracker_confidences"][1][0] = 0.9
    else:
        loaded["num_timesteps"] = 3
    with pytest.raises(ValueError):
        check.verify_loaded(raw, loaded)


@pytest.mark.parametrize("change", ["id", "geometry", "count", "length"])
def test_processed_correspondence_tampering_is_rejected(tmp_path, change):
    raw = rows()
    _, dataset, loaded = load(tmp_path, raw)
    processed = dataset.get_preprocessed_seq_data(loaded, "pedestrian")
    if change == "id":
        processed["tracker_ids"][1][0] += 1
    elif change == "geometry":
        processed["gt_dets"][1][0, 0] += 0.01
    elif change == "count":
        processed["num_tracker_dets"] += 1
    else:
        processed["num_timesteps"] = 3
    with pytest.raises(ValueError):
        check.verify_processed([local_row(row) for row in raw], processed)


@pytest.mark.parametrize("kind", ["order", "duplicate", "nan", "area"])
def test_invalid_saved_export_rejected(kind):
    raw = rows()
    if kind == "order":
        raw[0]["source_frame"] = 0
    elif kind == "duplicate":
        raw[1]["track_ids"][0] = 5
    elif kind == "nan":
        raw[1]["track_xyxy"][0][0] = np.nan
    else:
        raw[1]["track_xyxy"][0][2] = 9
    with pytest.raises(ValueError):
        check.tracker_text(raw)


def test_preview_has_no_input_or_output_access(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["check"])
    monkeypatch.setattr(check, "execute", lambda *a: pytest.fail("preview executed"))
    check.main()
    assert json.loads(capsys.readouterr().out)["tracker_executed"] is False


def test_write_requires_all_paths(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check", "--write"])
    with pytest.raises(ValueError, match="explicit inputs"):
        check.main()


def test_metric_disagreement_has_nonzero_exit(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check", "--write", "--baseline", "b", "--rescore", "r",
                                      "--cache", "c", "--labels", "l", "--output", "o"])
    monkeypatch.setattr(check, "execute", lambda *a: False)
    with pytest.raises(SystemExit) as error:
        check.main()
    assert error.value.code == 2


@pytest.mark.parametrize("where", ["existing", "repository"])
def test_output_refused_before_input_access(tmp_path, where):
    output = tmp_path if where == "existing" else Path(check.__file__).parent / "new-check"
    with pytest.raises(ValueError, match="new output|external"):
        check.execute(*(tmp_path / "missing" for _ in range(4)), output)


@pytest.mark.parametrize("which", ["baseline", "rescore"])
def test_cannot_add_files_inside_sealed_evidence(tmp_path, which):
    baseline, rescore = tmp_path / "baseline", tmp_path / "rescore"
    baseline.mkdir()
    rescore.mkdir()
    output = (baseline if which == "baseline" else rescore) / "new-check"
    with pytest.raises(ValueError, match="inside sealed"):
        check.execute(baseline, rescore, tmp_path / "missing", tmp_path / "missing", output)
    assert not output.exists()
