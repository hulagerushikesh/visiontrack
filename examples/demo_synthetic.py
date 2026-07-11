"""End-to-end example: simulate a scene, track it, score it, visualise it.

Run from the project root::

    PYTHONPATH=src python examples/demo_synthetic.py

Writes ``trajectories.png`` and ``tracking.gif`` next to this file (the GIF
needs the ``viz`` extra: matplotlib + pillow).
"""
from __future__ import annotations

import os

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.tracker import ByteTracker
from visiontrack.viz.draw import FrameRender, animate_scene, save_trajectory_plot

HERE = os.path.dirname(__file__)


def main() -> None:
    scene = SyntheticScene(
        SyntheticSceneConfig(num_objects=7, num_frames=120, seed=4)
    )
    tracker = ByteTracker()
    acc = MotAccumulator(iou_threshold=0.5)

    renders: list[FrameRender] = []
    trajectories: dict[int, list] = {}

    for frame in scene:
        observations = tracker.update(frame.detections)
        hyp_ids = [o.track_id for o in observations]
        hyp_boxes = [o.xyxy for o in observations]

        acc.update(frame.gt_ids, frame.gt_boxes, hyp_ids, hyp_boxes)
        renders.append(
            FrameRender(frame.index, hyp_ids, hyp_boxes or [], frame.gt_boxes)
        )
        for o in observations:
            trajectories.setdefault(o.track_id, []).append(o.xyxy)

    print(acc.result())

    save_trajectory_plot(
        os.path.join(HERE, "trajectories.png"),
        trajectories,
        scene.cfg.width,
        scene.cfg.height,
    )
    animate_scene(
        os.path.join(HERE, "tracking.gif"),
        renders,
        scene.cfg.width,
        scene.cfg.height,
        fps=12,
    )
    print("wrote trajectories.png and tracking.gif")


if __name__ == "__main__":
    main()
