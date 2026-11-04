"""Measure opt-in history retention on one continuously matched generated object.

Independent subprocesses, streaming output hashes and no saved trajectories.
Python tracemalloc is not process RSS; this is not an accuracy/speed benchmark.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import struct
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def worker(output: Path, mode: str, frames: int) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np

    from visiontrack import ByteTracker, Detection

    source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / "src" / "visiontrack").rglob("*.py"))}
    # Warm imports/BLAS dispatch before either retention policy is measured.
    warm = ByteTracker()
    for _ in range(10):
        warm.update([Detection([10., 20., 30., 60.], .9, 1)])
    del warm
    gc.collect()
    digest = hashlib.sha256()
    count = 0
    tracemalloc.start()
    started = time.perf_counter()
    tracker = ByteTracker(history_limit=None if mode == "full" else 6)
    for _ in range(frames):
        for obs in tracker.update([Detection([10., 20., 30., 60.], .9, 1)]):
            digest.update(struct.pack("<qqdi", obs.frame, obs.track_id, obs.score, obs.class_id))
            digest.update(np.asarray(obs.xyxy, dtype="<f8").tobytes())
            count += 1
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if len(tracker.tracks) != 1 or count != frames - 2:
        raise ValueError("probe did not retain one continuously matched confirmed object")
    track = tracker.tracks[0]
    expected = frames if mode == "full" else min(6, frames)
    if len(track.history) != expected:
        raise ValueError("unexpected history retention")
    after = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT / "src" / "visiontrack").rglob("*.py"))}
    if after != source:
        raise ValueError("source changed during measurement")
    receipt = dict(
        mode=mode, frames=frames, python=platform.python_version(), numpy=np.__version__,
        platform=platform.platform(),
        module=str(Path(sys.modules["visiontrack"].__file__).resolve()),
        history_limit=tracker.history_limit, retained_boxes=len(track.history),
        history_list_shallow_bytes=sys.getsizeof(track.history),
        retained_box_payload_bytes=sum(box.nbytes for box in track.history),
        traced_current_bytes=current, traced_peak_bytes=peak,
        elapsed_with_tracemalloc_seconds=elapsed, observations=count,
        output_sha256=digest.hexdigest(), source_sha256=source,
        synthetic_only=True, accuracy_claim=False, memory_is_not_process_rss=True,
    )
    (output / f"{mode}-{frames}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"{mode} {frames}: history={len(track.history)}, peak={peak} bytes", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--worker", choices=("full", "bounded"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (not 1 <= len(args.frames) <= 4 or len(set(args.frames)) != len(args.frames)
            or any(not 10 <= n <= 100_000 for n in args.frames)):
        parser.error("choose 1–4 distinct frame counts between 10 and 100000")
    if args.worker:
        if len(args.frames) != 1:
            parser.error("worker needs one size")
        worker(args.output, args.worker, args.frames[0])
        return
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("keep measurement outputs outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    comparisons = []
    for frames in args.frames:
        for mode in ("full", "bounded"):
            subprocess.run([
                sys.executable, "-I", str(Path(__file__).resolve()), "--worker", mode,
                "--output", str(output), "--frames", str(frames),
            ], check=True, cwd=output, timeout=600)
        full = json.loads((output / f"full-{frames}.json").read_text())
        bounded = json.loads((output / f"bounded-{frames}.json").read_text())
        for field in ("python", "numpy", "platform", "source_sha256", "output_sha256",
                      "observations"):
            if full[field] != bounded[field]:
                raise ValueError(f"policy comparison differs in {field}")
        comparisons.append(dict(
            frames=frames, full_peak_bytes=full["traced_peak_bytes"],
            bounded_peak_bytes=bounded["traced_peak_bytes"],
            full_retained_boxes=full["retained_boxes"],
            bounded_retained_boxes=bounded["retained_boxes"],
            output_sha256=full["output_sha256"], observations=full["observations"],
        ))
    (output / "comparison.json").write_text(json.dumps(comparisons, indent=2) + "\n")
    print(f"Exact output hashes agree. Receipt: {output / 'comparison.json'}")


if __name__ == "__main__":
    main()
