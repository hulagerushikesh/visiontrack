"""SportsMOT support, exercised on a tiny hand-written MOT sequence (no download).

SportsMOT reuses the generic MOT-format loader and the shared cache pipeline, so
these tests pin the wiring that makes ``--dataset sportsmot`` work end to end:
the loader aliases, the cache-reader discovery, and the benchmark dispatch.
"""
import numpy as np

from experiments._caches import discover_cache_readers
from experiments.benchmark import _cached_df, run_benchmark
from visiontrack.datasets.cache import save_sequence_cache
from visiontrack.detection.dancetrack_loader import (
    DanceTrackSequence,
    MotSequence,
    discover_dancetrack,
    discover_mot_sequences,
)
from visiontrack.detection.noise import NoiseConfig


def _make_seq(tmp_path, name="v_gameplay_0001", n_frames=6, n_obj=4, w=1280, h=720):
    d = tmp_path / name
    (d / "gt").mkdir(parents=True)
    (d / "img1").mkdir()
    (d / "seqinfo.ini").write_text(
        "[Sequence]\n"
        f"name={name}\nimDir=img1\nframeRate=25\n"
        f"seqLength={n_frames}\nimWidth={w}\nimHeight={h}\nimExt=.jpg\n"
    )
    lines = []
    for f in range(1, n_frames + 1):
        for oid in range(1, n_obj + 1):
            x, y = 60 * oid + 3 * f, 40 * oid + 2 * f  # simple motion
            lines.append(f"{f},{oid},{x},{y},38,84,1,1,1")
    (d / "gt" / "gt.txt").write_text("\n".join(lines) + "\n")
    return d


def test_generic_aliases_point_at_the_mot_loader():
    # SportsMOT support is the generic MOT loader under a clearer name — same code.
    assert MotSequence is DanceTrackSequence
    assert discover_mot_sequences is discover_dancetrack


def test_precompute_and_discover_roundtrip(tmp_path):
    seq_dir = _make_seq(tmp_path / "val")
    # discovery finds the sequence dir (as precompute would)
    assert seq_dir in discover_mot_sequences(tmp_path / "val")

    # precompute → one cache in a dedicated dir
    cache = tmp_path / "cache" / "sportsmot"
    cache.mkdir(parents=True)
    seq = MotSequence(seq_dir, noise_cfg=NoiseConfig(drop_prob=0.0, fp_rate=0.0), seed=0)
    save_sequence_cache(seq, cache / f"{seq.name}.npz")

    # the shared reader discovers it with the sportsmot glob ("*.npz", own dir)
    readers = discover_cache_readers(cache, glob="*.npz")
    assert len(readers) == 1
    assert readers[0].name == "v_gameplay_0001"
    assert len(readers[0]) == 6


def test_cached_df_scores_the_sportsmot_cache(tmp_path):
    seq_dir = _make_seq(tmp_path / "val")
    cache = tmp_path / "cache"
    cache.mkdir()
    seq = MotSequence(seq_dir, noise_cfg=NoiseConfig(drop_prob=0.0, fp_rate=0.0), seed=0)
    save_sequence_cache(seq, cache / f"{seq.name}.npz")

    df, seq_names = _cached_df(["bytetrack"], str(cache), "onnx", "*.npz")
    assert seq_names == ["v_gameplay_0001"]
    assert set(df["variant"]) == {"bytetrack"}
    # a real number came out of the from-scratch evaluator
    assert np.isfinite(df["MOTA"].iloc[0])


def test_run_benchmark_dispatches_sportsmot(tmp_path):
    _make_seq(tmp_path / "val", name="v_a_0001")
    cache = tmp_path / "cache"
    cache.mkdir()
    seq = MotSequence(tmp_path / "val" / "v_a_0001",
                      noise_cfg=NoiseConfig(drop_prob=0.0, fp_rate=0.0), seed=0)
    save_sequence_cache(seq, cache / f"{seq.name}.npz")

    rep = run_benchmark("sportsmot", tracker_names=["bytetrack"],
                        cache_dir=str(cache))
    assert rep.dataset == "sportsmot"
    assert rep.meta["config_hash"] == "sportsmot"
    assert "v_a_0001" in rep.meta["sequences"]
