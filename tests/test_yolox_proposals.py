"""Capture must explain actual decoder decisions without changing them."""
import json
from dataclasses import FrozenInstanceError, asdict
from types import SimpleNamespace

import numpy as np
import pytest

from visiontrack import ByteTracker
from visiontrack.core.geometry import iou_matrix
from visiontrack.detection.yolox_onnx import YoloxDetector


class Session:
    def __init__(self, raw):
        self.raw = raw
        self.calls = 0

    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def run(self, _names, _feed):
        self.calls += 1
        return [self.raw]


def make(raw, **kwargs):
    return YoloxDetector("unused", input_size=32, session=Session(raw), **kwargs)


def raw_rows(rows, classes=2):
    """Authored decoded boxes; row: cx,cy,w,h,objectness,class_score,class_id."""
    out = np.zeros((len(rows), 5 + classes), dtype=np.float64)
    for i, (cx, cy, w, h, obj, score, cid) in enumerate(rows):
        out[i, :5] = cx, cy, w, h, obj
        out[i, 5 + cid] = score
    return out


def signature(dets):
    return [(d.xyxy.tobytes(), d.score, d.class_id, d.feature) for d in dets]


def observation_signature(obs):
    return [(o.frame, o.track_id, o.xyxy.tobytes(), o.score, o.class_id) for o in obs]


def test_full_capture_explains_confidence_cross_class_suppression_and_output_order():
    raw = raw_rows([
        (10, 10, 8, 8, .9, 1., 0),  # suppresses row 1 across class boundary
        (10, 10, 8, 8, .8, 1., 1),
        (25, 25, 4, 4, .7, 1., 1),
        (15, 25, 4, 4, .5, .5, 1),  # score exactly threshold: survives
        (20, 10, 4, 4, .5, .49, 1),
    ])
    det = make(raw, class_filter={1})
    ordinary = det.detect(np.zeros((16, 32, 3), dtype=np.uint8))
    actual, capture = det.detect_with_proposals(np.zeros((16, 32, 3), dtype=np.uint8))
    assert signature(actual) == signature(ordinary)
    assert len(actual) == 2
    assert [(r.proposal_index, r.status, r.group_winner_index, r.output_index)
            for r in capture.records] == [
        (0, "class_filtered", 0, None), (1, "nms_suppressed", 0, None),
        (2, "returned", 2, 0), (3, "returned", 3, 1),
        (4, "confidence_filtered", None, None),
    ]
    assert capture.records[0].group_size == capture.records[1].group_size == 2
    assert capture.records[0].group_complete is True
    assert capture.records[4].group_complete is None
    assert capture.records[3].score == .25
    assert capture.records[4].objectness == .5
    assert capture.records[4].class_score == .49
    assert capture.records[0].xyxy == (6., 6., 14., 14.)
    assert (capture.total_proposals, capture.confidence_filtered_count,
            capture.nms_suppressed_count, capture.nms_kept_count,
            capture.class_filtered_count, capture.returned_count) == (5, 1, 1, 3, 1, 2)
    assert not capture.truncated and capture.omitted_count == 0
    assert capture.scale == 1. and capture.class_filter == (1,)
    assert not capture.grid_decode_applied and not capture.transposed
    assert det._session.calls == 2  # each API invokes inference exactly once


@pytest.mark.parametrize("limit", [0, 1, 2, 3, 10])
def test_bounded_prefix_declares_missing_winner_and_incomplete_groups(limit):
    raw = raw_rows([(10, 10, 4, 4, .5, 1., 0),
                    (25, 25, 4, 4, .7, 1., 0),
                    (10, 10, 4, 4, .9, 1., 0)])
    det = make(raw)
    actual, c = det.detect_with_proposals(np.zeros((32, 32, 3)), max_proposals=limit)
    assert signature(actual) == signature(det.detect(np.zeros((32, 32, 3))))
    assert len(c.records) == min(limit, 3)
    assert c.omitted_count == max(0, 3 - limit)
    assert c.truncated == (limit < 3)
    assert c.returned_count == 2 and c.nms_suppressed_count == 1
    if limit:
        first = c.records[0]
        assert first.status == "nms_suppressed" and first.group_winner_index == 2
        assert first.group_size == 2
        assert first.captured_group_size == (2 if limit >= 3 else 1)
        assert first.group_complete == (limit >= 3)


