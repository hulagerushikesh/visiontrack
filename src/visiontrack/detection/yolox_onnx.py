"""YOLOX detector via ONNX Runtime — the detector for H2 "run on real video".

YOLOX is the detector the ByteTrack / OC-SORT papers use, so it keeps this
project's tracking lineage consistent. Its ONNX output differs from the YOLOv8
family handled by :mod:`~visiontrack.detection.onnx_yolo`:

* output is ``(1, N, 5 + nc)`` = ``[cx, cy, w, h, objectness, class scores…]``
  where ``N`` is the total number of anchor points over strides 8/16/32, and
* preprocessing letterboxes to a padded square with **no** ``/255`` or mean/std
  normalisation (YOLOX consumes raw pixel values).

The box columns come in two flavours and we handle **both**, auto-detected:

* **decode baked in** (exported with ``--decode_in_inference``) — ``cx,cy,w,h``
  are already in network-pixel space; used directly.
* **raw grid output** (the *default* export, and what the official Megvii release
  ONNX files ship) — ``cx,cy`` are per-cell offsets and ``w,h`` are log-scale, so
  the standard grid/stride decode ``xy=(off+grid)·stride``, ``wh=exp(wh)·stride``
  is applied first. The two are told apart by coordinate magnitude (raw offsets
  are ``≪`` the input size).

Score is ``objectness × max class score``. ``onnxruntime`` is imported lazily; the
decode is a pure-NumPy method so it is unit-testable with a fake session (no model
or onnxruntime needed in CI) — the same pattern as :class:`OnnxReID`.
"""
from __future__ import annotations

import numpy as np

from ..core.geometry import iou_matrix
from .base import Detection
from .proposal_capture import ProposalCapture, _ProposalRecorder, _validate_limit

__all__ = ["YoloxDetector", "ProposalCapture"]


