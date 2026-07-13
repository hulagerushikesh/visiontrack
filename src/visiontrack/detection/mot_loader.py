"""MOT Challenge (MOT17) dataset loader.

Parses the on-disk MOT17 format — ``seqinfo.ini``, ``det/det.txt`` and
``gt/gt.txt`` — into per-frame detections and ground truth, **streaming one
frame at a time** so a whole sequence never sits in memory (the 8GB-RAM
constraint). Image frames (``img1/``) are never read: Phase 0 uses MOT17's
**public detections**, so the tracker is scored with no detector confound.

Format notes (the parts that bite you if you get them wrong)
-----------------------------------------------------------
Both txt files are comma-separated, **1-indexed frames**, top-left-origin
boxes stored as ``(bb_left, bb_top, bb_width, bb_height)``.

``det/det.txt`` columns::

    frame, id(=-1), bb_left, bb_top, bb_w, bb_h, conf, x, y, z

``id`` is always ``-1`` for detections; ``conf`` is the detector score and its
range **differs per detector** — SDP/FRCNN are already confidences in ``[0, 1]``
and are left untouched, but DPM is unbounded (log-likelihood ratios, can be
negative). Only out-of-range scores are min-max normalised per sequence, so the
tracker's high/low thresholds mean the same thing everywhere without distorting
an already-valid distribution.

``gt/gt.txt`` columns (MOT17)::

    frame, id, bb_left, bb_top, bb_w, bb_h, conf_flag, class, visibility

Here ``conf_flag`` is a 0/1 *consider* flag (0 ⇒ ignore this box), ``class`` is
the MOT17 class id (pedestrian = 1; distractor classes are handled at
evaluation time — see :mod:`visiontrack.eval.mot17`), and ``visibility`` ∈
``[0, 1]``. All three are preserved here; the loader does **not** filter them,
because faithful MOT17 scoring needs the distractor/ignore rows too.
"""
from __future__ import annotations

import configparser
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .base import Detection

__all__ = [
    "SeqInfo",
    "FrameData",
    "MOT17Sequence",
    "PEDESTRIAN_CLASS",
    "DISTRACTOR_CLASSES",
]

# MOT17 class semantics used by the evaluator's ignore logic.
PEDESTRIAN_CLASS = 1
# Classes whose GT boxes are "distractors": a tracker box matched to one is
# removed (not penalised as a false positive) during MOT17 preprocessing.
DISTRACTOR_CLASSES = frozenset({2, 7, 8, 12})


@dataclass(slots=True)
class SeqInfo:
    """Contents of a sequence's ``seqinfo.ini``."""

    name: str
    frame_rate: int
    length: int
    width: int
    height: int
    im_dir: str = "img1"
    im_ext: str = ".jpg"

    @classmethod
    def from_ini(cls, path: Path) -> SeqInfo:
        parser = configparser.ConfigParser()
        parser.read(path)
        s = parser["Sequence"]
        return cls(
            name=s.get("name", path.parent.name),
            frame_rate=int(s.get("frameRate", 30)),
            length=int(s.get("seqLength", 0)),
            width=int(s.get("imWidth", 0)),
            height=int(s.get("imHeight", 0)),
            im_dir=s.get("imDir", "img1"),
            im_ext=s.get("imExt", ".jpg"),
        )


@dataclass(slots=True)
class FrameData:
    """Everything known about one frame (1-indexed).

    Detection arrays are the public detections; GT arrays are the raw MOT17
    ground truth *including* distractor/ignore rows (filtering happens in the
    evaluator, not here).
    """

    frame: int
    det_xyxy: np.ndarray       # (D, 4)
    det_scores: np.ndarray     # (D,) normalised to [0, 1]
    gt_xyxy: np.ndarray        # (G, 4)
    gt_ids: np.ndarray         # (G,)
    gt_classes: np.ndarray     # (G,)
    gt_conf: np.ndarray        # (G,) 0/1 consider flag
    gt_vis: np.ndarray         # (G,) visibility in [0, 1]
    det_features: np.ndarray | None = None  # (D, F) appearance embeddings, if cached

    def detections(self) -> list[Detection]:
        """Public detections as :class:`Detection` objects (class-agnostic).

        Attaches cached appearance embeddings when available.
        """
        feats = self.det_features
        return [
            Detection(
                xyxy=self.det_xyxy[i],
                score=float(self.det_scores[i]),
                class_id=0,
                feature=None if feats is None else feats[i],
            )
            for i in range(self.det_xyxy.shape[0])
        ]


def _read_mot_txt(path: Path, min_cols: int) -> np.ndarray:
    """Read a MOT csv into an ``(N, C)`` float array (empty-safe)."""
    if not path.exists():
        return np.empty((0, min_cols), dtype=np.float64)
    arr = np.loadtxt(path, delimiter=",", ndmin=2)
    if arr.size == 0:
        return np.empty((0, min_cols), dtype=np.float64)
    return arr.astype(np.float64)


def _xywh_to_xyxy(a: np.ndarray) -> np.ndarray:
    out = np.empty_like(a)
    out[:, 0] = a[:, 0]
    out[:, 1] = a[:, 1]
    out[:, 2] = a[:, 0] + a[:, 2]
    out[:, 3] = a[:, 1] + a[:, 3]
    return out


