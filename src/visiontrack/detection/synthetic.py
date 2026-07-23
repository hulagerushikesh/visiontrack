"""A controllable synthetic scene generator.

Real MOT benchmarks require large video downloads and a heavyweight detector.
For development, testing and reproducible benchmarking we instead *simulate* a
scene: objects move on smooth trajectories, and a virtual "detector" observes
them through a configurable noise model — localisation jitter, missed
detections, spurious false positives and mutual occlusion.

Because the generator emits both the ground-truth tracks and the noisy
detections, it doubles as an evaluation oracle: run the tracker on the
detections, then score its output against the ground truth with
:mod:`visiontrack.eval.mot`.

The generator is fully deterministic given a seed, so benchmarks and tests
are reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Detection

__all__ = ["SceneObject", "SyntheticSceneConfig", "SyntheticScene", "Frame"]


@dataclass(slots=True)
class SceneObject:
    """A ground-truth object with linear motion and sinusoidal size breathing."""

    obj_id: int
    pos: np.ndarray          # centre (cx, cy)
    vel: np.ndarray          # velocity (vx, vy)
    size: np.ndarray         # (w, h)
    class_id: int = 0
    born: int = 0
    dies: int = 10_000
    _phase: float = 0.0
    appearance: np.ndarray | None = None  # unit "true" Re-ID descriptor (RQ1 probe)

    def box_at(self, t: int) -> np.ndarray:
        cx, cy = self.pos + self.vel * t
        # A gentle scale oscillation mimics perspective/pose change.
        breathe = 1.0 + 0.06 * np.sin(0.15 * t + self._phase)
        w, h = self.size * breathe
        return np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])

    def alive_at(self, t: int) -> bool:
        return self.born <= t < self.dies


@dataclass(slots=True)
class Frame:
    """One simulated frame: ground truth plus what the detector reported."""

    index: int
    detections: list[Detection]
    gt_boxes: np.ndarray            # (K, 4) xyxy
    gt_ids: np.ndarray              # (K,) object ids


@dataclass(slots=True)
class SyntheticSceneConfig:
    width: int = 1280
    height: int = 720
    num_objects: int = 6
    num_frames: int = 120
    # Detector noise model.
    loc_noise_std: float = 3.0        # px std of box-corner jitter
    miss_rate: float = 0.08           # probability a real object is missed
    occluded_miss_rate: float = 0.25  # extra miss probability when occluded
    false_positive_rate: float = 0.3  # expected # of spurious boxes per frame
    score_true: tuple[float, float] = (0.55, 0.98)   # score range for true det.
    score_false: tuple[float, float] = (0.10, 0.55)  # score range for FP
    occlusion_iou: float = 0.55       # if two GT boxes overlap more, the
                                      # occluded one is likely dropped
    # Appearance (Re-ID) probe for RQ1. OFF by default (dim=0) so scenes with no
    # appearance are byte-identical to before — no extra RNG is drawn.
    appearance_dim: int = 0           # 0 = no appearance; >0 emits det features
    appearance_diversity: float = 1.0  # 0 = all objects identical … 1 = fully distinct
    appearance_noise_std: float = 0.15  # obs. noise added to each detection's feature
    appearance_occluded_noise_mult: float = 2.5  # embeddings degrade under occlusion
    seed: int = 0


class SyntheticScene:
    """Deterministic generator of :class:`Frame` objects."""

    def __init__(self, config: SyntheticSceneConfig | None = None) -> None:
        self.cfg = config or SyntheticSceneConfig()
        self._rng = np.random.default_rng(self.cfg.seed)
        self._objects = self._spawn_objects()

    # -- scene construction ----------------------------------------------
    def _spawn_objects(self) -> list[SceneObject]:
        cfg = self.cfg
        rng = self._rng
        objects: list[SceneObject] = []
        for oid in range(cfg.num_objects):
            pos = rng.uniform([0.1, 0.1], [0.9, 0.9]) * [cfg.width, cfg.height]
            speed = rng.uniform(1.5, 6.0)
            angle = rng.uniform(0, 2 * np.pi)
            vel = np.array([np.cos(angle), np.sin(angle)]) * speed
            h = rng.uniform(60, 160)
            w = h * rng.uniform(0.35, 0.75)
            # Stagger births/deaths so the tracker must handle entries/exits.
            born = int(rng.integers(0, max(1, cfg.num_frames // 4)))
            lifespan = int(rng.integers(cfg.num_frames // 2, cfg.num_frames + 1))
            objects.append(
                SceneObject(
                    obj_id=oid,
                    pos=pos,
                    vel=vel,
                    size=np.array([w, h]),
                    class_id=int(rng.integers(0, 3)),
                    born=born,
                    dies=min(cfg.num_frames, born + lifespan),
                    _phase=float(rng.uniform(0, 2 * np.pi)),
                )
            )
        self._assign_appearance(objects)
        return objects

    def _assign_appearance(self, objects: list[SceneObject]) -> None:
        """Give each object a unit appearance vector, dialled by diversity.

        ``appearance = normalize((1 - d) * prototype + d * random_i)`` where the
        prototype is shared: ``d=0`` makes every object identical (the DanceTrack
        regime where appearance is uninformative), ``d=1`` makes them fully
        distinct (the MOT17 regime where it helps). The number of RNG draws is
        independent of ``d``, so a scene's geometry/noise is held fixed while only
        appearance varies — a valid controlled probe. No draws when disabled.
        """
        cfg = self.cfg
        if cfg.appearance_dim <= 0:
            return
        rng = self._rng
        d = float(np.clip(cfg.appearance_diversity, 0.0, 1.0))
        proto = self._unit(rng.normal(size=cfg.appearance_dim))
        for obj in objects:
            ri = self._unit(rng.normal(size=cfg.appearance_dim))
            obj.appearance = self._unit((1.0 - d) * proto + d * ri)

    @staticmethod
    def _unit(v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    # -- per-frame simulation --------------------------------------------
    def _in_bounds(self, box: np.ndarray) -> bool:
        cx = (box[0] + box[2]) / 2
        cy = (box[1] + box[3]) / 2
        return 0 <= cx <= self.cfg.width and 0 <= cy <= self.cfg.height

    def frame(self, t: int) -> Frame:
        from ..core.geometry import iou_matrix  # local import avoids cycle

        cfg = self.cfg
        rng = self._rng

        live = [o for o in self._objects if o.alive_at(t) and self._in_bounds(o.box_at(t))]
        gt_boxes = np.array([o.box_at(t) for o in live]).reshape(-1, 4)
        gt_ids = np.array([o.obj_id for o in live], dtype=np.int64)

        # Occlusion: the object drawn "behind" (smaller area, treated as
        # farther) has its detection degraded. Crucially, a real detector
        # under occlusion usually emits a *low-confidence* box rather than
        # nothing — modelling that is what makes the ByteTrack recovery stage
        # (and its ablation) meaningful.
        occluded = np.zeros(len(live), dtype=bool)
        if len(live) > 1:
            ious = iou_matrix(gt_boxes, gt_boxes)
            areas = (gt_boxes[:, 2] - gt_boxes[:, 0]) * (gt_boxes[:, 3] - gt_boxes[:, 1])
            for i in range(len(live)):
                for j in range(i + 1, len(live)):
                    if ious[i, j] > cfg.occlusion_iou:
                        behind = i if areas[i] < areas[j] else j
                        occluded[behind] = True

        detections: list[Detection] = []
        for k, obj in enumerate(live):
            is_occluded = occluded[k]
            # Occluded objects are missed more often; when seen at all they
            # come back weak and poorly localised.
            miss_p = cfg.miss_rate + (cfg.occluded_miss_rate if is_occluded else 0.0)
            if rng.random() < miss_p:
                continue
            noise = cfg.loc_noise_std * (2.5 if is_occluded else 1.0)
            box = self._fix_box(gt_boxes[k] + rng.normal(0, noise, size=4))
            score_range = cfg.score_false if is_occluded else cfg.score_true
            score = float(rng.uniform(*score_range))
            feature = None
            if obj.appearance is not None:
                fn = cfg.appearance_noise_std * (
                    cfg.appearance_occluded_noise_mult if is_occluded else 1.0
                )
                feature = self._unit(obj.appearance + rng.normal(0, fn, size=obj.appearance.shape))
            detections.append(
                Detection(xyxy=box, score=score, class_id=obj.class_id, feature=feature)
            )

        # False positives: Poisson-distributed spurious boxes.
        n_fp = rng.poisson(cfg.false_positive_rate)
        for _ in range(n_fp):
            cx, cy = rng.uniform([0, 0], [cfg.width, cfg.height])
            h = rng.uniform(50, 150)
            w = h * rng.uniform(0.3, 0.8)
            box = self._fix_box([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
            score = float(rng.uniform(*cfg.score_false))
            feature = None
            if cfg.appearance_dim > 0:
                feature = self._unit(rng.normal(size=cfg.appearance_dim))
            detections.append(
                Detection(xyxy=box, score=score, class_id=int(rng.integers(0, 3)), feature=feature)
            )

        rng.shuffle(detections)  # detectors do not emit in a stable order
        return Frame(index=t, detections=detections, gt_boxes=gt_boxes, gt_ids=gt_ids)

    @staticmethod
    def _fix_box(box) -> np.ndarray:
        b = np.asarray(box, dtype=np.float64)
        x1, x2 = sorted((b[0], b[2]))
        y1, y2 = sorted((b[1], b[3]))
        # Guarantee a minimum extent so no degenerate boxes reach the tracker.
        if x2 - x1 < 1:
            x2 = x1 + 1
        if y2 - y1 < 1:
            y2 = y1 + 1
        return np.array([x1, y1, x2, y2])

    def frames(self) -> list[Frame]:
        return [self.frame(t) for t in range(self.cfg.num_frames)]

    def __iter__(self):
        for t in range(self.cfg.num_frames):
            yield self.frame(t)

    def __len__(self) -> int:
        return self.cfg.num_frames
