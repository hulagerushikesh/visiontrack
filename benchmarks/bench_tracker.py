"""Throughput and accuracy benchmark for the tracker.

Reports frames-per-second and the average object count, plus MOT accuracy, so
performance regressions and accuracy regressions are both visible.

    PYTHONPATH=src python benchmarks/bench_tracker.py
"""
from __future__ import annotations

import statistics
import time

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig
from visiontrack.eval.mot import MotAccumulator
from visiontrack.tracking.tracker import ByteTracker


def bench(num_objects: int, num_frames: int, seed: int = 0) -> dict:
    # Pre-generate frames so we time the tracker, not the scene simulator.
    scene = SyntheticScene(
        SyntheticSceneConfig(num_objects=num_objects, num_frames=num_frames, seed=seed)
    )
    frames = scene.frames()
    det_counts = [len(f.detections) for f in frames]

    tracker = ByteTracker()
    acc = MotAccumulator(iou_threshold=0.5)

    per_frame_ms = []
    for f in frames:
        t0 = time.perf_counter()
        obs = tracker.update(f.detections)
        per_frame_ms.append((time.perf_counter() - t0) * 1e3)
        acc.update(f.gt_ids, f.gt_boxes, [o.track_id for o in obs], [o.xyxy for o in obs])

    m = acc.result()
    return {
        "objects": num_objects,
        "frames": num_frames,
        "avg_dets": statistics.mean(det_counts),
        "mean_ms": statistics.mean(per_frame_ms),
        "p95_ms": sorted(per_frame_ms)[int(0.95 * len(per_frame_ms)) - 1],
        "fps": 1000.0 / statistics.mean(per_frame_ms),
        "mota": m.mota,
        "idsw": m.id_switches,
    }


def main() -> None:
    print(
        f"{'objects':>8} {'avg_dets':>9} {'mean_ms':>8} {'p95_ms':>8} "
        f"{'fps':>8} {'MOTA':>7} {'IDSW':>6}"
    )
    print("-" * 60)
    for n in (4, 8, 16, 32, 64):
        r = bench(n, num_frames=200)
        print(
            f"{r['objects']:>8} {r['avg_dets']:>9.1f} {r['mean_ms']:>8.3f} "
            f"{r['p95_ms']:>8.3f} {r['fps']:>8.0f} {r['mota']:>7.3f} {r['idsw']:>6}"
        )


if __name__ == "__main__":
    main()