@pytest.mark.parametrize("layout", ["rows", "batch_rows", "columns", "batch_columns"])
@pytest.mark.parametrize("classes", [1, 80])
def test_layout_scale_and_original_indices(layout, classes):
    # N > columns for the transposed-layout heuristic, avoiding ambiguous shapes.
    raw = raw_rows([(10, 10, 4, 8, .9, 1., 0)] +
                   [(20, 20, 2, 2, .01, 1., 0)] * 90, classes)
    if "columns" in layout:
        raw = raw.T
    if layout.startswith("batch"):
        raw = raw[None]
    original = raw.copy()
    det = make(raw)
    frame = np.zeros((64, 32, 4), dtype=np.uint8)  # .5 scale, bottom/right pad
    actual, c = det.detect_with_proposals(frame)
    assert signature(actual) == signature(det.detect(frame))
    assert len(actual) == 1
    assert tuple(actual[0].xyxy) == c.records[0].xyxy == (16., 12., 24., 28.)
    assert c.scale == .5 and c.raw_shape == raw.shape
    assert c.transposed == ("columns" in layout)
    assert [r.proposal_index for r in c.records] == list(range(91))
    assert all(r.status == "confidence_filtered" for r in c.records[1:])
    np.testing.assert_array_equal(raw, original)


def test_raw_grid_capture_including_rows_below_threshold():
    raw = np.zeros((1, 21, 6))  # input 32: 4*4 + 2*2 + 1*1
    raw[0, 5, 4:] = .9, 1.  # stride8, grid(1,1), 8x8 -> (4,4,12,12)
    det = make(raw)
    actual, c = det.detect_with_proposals(np.zeros((32, 32, 3)))
    assert signature(actual) == signature(det.detect(np.zeros((32, 32, 3))))
    assert c.grid_decode_applied
    assert c.records[5].xyxy == tuple(actual[0].xyxy) == (4., 4., 12., 12.)
    assert c.records[20].xyxy == (-16., -16., 16., 16.)
    assert c.records[20].status == "confidence_filtered"
    assert c.strides == (8, 16, 32)
    assert np.count_nonzero(raw) == 2


def test_small_coordinate_unmatched_grid_is_not_reported_as_grid_decoded():
    raw = raw_rows([(1, 1, 2, 2, .9, 1., 0)])
    actual, c = make(raw).detect_with_proposals(np.zeros((32, 32, 3)))
    assert not c.grid_decode_applied
    assert c.records[0].xyxy == tuple(actual[0].xyxy) == (0., 0., 2., 2.)


@pytest.mark.parametrize("raw", [np.empty((0, 7)), raw_rows([(10, 10, 4, 4, .01, 1., 0)])])
def test_no_eligible_proposals(raw):
    det = make(raw)
    actual, c = det.detect_with_proposals(np.zeros((32, 32, 3)))
    assert actual == det.detect(np.zeros((32, 32, 3))) == []
    assert c.nms_kept_count == c.nms_suppressed_count == c.returned_count == 0
    assert c.confidence_filtered_count == len(raw)
    assert all(r.status == "confidence_filtered" and r.group_size is None for r in c.records)


@pytest.mark.parametrize("below", [False, True])
def test_iou_equality_survives_and_strictly_lower_threshold_suppresses(below):
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0), (12, 10, 4, 4, .8, 1., 0)])
    overlap = float(iou_matrix(np.array([[8., 8., 12., 12.]]),
                               np.array([[10., 8., 14., 12.]]))[0, 0])
    threshold = np.nextafter(overlap, -np.inf) if below else overlap
    det = make(raw, iou_threshold=threshold)
    actual, c = det.detect_with_proposals(np.zeros((32, 32, 3)))
    assert signature(actual) == signature(det.detect(np.zeros((32, 32, 3))))
    assert len(actual) == (1 if below else 2)
    assert c.records[1].status == ("nms_suppressed" if below else "returned")
    assert c.iou_threshold == threshold


def test_score_tie_follows_existing_argsort_reversal():
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0), (10, 10, 4, 4, .9, 1., 1)])
    actual, c = make(raw).detect_with_proposals(np.zeros((32, 32, 3)))
    assert len(actual) == 1 and actual[0].class_id == 1
    assert [r.group_winner_index for r in c.records] == [1, 1]


@pytest.mark.parametrize("limit", [-1, 1.0, True, False, None, "2", np.int64(2)])
def test_invalid_limits_fail_before_inference(limit):
    det = make(raw_rows([]))
    with pytest.raises(ValueError, match="max_proposals"):
        det.detect_with_proposals(np.zeros((32, 32, 3)), max_proposals=limit)
    assert det._session.calls == 0


