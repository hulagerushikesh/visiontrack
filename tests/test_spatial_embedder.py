"""Tests for the vertical-stripe (spatial) appearance embedder."""
import numpy as np
import pytest

from visiontrack.appearance.embedder import SpatialColorHistogramEmbedder, make_embedder


def test_dim_and_normalization():
    emb = SpatialColorHistogramEmbedder(stripes=3, h_bins=8, s_bins=4, v_bins=4)
    assert emb.dim == 3 * 16
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, size=(120, 60, 3), dtype=np.uint8)
    feats = emb.embed(img, np.array([[5, 5, 55, 115]]))
    assert feats.shape == (1, 48)
    assert np.linalg.norm(feats[0]) == pytest.approx(1.0, abs=1e-6)


def test_captures_vertical_layout_a_global_hist_would_miss():
    """Top-red/bottom-blue vs top-blue/bottom-red have identical GLOBAL colour
    histograms but must differ under the spatial (stripe) embedder."""
    h = 90
    top_red = np.zeros((h, 40, 3), dtype=np.uint8)
    top_red[: h // 2, :, 0] = 200      # red top
    top_red[h // 2 :, :, 2] = 200      # blue bottom

    top_blue = np.zeros((h, 40, 3), dtype=np.uint8)
    top_blue[: h // 2, :, 2] = 200     # blue top
    top_blue[h // 2 :, :, 0] = 200     # red bottom

    box = np.array([[0, 0, 40, h]])
    from visiontrack.appearance.embedder import ColorHistogramEmbedder

    g = ColorHistogramEmbedder()
    s = SpatialColorHistogramEmbedder()
    g_sim = float(g.embed(top_red, box)[0] @ g.embed(top_blue, box)[0])
    s_sim = float(s.embed(top_red, box)[0] @ s.embed(top_blue, box)[0])

    # Global histograms are (nearly) identical — the layout is invisible to it.
    assert g_sim > 0.99
    # The stripe embedder separates them: markedly lower similarity.
    assert s_sim < g_sim - 0.15


def test_make_embedder_factory():
    assert make_embedder("spatial").dim == 48
    assert make_embedder("colorhist").dim == 32
    with pytest.raises(ValueError):
        make_embedder("nope")
