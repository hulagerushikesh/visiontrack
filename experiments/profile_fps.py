"""Profile the tracker's throughput — is it real-time, and where does time go?

The tracker (association + Kalman + lifecycle) is the part this project owns;
detection is a swappable ONNX model. So we measure the **tracker update** FPS on
CPU as a function of scene load (number of objects), which answers "can the
from-scratch tracker keep up with a real-time detector?" honestly, without a GPU.

Detections come from the synthetic generator (cached per scene, excluded from the
timed region), so the numbers isolate tracking, not detection or I/O.

    python -m experiments.profile_fps
    python -m experiments.profile_fps --objects 5,15,30,60 --frames 200
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from visiontrack.detection.synthetic import SyntheticScene, SyntheticSceneConfig  # noqa: E402
from visiontrack.tracking.config import TrackerConfig  # noqa: E402
from visiontrack.tracking.tracker import ByteTracker  # noqa: E402


def profile_load(num_objects: int, num_frames: int, config: TrackerConfig | None = None,
                 warmup: int = 5) -> dict:
    """Return timing stats for tracking a scene of ``num_objects`` objects.

    Detections are materialised up front (outside the timed loop); only
    ``tracker.update`` is timed. Reports mean/median/p95 ms per frame and FPS.
    """
    scene = SyntheticScene(SyntheticSceneConfig(
        num_objects=num_objects, num_frames=num_frames + warmup, seed=0))
    frame_dets = [f.detections for f in scene]  # precompute, exclude from timing

    tracker = ByteTracker(config or TrackerConfig())
    per_frame_ms: list[float] = []
    for i, dets in enumerate(frame_dets):
        t0 = time.perf_counter()
        tracker.update(dets)
        dt = (time.perf_counter() - t0) * 1e3
        if i >= warmup:  # skip warm-up frames (JIT-free but caches/branch warmup)
            per_frame_ms.append(dt)

    arr = sorted(per_frame_ms)
    n = len(arr)
    mean = sum(arr) / n
    median = arr[n // 2]
    p95 = arr[min(n - 1, int(0.95 * n))]
    return {
        "objects": num_objects,
        "mean_ms": mean,
        "median_ms": median,
        "p95_ms": p95,
        "fps": 1000.0 / mean if mean > 0 else float("inf"),
    }


def report(rows: list[dict]) -> str:
    lines = ["# Tracker throughput (CPU, update() only, detection excluded)", ""]
    lines.append("| objects | mean ms | median ms | p95 ms | FPS |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['objects']} | {r['mean_ms']:.3f} | {r['median_ms']:.3f} | "
                     f"{r['p95_ms']:.3f} | {r['fps']:.0f} |")
    lines.append("")
    lines.append("FPS is the tracker's own rate; end-to-end throughput is "
                 "min(this, detector FPS). Real-time (>30 FPS) headroom means the "
                 "tracker is never the bottleneck at these loads.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile tracker throughput")
    parser.add_argument("--objects", default="5,15,30,60",
                        help="comma-separated object counts to sweep")
    parser.add_argument("--frames", type=int, default=150, help="timed frames per load")
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args(argv)

    loads = [int(x) for x in args.objects.split(",")]
    rows = [profile_load(k, args.frames) for k in loads]
    text = report(rows)
    print(text)
    if args.out_md:
        Path(args.out_md).write_text(text + "\n")
        print(f"\nwrote report -> {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