class MOT17Sequence:
    """A single MOT17 sequence directory (e.g. ``MOT17-02-FRCNN``).

    Loads the (small) txt annotations eagerly, indexes rows by frame, and
    exposes a frame-streaming iterator. Detection scores are min-max
    normalised per sequence unless ``normalize_scores=False``.
    """

    def __init__(self, seq_dir: str | Path, normalize_scores: bool = True) -> None:
        self.dir = Path(seq_dir)
        if not self.dir.exists():
            raise FileNotFoundError(f"sequence directory not found: {self.dir}")
        self.info = SeqInfo.from_ini(self.dir / "seqinfo.ini")
        self.normalize_scores = normalize_scores

        self._det = _read_mot_txt(self.dir / "det" / "det.txt", 7)
        self._gt = _read_mot_txt(self.dir / "gt" / "gt.txt", 9)

        self._score_range = self._compute_score_range()
        self._det_by_frame = self._index_by_frame(self._det)
        self._gt_by_frame = self._index_by_frame(self._gt)

    # -- indexing ---------------------------------------------------------
    @staticmethod
    def _index_by_frame(arr: np.ndarray) -> dict[int, np.ndarray]:
        index: dict[int, list[int]] = {}
        for i, frame in enumerate(arr[:, 0].astype(int)):
            index.setdefault(frame, []).append(i)
        return {f: arr[rows] for f, rows in index.items()}

    def _compute_score_range(self) -> tuple[float, float]:
        if self._det.shape[0] == 0:
            return (0.0, 1.0)
        scores = self._det[:, 6]
        lo, hi = float(scores.min()), float(scores.max())
        if hi - lo < 1e-9:
            return (lo, lo + 1.0)  # avoid divide-by-zero on constant scores
        return (lo, hi)

    def _norm(self, scores: np.ndarray) -> np.ndarray:
        """Map detector scores to ``[0, 1]``.

        FRCNN/SDP public detections are already confidences in ``[0, 1]`` and
        are passed through unchanged (min-max rescaling would *destroy* a valid
        distribution — e.g. mapping a genuine 0.5 to 0). Only when the score
        range falls outside ``[0, 1]`` (DPM, whose scores are unbounded
        log-likelihood ratios) do we min-max normalise so the tracker's high/low
        thresholds remain meaningful.
        """
        if not self.normalize_scores:
            return np.clip(scores, 0.0, 1.0)
        lo, hi = self._score_range
        if lo >= 0.0 and hi <= 1.0:
            return np.clip(scores, 0.0, 1.0)  # already valid confidences
        return np.clip((scores - lo) / (hi - lo), 0.0, 1.0)

    # -- streaming --------------------------------------------------------
    @property
    def name(self) -> str:
        return self.info.name

    def __len__(self) -> int:
        return self.info.length

    def frame(self, idx: int) -> FrameData:
        """Return :class:`FrameData` for a 1-indexed frame ``idx``."""
        det = self._det_by_frame.get(idx)
        if det is None:
            det_xyxy = np.empty((0, 4))
            det_scores = np.empty((0,))
        else:
            det_xyxy = _xywh_to_xyxy(det[:, 2:6])
            det_scores = self._norm(det[:, 6])

        gt = self._gt_by_frame.get(idx)
        if gt is None:
            gt_xyxy = np.empty((0, 4))
            gt_ids = np.empty((0,), dtype=np.int64)
            gt_classes = np.empty((0,), dtype=np.int64)
            gt_conf = np.empty((0,))
            gt_vis = np.empty((0,))
        else:
            gt_xyxy = _xywh_to_xyxy(gt[:, 2:6])
            gt_ids = gt[:, 1].astype(np.int64)
            gt_conf = gt[:, 6]
            has_cls = gt.shape[1] > 7
            gt_classes = gt[:, 7].astype(np.int64) if has_cls else np.ones(len(gt), dtype=np.int64)
            gt_vis = gt[:, 8] if gt.shape[1] > 8 else np.ones(len(gt))

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
        for idx in range(1, self.info.length + 1):
            yield self.frame(idx)

    def iter_range(self, first: int, last: int) -> Iterator[FrameData]:
        """Stream frames ``[first, last]`` inclusive (1-indexed)."""
        for idx in range(first, last + 1):
            yield self.frame(idx)


def discover_sequences(
    data_root: str | Path, split: str = "train", detector: str | None = None
) -> list[Path]:
    """List MOT17 sequence directories under ``<root>/<split>``.

    ``detector`` filters to one of ``DPM|FRCNN|SDP`` (each MOT17 video ships as
    three sequences, one per public detector, sharing the same ground truth).
    """
    base = Path(data_root) / split
    if not base.exists():
        raise FileNotFoundError(f"MOT17 split directory not found: {base}")
    seqs = sorted(p for p in base.iterdir() if p.is_dir() and (p / "seqinfo.ini").exists())
    if detector is not None:
        seqs = [p for p in seqs if p.name.endswith(f"-{detector}")]
    return seqs
