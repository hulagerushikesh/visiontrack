"""Optional YOLO detector backed by ONNX Runtime.

This is intentionally an *optional* backend: the core tracker, tests and demo
run entirely on the synthetic generator and require nothing beyond NumPy. If
you want to track real video, drop in a YOLOv8-style ONNX model and this class
adapts its output to :class:`~visiontrack.detection.base.Detection`.

``onnxruntime`` and an image backend are imported lazily so importing the
package never fails when they are absent.
"""
from __future__ import annotations

import numpy as np

from .base import Detection

__all__ = ["OnnxYoloDetector"]


class OnnxYoloDetector:
    """Runs a YOLOv8-family ONNX model and emits :class:`Detection` objects.

    Parameters
    ----------
    model_path:
        Path to an exported ``.onnx`` model with output ``(1, 4 + nc, N)`` or
        ``(1, N, 4 + nc)`` (both layouts are auto-detected).
    input_size:
        Square network input side (letterboxed).
    conf_threshold, iou_threshold:
        Confidence gate and NMS IoU threshold.
    class_filter:
        If given, keep only these class ids (e.g. ``{0}`` for "person").
    """

    def __init__(
        self,
        model_path: str,
        input_size: int = 640,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        class_filter: set[int] | None = None,
        providers: list[str] | None = None,
    ) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "OnnxYoloDetector requires onnxruntime: pip install onnxruntime"
            ) from exc

        self._session = ort.InferenceSession(
            model_path, providers=providers or ["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.class_filter = class_filter

    # -- pre/post-processing ---------------------------------------------
    def _letterbox(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        h, w = frame.shape[:2]
        scale = min(self.input_size / h, self.input_size / w)
        nh, nw = int(round(h * scale)), int(round(w * scale))

        try:
            import cv2

            resized = cv2.resize(frame, (nw, nh))
        except ImportError:  # pragma: no cover - fallback nearest-neighbour
            ys = (np.linspace(0, h - 1, nh)).astype(int)
            xs = (np.linspace(0, w - 1, nw)).astype(int)
            resized = frame[ys][:, xs]

        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        pad_y = (self.input_size - nh) // 2
        pad_x = (self.input_size - nw) // 2
        canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
        return canvas, scale, (pad_x, pad_y)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        canvas, scale, (pad_x, pad_y) = self._letterbox(frame)
        blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        raw = self._session.run(None, {self._input_name: blob})[0]

        pred = np.squeeze(raw, 0)
        if pred.shape[0] < pred.shape[1]:  # (4+nc, N) -> (N, 4+nc)
            pred = pred.T

        boxes_cxcywh = pred[:, :4]
        class_scores = pred[:, 4:]
        class_ids = class_scores.argmax(axis=1)
        confidences = class_scores.max(axis=1)

        keep = confidences >= self.conf_threshold
        boxes_cxcywh, class_ids, confidences = (
            boxes_cxcywh[keep],
            class_ids[keep],
            confidences[keep],
        )
        if boxes_cxcywh.shape[0] == 0:
            return []

        # cxcywh (network space) -> xyxy (original image space).
        xyxy = np.empty_like(boxes_cxcywh)
        xyxy[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        xyxy[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        xyxy[:, 2] = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        xyxy[:, 3] = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2
        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_x) / scale
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_y) / scale

        keep_idx = self._nms(xyxy, confidences)
        detections: list[Detection] = []
        for i in keep_idx:
            cid = int(class_ids[i])
            if self.class_filter is not None and cid not in self.class_filter:
                continue
            detections.append(
                Detection(xyxy=xyxy[i], score=float(confidences[i]), class_id=cid)
            )
        return detections

    def _nms(self, boxes: np.ndarray, scores: np.ndarray) -> list[int]:
        from ..core.geometry import iou_matrix

        order = scores.argsort()[::-1]
        keep: list[int] = []
        idxs = list(order)
        while idxs:
            i = idxs.pop(0)
            keep.append(i)
            if not idxs:
                break
            ious = iou_matrix(boxes[i][None], boxes[idxs])[0]
            idxs = [j for j, iou in zip(idxs, ious, strict=False) if iou <= self.iou_threshold]
        return keep
