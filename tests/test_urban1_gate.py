"""Urban1 junction test runner, checked on made-up files only."""
import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image

from experiments import urban1_gate as u
from experiments.gram_rtm_gate import detect_sequence, match
from visiontrack.detection.base import Detection

# --- lines from the exclusion map --------------------------------------------------------


def test_elongated_area_gets_lines_across_and_along_its_axis():
    labelled = np.zeros((360, 600), dtype=bool)
    labelled[150:210, 50:550] = True  # long horizontal band
    info = u.two_lines(labelled)
    assert info["rule"] == "across and along the axis"
    (ax, ay), (bx, by) = info["lines"]["across"]
    assert abs(ax - bx) < 1 and abs(ay - by) > 50  # vertical, across the band
    (ax, ay), (bx, by) = info["lines"]["along"]
    assert abs(ay - by) < 1 and abs(ax - bx) > 400  # horizontal, along the band


def test_round_area_gets_horizontal_and_vertical_lines():
    labelled = np.zeros((360, 600), dtype=bool)
    labelled[80:280, 200:400] = True  # square
    info = u.two_lines(labelled)
    assert info["rule"] == "horizontal and vertical"
    (ax, ay), (bx, by) = info["lines"]["across"]
    assert ay == by and ax == 200 and bx == 399


def test_empty_map_is_refused():
    with pytest.raises(ValueError):
        u.two_lines(np.zeros((10, 10), dtype=bool))


# --- turning vehicles ------------------------------------------------------------------


def test_turning_straight_and_unclassified_tracks():
    centres = {}
    for f in range(40):  # right for 20 frames, then down for 20: a right-angle turn
        centres[(f + 1, 1)] = (10.0 + 5 * min(f, 20), 10.0 + 5 * max(0, f - 20))
        centres[(f + 1, 2)] = (10.0 + 5 * f, 200.0)  # straight
        centres[(f + 1, 3)] = (300.0 + 0.1 * f, 300.0)  # barely moves
    centres[(1, 4)] = (0.0, 0.0)  # too short
    kinds = u.classify_tracks(centres)
    assert kinds == {1: "turning", 2: "straight", 3: "unclassified", 4: "unclassified"}


# --- matching, blocks and the decision rule --------------------------------------------


def _event(frame, ident, x=100.0, y=100.0, d="A->B"):
    return {"frame": frame, "id": ident, "x": x, "y": y, "dir": d}


def test_score_agrees_with_the_shared_matcher_and_splits_blocks(monkeypatch):
    monkeypatch.setattr(u, "FRAMES", 100)
    ref = {"across": [_event(5, 1), _event(55, 2), _event(95, 3)], "along": [_event(30, 4)]}
    pred = {"across": [_event(6, 9), _event(70, 8)], "along": [_event(31, 7)]}
    out = u.score(ref, pred, {1: "straight", 2: "turning", 3: "turning"}, 23.4)
    shared = [match(ref[k], pred[k], 23.4) for k in ref]
    assert (out["tp"], out["fp"], out["fn"]) == tuple(sum(m[k] for m in shared)
                                                      for k in ("tp", "fp", "fn"))
    assert (out["tp"], out["fp"], out["fn"]) == (2, 1, 2)
    assert out["missed_by_kind"] == {"turning": 2, "straight": 0, "unclassified": 0}
    assert out["blocks"][2]["fn"] == 1 and out["blocks"][3]["fp"] == 1
    assert out["blocks"][4]["fn"] == 1


def _result(on, cand, turning=(0, 0), idsw=(100, 100), blocks=None, reference=60):
    def cross(t, kind_missed, block_rows):
        rows = block_rows or [dict(zip(("tp", "fp", "fn"), (t[0] / 5, t[1] / 5, t[2] / 5),
                                       strict=True)) for _ in range(5)]
        return {"tp": t[0], "fp": t[1], "fn": t[2], "blocks": rows,
                "missed_by_kind": {"turning": kind_missed, "straight": 0, "unclassified": 0}}
    return {"reference_crossings": reference,
            "crossings": {"gate_on": cross(on, turning[0], blocks and blocks[0]),
                          "gate_off": cross(cand, turning[1], blocks and blocks[1])},
            "id_switches": {"gate_on": idsw[0], "gate_off": idsw[1]}}


def test_supported_no_harm_and_harmful():
    assert u.judge(_result((50, 2, 10), (55, 3, 5)), "gate_off") == "supported"
    assert u.judge(_result((50, 2, 10), (50, 4, 10)), "gate_off") == "no harm"
    assert u.judge(_result((50, 2, 10), (45, 2, 15)), "gate_off") == "harmful"


def test_more_missed_turning_crossings_block_support_and_count_as_harm():
    assert u.judge(_result((50, 2, 10), (55, 2, 5), turning=(2, 5)), "gate_off") == "harmful"


def test_identity_swaps_rising_over_ten_percent_is_harmful():
    assert u.judge(_result((50, 2, 10), (55, 2, 5), idsw=(100, 111)), "gate_off") == "harmful"
    assert u.judge(_result((50, 2, 10), (55, 2, 5), idsw=(100, 110)), "gate_off") == "supported"


