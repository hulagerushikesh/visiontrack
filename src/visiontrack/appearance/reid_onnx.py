"""Optional deep re-ID embedder backed by ONNX Runtime.

Drop-in replacement for :class:`ColorHistogramEmbedder` when a pretrained
re-ID model (OSNet, FastReID, …) is available as ``.onnx``. Same interface, so
nothing else changes. ``onnxruntime`` is imported lazily, so the package never
requires it. This is intentionally optional: the from-scratch colour-histogram
embedder keeps the whole appearance study runnable with no download.

Preprocessing matches the ``torchreid`` convention the OSNet/MSMT17 weights were
trained with: RGB, resize to ``(256, 128)``, scale to ``[0, 1]``, then ImageNet
mean/std normalization. Many exported re-ID ONNX graphs also pin a **fixed batch
size** (the MSMT17 OSNet-x0.25 export is batch-16), so :meth:`embed` chunks crops
into fixed-size batches, zero-pads the final partial batch, and slices the
padding back off — it never assumes a dynamic batch axis.
"""
from __future__ import annotations

import numpy as np

__all__ = ["OnnxReID"]

# torchreid / OSNet training normalization (ImageNet statistics, RGB order).
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class OnnxReID:
    """Runs a re-ID CNN over detection crops and returns L2-normalized features.

    Parameters
    ----------
    model_path:
        Path to a re-ID ``.onnx`` model with input ``(B, 3, H, W)`` and output
        ``(B, F)``. ``B`` may be a fixed integer (common for exported re-ID
        graphs) or a dynamic axis; both are handled.
    input_size:
        ``(height, width)`` the model expects. Ignored if the graph pins static
        spatial dims (those win). Defaults to ``(256, 128)`` for OSNet.
    mean, std:
        Per-channel RGB normalization applied after scaling to ``[0, 1]``.
        Defaults to ImageNet statistics (the torchreid convention).
    bgr:
        Set ``True`` only if the model was trained on BGR input (e.g. some
        OpenCV/Caffe exports). Default ``False`` (RGB), matching torchreid.
    """

    def __init__(
        self,
        model_path: str,
        input_size: tuple[int, int] = (256, 128),
        providers: list[str] | None = None,
        mean: np.ndarray | None = None,
        std: np.ndarray | None = None,
        bgr: bool = False,
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("OnnxReID requires onnxruntime: pip install onnxruntime") from exc

        self._session = ort.InferenceSession(
            model_path, providers=providers or ["CPUExecutionProvider"]
        )
        inp = self._session.get_inputs()[0]
        self._input_name = inp.name
        # Static dims in the graph override the caller's request.
        b, _c, h, w = inp.shape
        self.batch = b if isinstance(b, int) and b > 0 else None
        self.input_h = h if isinstance(h, int) and h > 0 else input_size[0]
        self.input_w = w if isinstance(w, int) and w > 0 else input_size[1]
        out_shape = self._session.get_outputs()[0].shape
        self.dim = int(out_shape[-1]) if isinstance(out_shape[-1], int) else -1
        self.mean = _IMAGENET_MEAN if mean is None else np.asarray(mean, dtype=np.float32)
        self.std = _IMAGENET_STD if std is None else np.asarray(std, dtype=np.float32)
        self.bgr = bgr

    def _resize(self, crop: np.ndarray) -> np.ndarray:
        """Resize an RGB crop to ``(input_h, input_w)``, best-quality available.

        cv2 (bilinear) if present, else Pillow (bilinear — in the ``[appearance]``
        extra), else a NumPy nearest-neighbour fallback so the class stays usable
        with zero optional deps.
        """
        try:
            import cv2

            return cv2.resize(crop, (self.input_w, self.input_h))
        except ImportError:
            pass
        try:
            from PIL import Image

            im = Image.fromarray(crop).resize((self.input_w, self.input_h), Image.BILINEAR)
            return np.asarray(im)
        except ImportError:  # nearest-neighbour fallback (no cv2 / PIL)
            ys = np.linspace(0, crop.shape[0] - 1, self.input_h).astype(int)
            xs = np.linspace(0, crop.shape[1] - 1, self.input_w).astype(int)
            return crop[ys][:, xs]

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """RGB crop (H, W, 3) -> normalized CHW float32 the network expects."""
        resized = self._resize(np.ascontiguousarray(crop))
        rgb = resized[:, :, ::-1] if self.bgr else resized
        norm = (rgb.astype(np.float32) / 255.0 - self.mean) / self.std
        return norm.transpose(2, 0, 1)  # HWC -> CHW

    def _run_batch(self, blobs: np.ndarray) -> np.ndarray:
        """Forward ``blobs`` (n, 3, H, W), padding to a fixed batch if required."""
        n = blobs.shape[0]
        if self.batch is not None and n != self.batch:
            if n > self.batch:  # shouldn't happen — caller chunks — but be safe
                parts = [
                    self._run_batch(blobs[i : i + self.batch]) for i in range(0, n, self.batch)
                ]
                return np.concatenate(parts, axis=0)
            pad = np.zeros((self.batch - n, *blobs.shape[1:]), dtype=blobs.dtype)
            blobs = np.concatenate([blobs, pad], axis=0)
        out = self._session.run(None, {self._input_name: blobs.astype(np.float32)})[0]
        return out[:n]

    def embed(self, image: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        image = np.asarray(image)
        boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
        H, W = image.shape[:2]

        # Preprocess valid crops; remember which rows had a usable box.
        blobs: list[np.ndarray] = []
        valid_rows: list[int] = []
        for r, (x1, y1, x2, y2) in enumerate(boxes):
            xa, xb = int(np.clip(x1, 0, W - 1)), int(np.clip(x2, 1, W))
            ya, yb = int(np.clip(y1, 0, H - 1)), int(np.clip(y2, 1, H))
            if xb <= xa or yb <= ya:
                continue
            blobs.append(self._preprocess(image[ya:yb, xa:xb, :3]))
            valid_rows.append(r)

        dim = max(self.dim, 1)
        feats = np.zeros((boxes.shape[0], dim), dtype=np.float64)
        if not blobs:
            return feats

        stacked = np.stack(blobs)  # (n_valid, 3, H, W)
        step = self.batch or stacked.shape[0]
        outs = [self._run_batch(stacked[i : i + step]) for i in range(0, stacked.shape[0], step)]
        raw = np.concatenate(outs, axis=0)
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        raw = np.divide(raw, norms, out=np.zeros_like(raw), where=norms > 0)
        feats[np.asarray(valid_rows)] = raw
        return feats
