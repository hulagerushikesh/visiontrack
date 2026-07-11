"""Compact on-disk cache of MOT17 detections + ground truth.

One compressed ``.npz`` per sequence stores every frame's public detections
and raw ground truth as flat arrays. This is the durable artifact of Phase 0:
once a sequence is cached, tracking experiments read **only** the cache and the
multi-GB ``img1/`` frames can be deleted.

The cache is intentionally numpy-only on the read path — no pandas, no parquet
engine — so it stays fast and dependency-light, and can be consumed frame by
frame without loading the whole sequence.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from ..detection.base import Detection
from ..detection.mot_loader import FrameData, MOT17Sequence

__all__ = ["save_sequence_cache", "CachedSequence"]

_SCHEMA_VERSION = 1


def save_sequence_cache(seq: MOT17Sequence, out_path: str | Path) -> Path:
    """Serialize an entire :class:`MOT17Sequence` to a compressed ``.npz``.

    Stores all frames flat (one row per detection / per GT box, tagged with its
    frame index) plus sequence metadata. Returns the written path.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    det_frame, det_xyxy, det_score = [], [], []
    gt_frame, gt_id, gt_xyxy, gt_class, gt_conf, gt_vis = [], [], [], [], [], []

    for fd in seq:  # streams frame by frame
        d = fd.det_xyxy.shape[0]
        if d:
            det_frame.append(np.full(d, fd.frame, dtype=np.int32))
            det_xyxy.append(fd.det_xyxy)
            det_score.append(fd.det_scores)
        g = fd.gt_xyxy.shape[0]
        if g:
            gt_frame.append(np.full(g, fd.frame, dtype=np.int32))
            gt_id.append(fd.gt_ids)
            gt_xyxy.append(fd.gt_xyxy)
            gt_class.append(fd.gt_classes)
            gt_conf.append(fd.gt_conf)
            gt_vis.append(fd.gt_vis)

    def _cat(chunks, cols):
        if not chunks:
            return np.empty((0, cols) if cols else (0,), dtype=np.float64)
        return np.concatenate(chunks, axis=0)

    np.savez_compressed(
        out_path,
        schema_version=_SCHEMA_VERSION,
        name=seq.info.name,
        detector=seq.info.name.split("-")[-1],
        length=seq.info.length,
        width=seq.info.width,
        height=seq.info.height,
        frame_rate=seq.info.frame_rate,
        det_frame=_cat(det_frame, 0).astype(np.int32),
        det_xyxy=_cat(det_xyxy, 4).astype(np.float32),
        det_score=_cat(det_score, 0).astype(np.float32),
        gt_frame=_cat(gt_frame, 0).astype(np.int32),
        gt_id=_cat(gt_id, 0).astype(np.int32),
        gt_xyxy=_cat(gt_xyxy, 4).astype(np.float32),
        gt_class=_cat(gt_class, 0).astype(np.int16),
        gt_conf=_cat(gt_conf, 0).astype(np.float32),
        gt_vis=_cat(gt_vis, 0).astype(np.float32),
    )
    return out_path.with_suffix(".npz") if out_path.suffix != ".npz" else out_path


class CachedSequence:
    """Read a cached sequence and stream :class:`FrameData` per frame.

    Drop-in replacement for :class:`MOT17Sequence` on the *read* side: same
    ``frame`` / iteration / ``iter_range`` interface, but backed by the npz
    cache with no dependency on the raw dataset.
    """

    def __init__(self, npz_path: str | Path) -> None:
        self.path = Path(npz_path)
        with np.load(self.path, allow_pickle=False) as z:
            self.name = str(z["name"])
            self.detector = str(z["detector"])
            self.length = int(z["length"])
            self.width = int(z["width"])
            self.height = int(z["height"])
            self.frame_rate = int(z["frame_rate"])
            self._det_frame = z["det_frame"]
            self._det_xyxy = z["det_xyxy"].astype(np.float64)
            self._det_score = z["det_score"].astype(np.float64)
            self._gt_frame = z["gt_frame"]
            self._gt_id = z["gt_id"].astype(np.int64)
            self._gt_xyxy = z["gt_xyxy"].astype(np.float64)
            self._gt_class = z["gt_class"].astype(np.int64)
            self._gt_conf = z["gt_conf"].astype(np.float64)
            self._gt_vis = z["gt_vis"].astype(np.float64)

        self._det_index = self._build_index(self._det_frame)
        self._gt_index = self._build_index(self._gt_frame)

    @staticmethod
    def _build_index(frames: np.ndarray) -> dict[int, np.ndarray]:
        index: dict[int, list[int]] = {}
        for i, f in enumerate(frames.tolist()):
            index.setdefault(int(f), []).append(i)
        return {f: np.asarray(rows, dtype=np.int64) for f, rows in index.items()}

    def __len__(self) -> int:
        return self.length

    def frame(self, idx: int) -> FrameData:
        di = self._det_index.get(idx)
        if di is None:
            det_xyxy, det_scores = np.empty((0, 4)), np.empty((0,))
        else:
            det_xyxy, det_scores = self._det_xyxy[di], self._det_score[di]

        gi = self._gt_index.get(idx)
        if gi is None:
            gt_xyxy = np.empty((0, 4))
            gt_ids = np.empty((0,), dtype=np.int64)
            gt_classes = np.empty((0,), dtype=np.int64)
            gt_conf = np.empty((0,))
            gt_vis = np.empty((0,))
        else:
            gt_xyxy = self._gt_xyxy[gi]
            gt_ids = self._gt_id[gi]
            gt_classes = self._gt_class[gi]
            gt_conf = self._gt_conf[gi]
            gt_vis = self._gt_vis[gi]

        return FrameData(
            frame=idx,
            det_xyxy=det_xyxy,
            det_scores=det_scores,
            gt_xyxy=gt_xyxy,
            gt_ids=gt_ids,
            gt_classes=gt_classes,
            gt_conf=gt_conf,
            gt_vis=gt_vis,
        )

    def __iter__(self) -> Iterator[FrameData]:
        for idx in range(1, self.length + 1):
            yield self.frame(idx)

    def iter_range(self, first: int, last: int) -> Iterator[FrameData]:
        for idx in range(first, last + 1):
            yield self.frame(idx)

    def detections_at(self, idx: int) -> list[Detection]:
        return self.frame(idx).detections()
