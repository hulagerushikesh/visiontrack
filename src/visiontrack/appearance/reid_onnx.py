"""Optional deep re-ID embedder backed by ONNX Runtime.

Drop-in replacement for :class:`ColorHistogramEmbedder` when a pretrained
re-ID model (OSNet, FastReID, …) is available as ``.onnx``. Same interface, so
nothing else changes. ``onnxruntime`` is imported lazily, so the package never
requires it. This is intentionally optional: the from-scratch colour-histogram
embedder keeps the whole appearance study runnable with no download.
"""
from __future__ import annotations

import numpy as np

__all__ = ["OnnxReID"]


class OnnxReID:
    """Runs a re-ID CNN over detection crops and returns L2-normalized features.

    Parameters
    ----------
    model_path:
        Path to a re-ID ``.onnx`` model with input ``(1, 3, H, W)`` and output
        ``(1, F)``.
    input_size:
        ``(height, width)`` the model expects (e.g. ``(256, 128)`` for OSNet).
    """

    def __init__(
        self,
        model_path: str,
        input_size: tuple[int, int] = (256, 128),
        providers: list[str] | None = None,
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("OnnxReID requires onnxruntime: pip install onnxruntime") from exc

        self._session = ort.InferenceSession(
            model_path, providers=providers or ["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name
        self.input_h, self.input_w = input_size
        out_shape = self._session.get_outputs()[0].shape
        self.dim = int(out_shape[-1]) if isinstance(out_shape[-1], int) else -1

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        try:
            import cv2

            resized = cv2.resize(crop, (self.input_w, self.input_h))
        except ImportError:  # pragma: no cover - nearest-neighbour fallback
            ys = np.linspace(0, crop.shape[0] - 1, self.input_h).astype(int)
            xs = np.linspace(0, crop.shape[1] - 1, self.input_w).astype(int)
            resized = crop[ys][:, xs]
        chw = resized[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        return chw

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        image = np.asarray(image)
        boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
        H, W = image.shape[:2]
        feats = []
        for x1, y1, x2, y2 in boxes:
            xa, xb = int(np.clip(x1, 0, W - 1)), int(np.clip(x2, 1, W))
            ya, yb = int(np.clip(y1, 0, H - 1)), int(np.clip(y2, 1, H))
            if xb <= xa or yb <= ya:
                feats.append(np.zeros(max(self.dim, 1)))
                continue
            blob = self._preprocess(image[ya:yb, xa:xb, :3])[None]
            out = self._session.run(None, {self._input_name: blob})[0].ravel()
            norm = np.linalg.norm(out)
            feats.append(out / norm if norm > 0 else out)
        return np.stack(feats) if feats else np.zeros((0, max(self.dim, 1)))