class YoloxDetector:
    def __init__(
        self,
        model_path: str,
        input_size: int = 416,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        class_filter: set[int] | None = None,
        strides: tuple[int, ...] = (8, 16, 32),
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
        self.strides = strides
        self._grid_cache: tuple[np.ndarray, np.ndarray] | None = None

    # -- grid decode (for raw, non-decode-baked exports) ------------------
    def _grids(self) -> tuple[np.ndarray, np.ndarray]:
        """Cached ``(grid_xy, stride)`` anchor tables for strides 8/16/32.

        Row order matches YOLOX's flattened output: per stride, cells in
        row-major order, strides concatenated small→large.
        """
        if self._grid_cache is None:
            grids, strides = [], []
            for stride in self.strides:
                g = self.input_size // stride
                xv, yv = np.meshgrid(np.arange(g), np.arange(g))
                grids.append(np.stack((xv, yv), axis=2).reshape(-1, 2))
                strides.append(np.full((g * g, 1), stride, dtype=np.float64))
            self._grid_cache = (
                np.concatenate(grids, axis=0).astype(np.float64),
                np.concatenate(strides, axis=0),
            )
        return self._grid_cache

    def _grid_decode(self, boxes: np.ndarray) -> np.ndarray:
        """Map raw ``cx,cy`` offsets + log ``w,h`` to network-pixel ``cxcywh``."""
        grid, stride = self._grids()
        if boxes.shape[0] != grid.shape[0]:  # unexpected N — leave untouched
            return boxes
        out = np.empty_like(boxes)
        out[:, :2] = (boxes[:, :2] + grid) * stride
        out[:, 2:4] = np.exp(boxes[:, 2:4]) * stride
        return out

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
        raw, scale = self._infer(frame)
        return self._decode(raw, scale)

    def detect_with_proposals(
        self, frame: np.ndarray, *, max_proposals: int = 4096,
    ) -> tuple[list[Detection], ProposalCapture]:
        """Run once; return normal detections plus bounded research diagnostics.

        Keeps the first ``max_proposals`` original rows (zero means counts only).
        Suppression is class-agnostic; class filtering happens afterwards, just
        as in :meth:`detect`. The detector never stores the returned capture.
        No uncertainty/covariance is estimated. See ``ProposalCapture`` for limits.
        """
        _validate_limit(max_proposals)  # reject before model execution
        raw, scale = self._infer(frame)
        detections, capture = self._decode_frame(raw, scale, max_proposals)
        assert capture is not None
        return detections, capture

    def _infer(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        canvas, scale = self._letterbox(np.asarray(frame)[:, :, :3])
        # YOLOX: raw pixels, CHW, no /255. Channel order matches the export.
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32)
        raw = self._session.run(None, {self._input_name: blob})[0]
        return raw, scale

    def _decode(self, raw: np.ndarray, scale: float) -> list[Detection]:
        """Turn raw YOLOX output ``(1, N, 5+nc)`` into image-space detections."""
        return self._decode_frame(raw, scale)[0]

    def _decode_frame(
        self, raw: np.ndarray, scale: float, max_proposals: int | None = None,
    ) -> tuple[list[Detection], ProposalCapture | None]:
        pred = np.asarray(raw, dtype=np.float64)
        transposed = False
        if pred.ndim == 3:
            pred = pred[0]
        if pred.shape[0] < pred.shape[1] and pred.shape[0] in (5 + 80, 6):
            pred = pred.T  # tolerate (5+nc, N) layout
            transposed = True
        boxes = pred[:, :4]
        # Raw (non-decode-baked) exports emit per-cell offsets whose magnitude is
        # ≪ the input size; decode-baked exports emit pixel coords. Auto-detect.
        grid_decode_applied = False
        if boxes.shape[0] and boxes[:, :2].max() < self.input_size / 8:
            decoded = self._grid_decode(boxes)
            grid_decode_applied = decoded is not boxes
            boxes = decoded
        objectness = pred[:, 4]
        class_scores = pred[:, 5:]
        class_ids = class_scores.argmax(axis=1)
        confidences = objectness * class_scores.max(axis=1)

        keep = confidences >= self.conf_threshold
        recorder = None if max_proposals is None else _ProposalRecorder(
            boxes, objectness, class_scores, class_ids, confidences, keep, scale, max_proposals,
        )
        boxes, class_ids, confidences = boxes[keep], class_ids[keep], confidences[keep]

        # cxcywh (network px) -> xyxy, then undo the letterbox scale.
        xyxy = np.empty_like(boxes)
        xyxy[:, 0] = (boxes[:, 0] - boxes[:, 2] / 2) / scale
        xyxy[:, 1] = (boxes[:, 1] - boxes[:, 3] / 2) / scale
        xyxy[:, 2] = (boxes[:, 0] + boxes[:, 2] / 2) / scale
        xyxy[:, 3] = (boxes[:, 1] + boxes[:, 3] / 2) / scale

        detections: list[Detection] = []
        for i in self._nms(xyxy, confidences, recorder=recorder):
            cid = int(class_ids[i])
            if self.class_filter is not None and cid not in self.class_filter:
                if recorder is not None:
                    recorder.output(i, None)
                continue
            if recorder is not None:
                recorder.output(i, len(detections))
            detections.append(
                Detection(xyxy=xyxy[i], score=float(confidences[i]), class_id=cid)
            )
        if recorder is None:
            return detections, None
        capture = ProposalCapture(
            max_proposals=max_proposals, total_proposals=len(pred),
            raw_shape=tuple(raw.shape), transposed=transposed,
            grid_decode_applied=grid_decode_applied, input_size=self.input_size,
            strides=tuple(self.strides), scale=float(scale),
            conf_threshold=float(self.conf_threshold), iou_threshold=float(self.iou_threshold),
            class_filter=None if self.class_filter is None else tuple(sorted(self.class_filter)),
            confidence_filtered_count=len(pred) - len(boxes),
            nms_suppressed_count=recorder.nms_suppressed_count,
            nms_kept_count=recorder.nms_kept_count,
            class_filtered_count=recorder.class_filtered_count,
            returned_count=len(detections), records=tuple(recorder.records),
        )
        return detections, capture

    def _nms(
        self, boxes: np.ndarray, scores: np.ndarray, *, recorder: _ProposalRecorder | None = None,
    ) -> list[int]:
        order = list(scores.argsort()[::-1])
        keep: list[int] = []
        while order:
            i = order.pop(0)
            keep.append(i)
            if not order:
                if recorder is not None:
                    recorder.selection(i, [], np.empty(0), self.iou_threshold)
                break
            ious = iou_matrix(boxes[i][None], boxes[order])[0]
            if recorder is not None:
                recorder.selection(i, order, ious, self.iou_threshold)
            order = [j for j, iou in zip(order, ious, strict=False)
                     if iou <= self.iou_threshold]
        return keep