def test_immutable_capture_detached_from_model_and_no_default_recorder(monkeypatch):
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0)])
    det = make(raw)
    _, c = det.detect_with_proposals(np.zeros((32, 32, 3)))
    saved = asdict(c)
    with pytest.raises(FrozenInstanceError):
        c.records[0].score = .1
    raw[:] = 0
    assert asdict(c) == saved
    assert not any(value is c for value in vars(det).values())
    import visiontrack.detection.yolox_onnx as module

    def forbidden(*args):
        pytest.fail("ordinary detect must not allocate a proposal recorder")
    monkeypatch.setattr(module, "_ProposalRecorder", forbidden)
    assert det.detect(np.zeros((32, 32, 3))) == []
    assert asdict(c) == saved


@pytest.mark.parametrize("limit", [0, 2, 4096])
def test_multiframe_tracker_parity_with_occlusion_overlap_and_reset(limit):
    rng = np.random.default_rng(79)
    tensors = []
    for frame in range(45):
        rows = []
        for i in range(5):
            score = .1 if 10 <= frame < 16 and i == 1 else (.9 if i % 2 else .8)
            rows.append((10 + i * 3 + frame / 10, 10 + i, 8, 12, score, .95, i % 2))
        rows.extend((25, 25, 3, 3, float(rng.uniform(.01, .9)), .7, 0) for _ in range(3))
        tensors.append(raw_rows(rows))
    ordinary, instrumented = make(tensors[0]), make(tensors[0])
    left, right = ByteTracker(), ByteTracker()
    frame = np.zeros((32, 32, 3))
    replay = []
    for _ in range(2):
        outputs = []
        for raw in tensors:
            ordinary._session.raw = instrumented._session.raw = raw
            a = ordinary.detect(frame)
            b, _ = instrumented.detect_with_proposals(frame, max_proposals=limit)
            assert signature(a) == signature(b)
            out_a, out_b = left.update(a), right.update(b)
            assert observation_signature(out_a) == observation_signature(out_b)
            outputs.extend(observation_signature(out_a))
            for ta, tb in zip(left.tracks, right.tracks, strict=True):
                assert ta.mean.tobytes() == tb.mean.tobytes()
                assert ta.covariance.tobytes() == tb.covariance.tobytes()
        assert outputs
        replay.append(outputs)
        left.reset()
        right.reset()
    assert replay[0] == replay[1]


def test_prefix_winner_does_not_make_truncated_group_complete():
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0), (10, 10, 4, 4, .8, 1., 0)])
    _, c = make(raw).detect_with_proposals(np.zeros((32, 32, 3)), max_proposals=1)
    assert c.records[0].status == "returned"
    assert c.records[0].group_size == 2 and c.records[0].group_complete is False
    exported = json.loads(json.dumps(c.to_dict(), allow_nan=False))
    assert exported["truncated"] and exported["omitted_count"] == 1
    assert exported["records"][0]["group_complete"] is False
    assert exported["coordinates"] == "original_image_xyxy_unclipped"
    assert exported["nms_class_agnostic"] is True
    assert exported["class_filter_stage"] == "after_nms"
    assert exported["selection_policy"] == "original_row_prefix"
    exported["records"][0]["score"] = 0
    assert c.records[0].score == .9


def test_groups_are_direct_suppression_not_transitive_object_clusters():
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0), (12, 10, 4, 4, .8, 1., 0),
                    (14, 10, 4, 4, .7, 1., 0)])
    actual, c = make(raw, iou_threshold=.3).detect_with_proposals(np.zeros((32, 32, 3)))
    assert len(actual) == 2
    assert [r.group_winner_index for r in c.records] == [0, 0, 2]
    assert [r.group_size for r in c.records] == [2, 2, 1]
    assert all(r.group_complete for r in c.records)


def test_empty_class_filter_runs_suppression_then_returns_no_detections():
    raw = raw_rows([(10, 10, 4, 4, .9, 1., 0), (10, 10, 4, 4, .8, 1., 1)])
    det = make(raw, class_filter=set())
    actual, c = det.detect_with_proposals(np.zeros((32, 32, 3)))
    assert actual == det.detect(np.zeros((32, 32, 3))) == []
    assert c.class_filter == ()
    assert c.nms_suppressed_count == c.class_filtered_count == 1
    assert [r.status for r in c.records] == ["class_filtered", "nms_suppressed"]
