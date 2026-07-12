"""Evaluate a single experiment cell: (variant, sequence, seed) -> metrics.

Dataset-agnostic. For synthetic data the (sequence, seed) pair deterministically
selects a scene, so every variant is scored on the *same* scenes — that pairing
is what makes the downstream paired significance tests valid. For MOT17 the
tracker is deterministic, so ``seed`` currently only labels the cell (a hook for
future stochastic components, e.g. injected detector noise in RQ3).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from experiments.config import ExperimentConfig, VariantSpec
from visiontrack.eval.mot17 import evaluate_frames, run_sequence
from visiontrack.tracking.config import TrackerConfig
from visiontrack.tracking.tracker import ByteTracker


def _tracker_config(variant: VariantSpec) -> TrackerConfig:
    try:
        return replace(TrackerConfig(), **variant.overrides)
    except TypeError as exc:
        raise ValueError(
            f"variant '{variant.name}' has an invalid TrackerConfig override: {exc}"
        ) from exc


def _run_synthetic(sequence_id: int, seed: int, cfg: TrackerConfig, scene_kwargs: dict):
    from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig

    # sequence_id fixes the scene family; seed perturbs the noise realisation.
    scene_seed = int(sequence_id) * 1000 + int(seed)
    scene = SyntheticScene(SyntheticSceneConfig(seed=scene_seed, **scene_kwargs))
    tracker = ByteTracker(cfg)
    frames = []
    for f in scene:
        obs = tracker.update(f.detections)
        if obs:
            tr_ids = np.array([o.track_id for o in obs], dtype=np.int64)
            tr_boxes = np.stack([o.xyxy for o in obs], axis=0)
        else:
            tr_ids = np.empty((0,), dtype=np.int64)
            tr_boxes = np.empty((0, 4))
        frames.append((f.gt_ids, f.gt_boxes, tr_ids, tr_boxes))
    return frames


def _run_mot17(exp: ExperimentConfig, video: str, cfg: TrackerConfig):
    from visiontrack.datasets.cache import CachedSequence
    from visiontrack.datasets.splits import load_split

    split = load_split(exp.split_file)
    seq_name = f"{video}-{exp.detector}"
    npz = Path(exp.cache_dir) / f"{seq_name}.npz"
    if not npz.exists():
        raise FileNotFoundError(
            f"cache missing for {seq_name}: {npz} — run data/cache/precompute.py"
        )
    reader = CachedSequence(npz)
    first, last = split.range_for(seq_name, exp.split)
    return run_sequence(reader, cfg, first, last)


def evaluate_cell(exp: ExperimentConfig, variant: VariantSpec, sequence, seed: int) -> dict:
    """Run one cell and return its metric dict (CLEAR-MOT + IDF1 + HOTA)."""
    cfg = _tracker_config(variant)
    if exp.dataset == "synthetic":
        frames = _run_synthetic(sequence, seed, cfg, exp.scene)
    elif exp.dataset == "mot17":
        frames = _run_mot17(exp, str(sequence), cfg)
    else:
        raise ValueError(f"unknown dataset: {exp.dataset!r}")
    return evaluate_frames(frames)
