"""Appearance embedders — turn a detection crop into a descriptor vector.

The default :class:`ColorHistogramEmbedder` is **from scratch** (NumPy +
matplotlib's vectorized RGB→HSV): it needs no model download, no GPU, and runs
in microseconds per crop, which suits this project's constraints and ethos. An
HSV colour histogram is a deliberately *weak* appearance cue — which is exactly
what makes the RQ1 study interesting: does even a cheap appearance signal help
association on MOT17, and where does it start to hurt?

For a stronger descriptor, :class:`~visiontrack.appearance.reid_onnx.OnnxReID`
(optional, lazy) drops in a pretrained deep re-ID model behind the same
interface — the tracker and cache are embedder-agnostic.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

__all__ = ["Embedder", "ColorHistogramEmbedder", "IdentityEmbedder"]


class Embedder(Protocol):
    """Maps an image + boxes to one L2-normalized descriptor per box."""

    dim: int

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """Return an ``(N, dim)`` array of features for ``N`` ``xyxy`` boxes."""
        ...


class ColorHistogramEmbedder:
    """HSV colour-histogram appearance descriptor (from scratch).

    Each crop becomes a concatenation of per-channel Hue/Saturation/Value
    histograms, each normalized to sum 1, then the whole vector L2-normalized.
    Illumination is partly factored out by using HSV rather than RGB.
    """

    def __init__(self, h_bins: int = 16, s_bins: int = 8, v_bins: int = 8) -> None:
        self.h_bins = h_bins
        self.s_bins = s_bins
        self.v_bins = v_bins
        self.dim = h_bins + s_bins + v_bins

    def _hist(self, channel: np.ndarray, bins: int) -> np.ndarray:
        h, _ = np.histogram(channel, bins=bins, range=(0.0, 1.0))
        total = h.sum()
        return h / total if total > 0 else h.astype(np.float64)

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        from matplotlib.colors import rgb_to_hsv

        image = np.asarray(image)
        boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
        H, W = image.shape[:2]
        feats = np.zeros((boxes.shape[0], self.dim), dtype=np.float64)

        for i, (x1, y1, x2, y2) in enumerate(boxes):
            xa, xb = int(np.clip(x1, 0, W - 1)), int(np.clip(x2, 1, W))
            ya, yb = int(np.clip(y1, 0, H - 1)), int(np.clip(y2, 1, H))
            if xb <= xa or yb <= ya:
                continue
            crop = image[ya:yb, xa:xb, :3].astype(np.float64) / 255.0
            hsv = rgb_to_hsv(crop)
            hist = np.concatenate(
                [
                    self._hist(hsv[..., 0], self.h_bins),
                    self._hist(hsv[..., 1], self.s_bins),
                    self._hist(hsv[..., 2], self.v_bins),
                ]
            )
            norm = np.linalg.norm(hist)
            feats[i] = hist / norm if norm > 0 else hist
        return feats


class SpatialColorHistogramEmbedder:
    """Vertical-stripe HSV colour histogram (from scratch).

    A global histogram ignores *where* colour sits in the box, so a
    dark-top/light-bottom person and a light-top/dark-bottom person look
    identical. Splitting the crop into horizontal stripes (roughly head /
    torso / legs for a pedestrian) and histogramming each keeps that coarse
    spatial layout — the classic cheap re-ID descriptor, and a stronger
    appearance cue than the global one, still with no model download.
    """

    def __init__(
        self, stripes: int = 3, h_bins: int = 8, s_bins: int = 4, v_bins: int = 4
    ) -> None:
        self.stripes = stripes
        self.h_bins = h_bins
        self.s_bins = s_bins
        self.v_bins = v_bins
        self.dim = stripes * (h_bins + s_bins + v_bins)

    def _hist(self, channel: np.ndarray, bins: int) -> np.ndarray:
        h, _ = np.histogram(channel, bins=bins, range=(0.0, 1.0))
        total = h.sum()
        return h / total if total > 0 else h.astype(np.float64)

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        from matplotlib.colors import rgb_to_hsv

        image = np.asarray(image)
        boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
        H, W = image.shape[:2]
        feats = np.zeros((boxes.shape[0], self.dim), dtype=np.float64)

        for i, (x1, y1, x2, y2) in enumerate(boxes):
            xa, xb = int(np.clip(x1, 0, W - 1)), int(np.clip(x2, 1, W))
            ya, yb = int(np.clip(y1, 0, H - 1)), int(np.clip(y2, 1, H))
            if xb <= xa or yb <= ya:
                continue
            crop = image[ya:yb, xa:xb, :3].astype(np.float64) / 255.0
            hsv = rgb_to_hsv(crop)
            edges = np.linspace(0, hsv.shape[0], self.stripes + 1).astype(int)
            parts = []
            for s in range(self.stripes):
                band = hsv[edges[s] : max(edges[s] + 1, edges[s + 1])]
                parts.append(self._hist(band[..., 0], self.h_bins))
                parts.append(self._hist(band[..., 1], self.s_bins))
                parts.append(self._hist(band[..., 2], self.v_bins))
            hist = np.concatenate(parts)
            norm = np.linalg.norm(hist)
            feats[i] = hist / norm if norm > 0 else hist
        return feats


def make_embedder(name: str, model_path: str | None = None):
    """Factory: build an embedder by name.

    ``'colorhist'`` / ``'spatial'`` are the from-scratch, no-download descriptors.
    ``'onnx'`` builds the deep re-ID :class:`~visiontrack.appearance.reid_onnx.OnnxReID`
    from ``model_path`` (requires ``onnxruntime``; imported lazily here so the
    other embedders never pull the optional dependency).
    """
    if name == "colorhist":
        return ColorHistogramEmbedder()
    if name == "spatial":
        return SpatialColorHistogramEmbedder()
    if name == "onnx":
        if not model_path:
            raise ValueError("embedder 'onnx' requires model_path=<path to .onnx>")
        from visiontrack.appearance.reid_onnx import OnnxReID

        return OnnxReID(model_path)
    raise ValueError(f"unknown embedder: {name!r}")


class IdentityEmbedder:
    """Deterministic test embedder: features come from caller-supplied vectors.

    Not for real use — it maps each box to a fixed vector via a provided lookup
    (indexed by row), so tests can inject controlled appearance signals without
    any image. Missing rows get a zero vector.
    """

    def __init__(self, vectors: np.ndarray) -> None:
        self.vectors = np.asarray(vectors, dtype=np.float64).reshape(len(vectors), -1)
        self.dim = self.vectors.shape[1]

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        n = len(boxes)
        out = np.zeros((n, self.dim), dtype=np.float64)
        out[: min(n, len(self.vectors))] = self.vectors[: min(n, len(self.vectors))]
        return out
