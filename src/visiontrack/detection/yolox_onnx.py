"""YOLOX detector via ONNX Runtime — the detector for H2 "run on real video".

YOLOX is the detector the ByteTrack / OC-SORT papers use, so it keeps this
project's tracking lineage consistent. Its ONNX output differs from the YOLOv8
family handled by :mod:`~visiontrack.detection.onnx_yolo`:

* output is ``(1, N, 5 + nc)`` = ``[cx, cy, w, h, objectness, class scores…]``
  in **network-pixel** space (exported with decode baked in), and
* preprocessing letterboxes to a padded square with **no** ``/255`` or mean/std
  normalisation (YOLOX consumes raw pixel values).

Score is ``objectness × max class score``. ``onnxruntime`` is imported lazily; the
decode is a pure-NumPy method so it is unit-testable with a fake session (no model
or onnxruntime needed in CI) — the same pattern as :class:`OnnxReID`.
"""
from __future__ import annotations

import numpy as np

from ..core.geometry import iou_matrix
from .base import Detection

__all__ = ["YoloxDetector"]


class YoloxDetector:
    def __init__(
        self,
        model_path: str,
        input_size: int = 416,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        class_filter: set[int] | None = None,
        session=None,
    ) -> None:
        """``session`` may be injected (a fake) for testing; otherwise an
        onnxruntime session is created from ``model_path``."""
        if session is not None:
            self._session = session
        else:  # pragma: no cover - needs onnxruntime + a real model
            try:
                import onnxruntime as ort
            except ImportError as exc:
                raise ImportError(
                    "YoloxDetector requires onnxruntime: pip install onnxruntime"
                ) from exc
            self._session = ort.InferenceSession(
                model_path, providers=["CPUExecutionProvider"]
            )
        self._input_name = self._session.get_inputs()[0].name
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.class_filter = class_filter

    # -- preprocessing ----------------------------------------------------
    def _letterbox(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        """Resize keeping aspect ratio, pad to a square with 114 (YOLOX style)."""
        h, w = frame.shape[:2]
        scale = min(self.input_size / h, self.input_size / w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        ys = np.linspace(0, h - 1, nh).astype(int)
        xs = np.linspace(0, w - 1, nw).astype(int)
        resized = frame[ys][:, xs]
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[:nh, :nw] = resized  # YOLOX pads bottom-right (origin top-left)
        return canvas, scale

    # -- inference + decode ----------------------------------------------
    def detect(self, frame: np.ndarray) -> list[Detection]:
        canvas, scale = self._letterbox(np.asarray(frame)[:, :, :3])
        # YOLOX: raw pixels, CHW, no /255. Channel order matches the export.
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32)
        raw = self._session.run(None, {self._input_name: blob})[0]
        return self._decode(raw, scale)

    def _decode(self, raw: np.ndarray, scale: float) -> list[Detection]:
        """Turn raw YOLOX output ``(1, N, 5+nc)`` into image-space detections."""
        pred = np.asarray(raw, dtype=np.float64)
        if pred.ndim == 3:
            pred = pred[0]
        if pred.shape[0] < pred.shape[1] and pred.shape[0] in (5 + 80, 6):
            pred = pred.T  # tolerate (5+nc, N) layout
        boxes = pred[:, :4]
        objectness = pred[:, 4]
        class_scores = pred[:, 5:]
        class_ids = class_scores.argmax(axis=1)
        confidences = objectness * class_scores.max(axis=1)

        keep = confidences >= self.conf_threshold
        boxes, class_ids, confidences = boxes[keep], class_ids[keep], confidences[keep]
        if boxes.shape[0] == 0:
            return []

        # cxcywh (network px) -> xyxy, then undo the letterbox scale.
        xyxy = np.empty_like(boxes)
        xyxy[:, 0] = (boxes[:, 0] - boxes[:, 2] / 2) / scale
        xyxy[:, 1] = (boxes[:, 1] - boxes[:, 3] / 2) / scale
        xyxy[:, 2] = (boxes[:, 0] + boxes[:, 2] / 2) / scale
        xyxy[:, 3] = (boxes[:, 1] + boxes[:, 3] / 2) / scale

        detections: list[Detection] = []
        for i in self._nms(xyxy, confidences):
            cid = int(class_ids[i])
            if self.class_filter is not None and cid not in self.class_filter:
                continue
            detections.append(
                Detection(xyxy=xyxy[i], score=float(confidences[i]), class_id=cid)
            )
        return detections

    def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> list[int]:
        order = list(scores.argsort()[::-1])
        keep: list[int] = []
        while order:
            i = order.pop(0)
            keep.append(i)
            if not order:
                break
            ious = iou_matrix(boxes[i][None], boxes[order])[0]
            order = [j for j, iou in zip(order, ious, strict=False)
                     if iou <= self.iou_threshold]
        return keep