def test_one_block_worse_by_three_blocks_support():
    zero = {"tp": 10, "fp": 0, "fn": 2}
    on = [zero] * 5
    cand = [{"tp": 12, "fp": 0, "fn": 0}] * 4 + [{"tp": 7, "fp": 1, "fn": 4}]
    result = _result((50, 0, 10), (55, 1, 4), blocks=(on, cand))
    assert u.judge(result, "gate_off") == "no harm"


def test_fewer_than_thirty_reference_crossings_is_inconclusive():
    result = _result((20, 0, 9), (29, 0, 0), reference=29)
    assert u.judge(result, "gate_off") == "inconclusive"
    assert u.prefer(result, {"gate_off": "inconclusive", "aspect_free_gate": "no harm"}) is None


def test_offset_needs_a_clear_lead():
    assert u.choose_offset({"-1": 0.5, "0": 0.7, "1": 0.705, "2": 0.6}) == 1
    assert u.choose_offset({"-1": 0.5, "0": 0.8, "1": 0.7, "2": 0.6}) == 0


# --- made-up dataset on disk -----------------------------------------------------------

W, H, N = 160, 100, 60


def _jpeg(size=(W, H)):
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 90, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def _vehicles(k):
    """Label frame k: vehicle 1 moves right along y=20; vehicle 2 moves down along x=30."""
    return [(1, [2.0 * k, 15.0, 2.0 * k + 10, 25.0]), (2, [25.0, 1.5 * k, 35.0, 1.5 * k + 8])]


def _root(tmp_path, first_number=0, gap=False):
    kit = tmp_path / "extracted" / "GRAM-RTMv4"
    xml = kit / "Annotations" / "Urban1" / "xml"
    xml.mkdir(parents=True)
    for k in range(N):
        objs = "".join(f"<object><class>car</class><ID>{i}</ID><bndbox><xmin>{b[0]}</xmin>"
                       f"<ymin>{b[1]}</ymin><xmax>{b[2]}</xmax><ymax>{b[3]}</ymax></bndbox>"
                       "</object>" for i, b in _vehicles(k))
        (xml / f"{k}.xml").write_text(f"<annotation>{objs}</annotation>")
    (kit / "ROI").mkdir()
    Image.new("L", (W, H), 255).save(kit / "ROI" / "Urban1-map.jpg")
    (tmp_path / "images").mkdir()
    with zipfile.ZipFile(tmp_path / "images" / "Urban1.zip", "w") as archive:
        for i in range(N):
            number = first_number + i + (1 if gap and i > 5 else 0)
            archive.writestr(f"Urban1/image{number:06d}.jpg", _jpeg())
    return tmp_path


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(u, "FRAMES", N)
    monkeypatch.setattr(u, "WIDTH", W)
    monkeypatch.setattr(u, "HEIGHT", H)


def test_frames_are_addressed_by_position_and_gaps_are_refused(tmp_path, small):
    root = _root(tmp_path, first_number=0)
    with zipfile.ZipFile(root / "images" / "Urban1.zip") as archive:
        members = u.image_members(archive)
    assert members[0].endswith("image000000.jpg") and len(members) == N
    gapped = _root(tmp_path / "gap", gap=True)
    with zipfile.ZipFile(gapped / "images" / "Urban1.zip") as archive, \
            pytest.raises(ValueError):
        u.image_members(archive)


def test_format_check_passes_and_catches_a_wrong_size(tmp_path, small, monkeypatch):
    root = _root(tmp_path)
    assert u.format_check(root)["passed"] is True
    monkeypatch.setattr(u, "WIDTH", W + 1)
    assert u.format_check(root)["passed"] is False


class _LabelDetector:
    """Returns the label boxes of the matching frame, as a perfect detector would."""

    def detect(self, image):  # noqa: ARG002 - frame content is ignored
        self.k += 1
        return [Detection(np.array(b), 0.9, 2) for _, b in _vehicles(self.k - 1)]

    k = 0


def test_detection_resumes_and_full_run_counts_every_crossing(tmp_path, small):
    pytest.importorskip("trackeval", reason="trackeval not installed")
    root = _root(tmp_path)
    cache = root / "gate-cache"
    det = _LabelDetector()
    first = detect_sequence(root, root / "unused.onnx", "Urban1", cache, max_minutes=0.0,
                            det=det, chunk=10, count=N, frames=u.frames_from_zip)
    assert first["status"] == "partial" and first["parts_done"] == 0
    done = detect_sequence(root, root / "unused.onnx", "Urban1", cache, det=det, chunk=10,
                           count=N, frames=u.frames_from_zip)
    assert done["status"] == "complete" and done["detections"] == 2 * N

    out = u.run(root, cache, offset=1)
    result = out["result"]
    assert result["reference_crossings"] == 2  # one on each line
    assert result["reference_by_kind"]["straight"] == 2
    for variant in ("gate_on", "gate_off", "aspect_free_gate"):
        c = result["crossings"][variant]
        assert (c["tp"], c["fp"], c["fn"]) == (2, 0, 0)
        assert result["id_switches"][variant] == 0
    assert out["verdicts"] == {"aspect_free_gate": "inconclusive", "gate_off": "inconclusive"}
    assert out["preferred"] is None
    json.dumps(out)  # the record is plain JSON


def test_turning_step_reads_labels_only(tmp_path, small):
    root = _root(tmp_path)
    assert u.turning_step(root) == {"vehicles": 2, "turning": 0, "straight": 2,
                                    "unclassified": 0}
