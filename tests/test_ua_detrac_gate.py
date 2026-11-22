"""UA-DETRAC gate runner: parsers, set choice, ignored regions, matching and decision rule."""
import pytest

import experiments.ua_detrac_gate as u

XML = """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_1">
  <sequence_attribute camera_state="stable" sence_weather="sunny"/>
  <ignored_region>
    <box left="0" top="0" width="100" height="540"/>
  </ignored_region>
  <frame density="1" num="1"><target_list>
    <target id="7"><box left="400" top="250" width="40" height="10"/></target>
  </target_list></frame>
  <frame density="1" num="2"><target_list>
    <target id="7"><box left="400" top="270" width="40" height="10"/></target>
  </target_list></frame>
</sequence>
"""


def _dataset(tmp_path, scores=(0.9, 0.4)):
    (tmp_path / "annotations").mkdir()
    (tmp_path / "annotations" / "MVI_1.xml").write_text(XML)
    for det_set, score in zip(("R-CNN", "CompACT"), scores, strict=True):
        folder = tmp_path / "detections" / det_set
        folder.mkdir(parents=True)
        (folder / f"MVI_1_Det_{det_set}.txt").write_text(
            f"1,1,400,250,40,10,{score}\n2,1,400,270,40,10,{score}\n")
    return tmp_path


def test_parsers_read_boxes_ignored_regions_and_detections(tmp_path):
    root = _dataset(tmp_path)
    ann = u.load_annotation(root, "MVI_1")
    assert ann["boxes"][(2, 7)] == [400.0, 270.0, 440.0, 280.0]
    assert ann["ignored"] == [[0.0, 0.0, 100.0, 540.0]]
    dets = u.load_detections(root, "R-CNN", "MVI_1")
    assert dets.tolist()[0] == [1, 400, 250, 440, 260, 0.9, 0]
    assert u.frame_info(root, "MVI_1", ann, dets) == (2, 960, 540)


def test_first_set_in_order_with_scores_in_range_is_chosen(tmp_path):
    root = _dataset(tmp_path, scores=(1.7, 0.4))  # R-CNN breaks the 0-to-1 rule
    chosen = u.choose_set(root, ["MVI_1"])
    assert chosen["chosen"] == "CompACT"
    assert chosen["checked"]["R-CNN"]["passes"] is False


def test_reference_crossing_counted_and_ignored_region_drops_it(tmp_path):
    root = _dataset(tmp_path)
    ann = u.load_annotation(root, "MVI_1")
    line = u.line_at(0.5, 960, 540)
    assert line == ((0.0, 270.0), (960.0, 270.0))
    events = u.count(u.centres_of(ann["boxes"]), line, ann["ignored"])["cancel"]
    assert [(e["frame"], e["dir"]) for e in events] == [(2, "A->B")]
    assert u.count(u.centres_of(ann["boxes"]), line, [[0, 0, 960, 540]])["cancel"] == []


def test_match_limits_five_frames_and_38_pixels():
    ref = [{"frame": 10, "x": 100.0, "y": 270.0, "dir": "A->B"}]
    assert u.match(ref, [{"frame": 15, "x": 138.0, "y": 270.0, "dir": "A->B"}], 38)["tp"] == 1
    assert u.match(ref, [{"frame": 16, "x": 100.0, "y": 270.0, "dir": "A->B"}], 38)["tp"] == 0
    assert u.match(ref, [{"frame": 10, "x": 139.0, "y": 270.0, "dir": "A->B"}], 38)["tp"] == 0
    assert u.match(ref, [{"frame": 10, "x": 100.0, "y": 270.0, "dir": "B->A"}], 38)["tp"] == 0


def _seqs(rows):
    """rows: per sequence {variant: (tp, fp, fn, idsw)}."""
    out = {}
    for i, row in enumerate(rows):
        main = {v: dict(zip(("tp", "fp", "fn"), r[:3], strict=True)) for v, r in row.items()}
        out[f"s{i}"] = {"lines": {"main": {"cancel": main}},
                        "id_switches": {v: r[3] for v, r in row.items()}}
    return out


def test_sign_test_values():
    assert u.sign_test(5, 0) == pytest.approx(1 / 32)
    assert u.sign_test(4, 0) == pytest.approx(1 / 16)  # not below 5%
    assert u.sign_test(0, 0) == 1.0


def test_judge_needs_sign_test_and_id_switch_safeguard():
    better = {"gate_on": (8, 0, 2, 10), "gate_off": (10, 0, 0, 10)}
    same = {"gate_on": (8, 0, 2, 10), "gate_off": (8, 0, 2, 10)}
    assert u.judge(_seqs([better] * 5 + [same] * 3), "gate_off")["verdict"] == "supported"
    # only four sequences differ: p = 1/16, not significant
    assert u.judge(_seqs([better] * 4 + [same] * 4), "gate_off")["verdict"] == "not supported"
    swaps = {"gate_on": (8, 0, 2, 10), "gate_off": (10, 0, 0, 12)}  # +20% ID switches
    judged = u.judge(_seqs([swaps] * 5), "gate_off")
    assert judged["verdict"] == "not supported"
    assert judged["conditions"]["id_switches_within_limit"] is False


def test_run_sequence_replays_identically(tmp_path):
    pytest.importorskip("trackeval", reason="trackeval not installed")
    root = _dataset(tmp_path)
    result = u.run_sequence(root, "MVI_1", "R-CNN")
    assert result["lines"]["main"]["cancel"]["reference"] == 1
    assert set(result["output_sha256"]) == set(u.VARIANTS)
