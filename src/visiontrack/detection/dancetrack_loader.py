"""DanceTrack loader with oracle-perturbed detections.

DanceTrack (CVPR'22) is the RQ1 *appearance-hurts* case: dancers wear near-
identical outfits (appearance is uninformative) and move non-linearly (the
constant-velocity motion prior struggles), so folding an appearance cost in can
actively cause identity swaps.

Unlike MOT17, DanceTrack ships **no public detections**. Rather than introduce a
detector-quality confound (which the MOT17 study showed dominates appearance's
effect), we synthesize detections by **perturbing the ground truth** — jitter,
drop, and false positives via :mod:`visiontrack.detection.noise`. This isolates
the association question (RQ1) and holds detection quality fixed across datasets,
exactly the oracle-perturbed protocol used by the synthetic probe. The appearance
embeddings still come from the *real* dancer crops, which is the whole point.

The GT format is MOT-style (``frame,id,x,y,w,h,…``); DanceTrack marks every box
as an active person (conf=1, class=1, vis=1), so there are no distractor rows to
filter. Frame files under ``img1`` may be zero-padded to 8 digits (vs MOT17's 6),
so callers that need the image path should use :func:`frame_filename`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .base import Detection
from .mot_loader import PEDESTRIAN_CLASS, FrameData, SeqInfo, _read_mot_txt, _xywh_to_xyxy
from .noise import NoiseConfig, perturb_detections

__all__ = ["DanceTrackSequence", "discover_dancetrack", "frame_filename"]


def frame_filename(img_dir: Path, frame_idx: int) -> Path | None:
    """Resolve a 1-indexed frame to its image file, auto-detecting zero padding.

    DanceTrack uses 8-digit names (``00000001.jpg``); MOT17 uses 6. Try the
    common widths, then fall back to a glob.
    """
    for width in (8, 6, 5, 7):
        p = img_dir / f"{frame_idx:0{width}d}.jpg"
        if p.exists():
            return p
    matches = sorted(img_dir.glob("*.jpg"))
    idx = frame_idx - 1
    return matches[idx] if 0 <= idx < len(matches) else None


class DanceTrackSequence:
    """A DanceTrack sequence; detections are perturbed GT (see module docstring).

    Read-side compatible with :class:`~visiontrack.detection.mot_loader.MOT17Sequence`
    (``info`` / ``frame`` / iteration), so :func:`save_sequence_cache` and every
    downstream reader work unchanged. Perturbation is deterministic per
    ``(seed, frame)``, so the detection stream is fixed and reproducible.
    """

    def __init__(self, seq_dir: str | Path, noise_cfg: NoiseConfig | None = None,
                 seed: int = 0) -> None:
        self.dir = Path(seq_dir)
        if not self.dir.exists():
            raise FileNotFoundError(f"sequence directory not found: {self.dir}")
        self.info = SeqInfo.from_ini(self.dir / "seqinfo.ini")
        self._gt = _read_mot_txt(self.dir / "gt" / "gt.txt", 9)
        self._gt_by_frame = self._index_by_frame(self._gt)
        self.cfg = noise_cfg or NoiseConfig()
        self.seed = seed

    @staticmethod
    def _index_by_frame(arr: np.ndarray) -> dict[int, np.ndarray]:
        index: dict[int, list[int]] = {}
        for i, frame in enumerate(arr[:, 0].astype(int)):
            index.setdefault(frame, []).append(i)
        return {f: arr[rows] for f, rows in index.items()}

    @property
    def name(self) -> str:
        return self.info.name

    def _gt_arrays(self, idx: int):
        rows = self._gt_by_frame.get(idx)
        if rows is None or rows.shape[0] == 0:
            z4 = np.empty((0, 4), dtype=np.float64)
            z = np.empty((0,), dtype=np.float64)
            return z4, z.astype(np.int64), z.astype(np.int64), z, z
        gt_xyxy = _xywh_to_xyxy(rows[:, 2:6].astype(np.float64))
        gt_ids = rows[:, 1].astype(np.int64)
        # DanceTrack has only people; mark them PEDESTRIAN so the MOT17-style
        # evaluator scores them (class != PEDESTRIAN_CLASS would be ignored).
        gt_classes = np.full(rows.shape[0], PEDESTRIAN_CLASS, dtype=np.int64)
        # DanceTrack marks all boxes active; tolerate missing conf/vis columns.
        gt_conf = rows[:, 6].astype(np.float64) if rows.shape[1] > 6 else np.ones(rows.shape[0])
        gt_vis = rows[:, 8].astype(np.float64) if rows.shape[1] > 8 else np.ones(rows.shape[0])
        return gt_xyxy, gt_ids, gt_classes, gt_conf, gt_vis

    def frame(self, idx: int) -> FrameData:
        gt_xyxy, gt_ids, gt_classes, gt_conf, gt_vis = self._gt_arrays(idx)
        # Oracle detections: perturb the active GT boxes.
        base = [Detection(xyxy=gt_xyxy[i], score=1.0, class_id=0)
                for i in range(gt_xyxy.shape[0]) if gt_conf[i] > 0]
        rng = np.random.default_rng([self.seed, idx])
        noisy = perturb_detections(base, rng, self.cfg, self.info.width, self.info.height)
        if noisy:
            det_xyxy = np.stack([d.xyxy for d in noisy], axis=0)
            det_scores = np.array([d.score for d in noisy], dtype=np.float64)
        else:
            det_xyxy = np.empty((0, 4), dtype=np.float64)
            det_scores = np.empty((0,), dtype=np.float64)
        return FrameData(
            frame=idx, det_xyxy=det_xyxy, det_scores=det_scores,
            gt_xyxy=gt_xyxy, gt_ids=gt_ids, gt_classes=gt_classes,
            gt_conf=gt_conf, gt_vis=gt_vis,
        )

    def __len__(self) -> int:
        return self.info.length

    def __iter__(self):
        for idx in range(1, self.info.length + 1):
            yield self.frame(idx)


def discover_dancetrack(root: str | Path, split: str = "val") -> list[Path]:
    """List DanceTrack sequence dirs under ``root/split`` (each has seqinfo.ini)."""
    base = Path(root) / split
    if not base.exists():
        base = Path(root)  # allow pointing straight at a split dir
    return sorted(p for p in base.iterdir() if (p / "seqinfo.ini").exists())
