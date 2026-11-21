"""SVMOT gate test: mask line rule, decision rule, ID switches and resumable detection."""
import json

import numpy as np
import pytest

import experiments.svmot_gate as s


def _seqs(rows, reference=40):
    """rows: per sequence {variant: (tp, fp, fn, idsw)}."""
    out = {}
    for i, row in enumerate(rows):
        out[f"seq_{i}"] = {
            "crossings": {"reference": reference,
                          **{v: dict(zip(("tp", "fp", "fn"), r[:3], strict=True))
                             for v, r in row.items()}},
            "id_switches": {v: r[3] for v, r in row.items()}}
    return out


def test_line_perpendicular_to_a_long_road():
    mask = np.zeros((100, 400), dtype=bool)
    mask[40:60, 20:380] = True  # a horizontal road strip
    info = s.line_from_mask(mask)
    (ax, ay), (bx, by) = info["line"]
    assert info["rule"] == "perpendicular"
    assert abs(ax - bx) < 1e-6 and abs(ax - 199.5) < 1e-6  # vertical, through the centroid
    assert sorted((ay, by)) == [40.0, 59.0]


def test_line_horizontal_when_mask_has_no_direction():
    mask = np.zeros((100, 100), dtype=bool)
    mask[20:80, 20:80] = True
    info = s.line_from_mask(mask)
    (ax, ay), (bx, by) = info["line"]
    assert info["rule"] == "horizontal" and ay == by == 49.5
    assert (ax, bx) == (20.0, 79.0)


def test_judge_supported_needs_id_switch_safeguard():
    good = [{"gate_on": (20, 1, 10, 10), "gate_off": (26, 1, 4, 11)}] * 2
    assert s.judge(_seqs(good), "gate_off") == "supported"
    swaps = [{"gate_on": (20, 1, 10, 10), "gate_off": (26, 1, 4, 12)}] * 2  # +20% swaps
    assert s.judge(_seqs(swaps), "gate_off") == "harmful"


def test_judge_no_harm_and_inconclusive():
    flat = [{"gate_on": (20, 1, 10, 10), "gate_off": (20, 2, 10, 10)}] * 2
    assert s.judge(_seqs(flat), "gate_off") == "no harm"
    assert s.judge(_seqs(flat, reference=10), "gate_off") == "inconclusive"


def test_id_switches_counts_one_swap():
    pytest.importorskip("trackeval", reason="trackeval not installed")
    box_a, box_b = [0.0, 0.0, 10.0, 10.0], [50.0, 0.0, 60.0, 10.0]
    reference = {(n, 1): box_a for n in range(1, 5)} | {(n, 2): box_b for n in range(1, 5)}
    clean = {(n, 7): box_a for n in range(1, 5)} | {(n, 8): box_b for n in range(1, 5)}
    assert s.id_switches(reference, clean, 4) == 0
    swapped = dict(clean)
    for n in (3, 4):  # the tracker swaps identities halfway
        swapped[(n, 7)], swapped[(n, 8)] = box_b, box_a
    assert s.id_switches(reference, swapped, 4) == 2


class _FakeDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, img):
        from types import SimpleNamespace
        self.calls += 1
        n = int(img)
        return [SimpleNamespace(xyxy=np.array([n, 0.0, n + 1, 1.0]), score=0.5, class_id=2)]


def test_detection_resumes_across_sequences(tmp_path, monkeypatch):
    seqs = ("seq_a", "seq_b")
    receipt = {"sequences": {q: {"sha256": {"img/0001.jpg": "x"}} for q in seqs}}
    (tmp_path / "download-receipt.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(s, "seq_info", lambda root, seq: (7, 1920, 1080))
    monkeypatch.setattr(s, "frames_from_folder", lambda root, seq, idx: ((n, n) for n in idx))
    cache = tmp_path / "cache"

    first = _FakeDetector()
    out = s.detect_all(tmp_path, None, cache, max_minutes=0, det=first, chunk=5, sequences=seqs)
    assert out["status"] == "partial" and first.calls == 0

    s.detect_all(tmp_path, None, cache, det=_FakeDetector(), chunk=5, sequences=seqs)
    (cache / "seq_b-parts" / "frames-000006-000007.npy").unlink()
    (cache / "seq_b-detections.json").unlink()

    resumed = _FakeDetector()
    out = s.detect_all(tmp_path, None, cache, det=resumed, chunk=5, sequences=seqs)
    assert resumed.calls == 2 and out["status"] == "complete"
    assert np.load(cache / "seq_b-detections.npy")[:, 0].tolist() == list(range(1, 8))
