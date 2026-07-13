"""MOT17 loader, cache round-trip, and CachedDetections adapter tests.

Uses a tiny inline MOT17-format fixture written to a temp dir, so these run in
CI with no dataset download.
"""
import numpy as np
import pytest

from visiontrack.datasets.cache import CachedSequence, save_sequence_cache
from visiontrack.datasets.splits import load_split, video_base_id
from visiontrack.detection.cached import CachedDetections
from visiontrack.detection.mot_loader import MOT17Sequence

SEQINFO = """[Sequence]
name=MOT17-99-FRCNN
imDir=img1
frameRate=30
seqLength=3
imWidth=1920
imHeight=1080
imExt=.jpg
"""

# frame,-1,left,top,w,h,conf,-1,-1,-1   (scores span a non-[0,1] range on purpose)
DET = """1,-1,100,100,50,80,0.9,-1,-1,-1
1,-1,300,200,40,90,0.2,-1,-1,-1
2,-1,105,102,50,80,0.95,-1,-1,-1
3,-1,110,104,50,80,0.7,-1,-1,-1
"""

# frame,id,left,top,w,h,flag,class,visibility
GT = """1,1,100,100,50,80,1,1,1.0
1,2,300,200,40,90,1,1,0.9
2,1,105,102,50,80,1,1,1.0
2,2,305,202,40,90,1,1,0.8
3,1,110,104,50,80,1,1,1.0
3,7,500,500,30,60,1,7,1.0
"""


@pytest.fixture
def seq_dir(tmp_path):
    d = tmp_path / "MOT17-99-FRCNN"
    (d / "det").mkdir(parents=True)
    (d / "gt").mkdir(parents=True)
    (d / "seqinfo.ini").write_text(SEQINFO)
    (d / "det" / "det.txt").write_text(DET)
    (d / "gt" / "gt.txt").write_text(GT)
    return d


def test_seqinfo_parsed(seq_dir):
    seq = MOT17Sequence(seq_dir)
    assert seq.name == "MOT17-99-FRCNN"
    assert seq.info.frame_rate == 30
    assert seq.info.length == 3
    assert seq.info.width == 1920 and seq.info.height == 1080


def test_frames_1_indexed_and_boxes_xyxy(seq_dir):
    seq = MOT17Sequence(seq_dir)
    f1 = seq.frame(1)
    assert f1.frame == 1
    # xywh (100,100,50,80) -> xyxy (100,100,150,180)
    np.testing.assert_allclose(f1.det_xyxy[0], [100, 100, 150, 180])
    assert f1.gt_xyxy.shape[0] == 2
    assert set(f1.gt_ids.tolist()) == {1, 2}


def test_in_range_scores_pass_through(seq_dir):
    # The fixture's scores are already in [0, 1] (FRCNN/SDP-like), so they must
    # be preserved exactly rather than min-max stretched.
    seq = MOT17Sequence(seq_dir, normalize_scores=True)
    f1 = seq.frame(1)
    np.testing.assert_allclose(sorted(f1.det_scores.tolist()), [0.2, 0.9])


def test_out_of_range_scores_are_minmax_normalized(seq_dir):
    # Rewrite det.txt with DPM-like unbounded scores; these SHOULD be rescaled.
    dpm = "1,-1,100,100,50,80,-30.0,-1,-1,-1\n1,-1,300,200,40,90,20.0,-1,-1,-1\n"
    (seq_dir / "det" / "det.txt").write_text(dpm)
    seq = MOT17Sequence(seq_dir, normalize_scores=True)
    scores = seq.frame(1).det_scores
    assert scores.min() == pytest.approx(0.0)
    assert scores.max() == pytest.approx(1.0)


def test_distractor_class_and_flag_preserved(seq_dir):
    seq = MOT17Sequence(seq_dir)
    f3 = seq.frame(3)
    # Frame 3 has a pedestrian (class 1) and a static-person distractor (class 7).
    assert set(f3.gt_classes.tolist()) == {1, 7}


def test_streaming_does_not_load_all_frames(seq_dir):
    seq = MOT17Sequence(seq_dir)
    frames = list(seq.iter_range(2, 3))
    assert [f.frame for f in frames] == [2, 3]


def test_cache_roundtrip_matches_source(seq_dir, tmp_path):
    seq = MOT17Sequence(seq_dir)
    out = save_sequence_cache(seq, tmp_path / "cache" / "MOT17-99-FRCNN.npz")
    cached = CachedSequence(out)

    assert len(cached) == len(seq)
    assert cached.name == seq.name
    for idx in range(1, len(seq) + 1):
        a, b = seq.frame(idx), cached.frame(idx)
        np.testing.assert_allclose(a.det_xyxy, b.det_xyxy, rtol=1e-5)
        np.testing.assert_allclose(a.det_scores, b.det_scores, rtol=1e-5, atol=1e-6)
        np.testing.assert_array_equal(a.gt_ids, b.gt_ids)
        np.testing.assert_array_equal(a.gt_classes, b.gt_classes)


def test_cached_detections_adapter_is_a_detector(seq_dir, tmp_path):
    seq = MOT17Sequence(seq_dir)
    out = save_sequence_cache(seq, tmp_path / "MOT17-99-FRCNN.npz")
    cached = CachedSequence(out)
    adapter = CachedDetections(cached)

    # detect() ignores the image and walks frames in order.
    dets1 = adapter.detect(None)
    assert len(dets1) == 2  # frame 1 has two detections
    dets2 = adapter.detect(None)
    # In-range scores pass through unchanged (frame 2's single det is 0.95).
    assert dets2[0].score == pytest.approx(0.95)
    assert len(adapter) == 3


def test_cached_sequence_attaches_aligned_embeddings(seq_dir, tmp_path):
    seq = MOT17Sequence(seq_dir)
    det_npz = save_sequence_cache(seq, tmp_path / "MOT17-99-FRCNN.npz")

    # Build an embedding cache aligned row-for-row with the detection cache.
    with np.load(det_npz) as z:
        det_frame = z["det_frame"]
        n = det_frame.shape[0]
    emb = np.arange(n * 3, dtype=np.float32).reshape(n, 3)  # distinct per row
    emb_npz = tmp_path / "MOT17-99-FRCNN.colorhist.emb.npz"
    np.savez_compressed(emb_npz, emb=emb, emb_frame=det_frame, embedder="test", dim=3)

    cached = CachedSequence(det_npz, emb_path=emb_npz)
    # Frame 1 has two detections -> two features, aligned to the first two rows.
    dets = cached.frame(1).detections()
    assert all(d.feature is not None for d in dets)
    assert dets[0].feature.shape == (3,)
    np.testing.assert_allclose(dets[0].feature, emb[0])


def test_misaligned_embedding_cache_raises(seq_dir, tmp_path):
    seq = MOT17Sequence(seq_dir)
    det_npz = save_sequence_cache(seq, tmp_path / "seq.npz")
    bad = tmp_path / "seq.bad.emb.npz"
    np.savez_compressed(bad, emb=np.zeros((999, 3), dtype=np.float32))
    with pytest.raises(ValueError):
        CachedSequence(det_npz, emb_path=bad)


def test_frozen_split_ranges_and_base_id():
    split = load_split("mot17_val_half")
    assert video_base_id("MOT17-02-SDP") == "MOT17-02"
    first, last = split.range_for("MOT17-02-FRCNN", "val")
    assert (first, last) == (301, 600)
    tfirst, tlast = split.range_for("MOT17-02-FRCNN", "train")
    assert (tfirst, tlast) == (1, 300)
    # train and val partition the sequence with no overlap.
    assert tlast + 1 == first
