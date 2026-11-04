"""Compare checkout diagnostic memory with an isolated published baseline.

Synthetic fixed boxes only; no camera, dataset, inference or accuracy result.
Run with --baseline-python PATH --output NEW_DIRECTORY. The receipt retains
both producers, exact semantic hashes, Python allocation peaks and traced times.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def worker(output: Path, mode: str, sizes: list[int], baseline_version: str) -> None:
    if mode == "checkout":
        sys.path.insert(0, str(ROOT / "src"))
    import numpy as np

    import visiontrack
    from visiontrack.lab import (
        DetectionRecord,
        ExperimentManifest,
        GroundTruthRecord,
        SourceManifest,
        build_association_explanation,
        build_initiation_trace,
        canonical_json,
        create_experiment_bundle,
        detection_payload_sha256,
        ground_truth_payload_sha256,
        run_comparison,
    )

    module = Path(visiontrack.__file__).resolve()
    if mode == "baseline":
        if (visiontrack.__version__ != baseline_version
                or not module.is_relative_to(Path(sys.prefix))):
            raise ValueError(
                f"baseline must be a non-editable published {baseline_version} install"
            )
    elif not module.is_relative_to(ROOT / "src"):
        raise ValueError("checkout worker did not import the repository source")
    results = []
    for size in sizes:
        if mode == "baseline":
            records = [DetectionRecord(i, None, key, (10., 10., 30., 50.), score, 1)
                       for i in range(size) for key, score in ((7, .9), (91, .05))]
            truth = [GroundTruthRecord(i, None, 1, (10., 10., 30., 50.), 1, 1., False)
                     for i in range(size)]
            source = SourceManifest.create(
                kind="synthetic", name=f"streaming development probe {size}",
                detection_sha256=detection_payload_sha256(records, frame_count=size),
                ground_truth_sha256=ground_truth_payload_sha256(truth, frame_count=size),
                video_sha256=None, detector={"name": "hand-authored fixed boxes"},
                frame_count=size, width=100, height=80, fps=30., coordinate_space="pixel_xyxy",
                created_at="2026-11-01T00:00:00Z",
            )
            experiment = ExperimentManifest.create(
                source_id=source.source_id, baseline="baseline", variants=({"name": "baseline"},),
                metrics=("track_count",), frame_range={"start": 0, "end": size},
                visiontrack_version=baseline_version, git_revision=None,
                environment={"python": "fixed synthetic fixture"},
                created_at="2026-11-01T00:00:00Z",
            )
            bundle = create_experiment_bundle(
                output / f"bundle-{size}", experiment, source, records, truth,
            )
            run_comparison(bundle)
            (output / f"path-{size}.txt").write_text(str(bundle), encoding="utf-8")
            del records, truth, source, experiment
        else:
            bundle = Path((output / f"path-{size}.txt").read_text(encoding="utf-8"))
        before = snapshot(bundle)
        for kind in ("initiation", "association"):
            gc.collect()
            tracemalloc.start()
            started = time.perf_counter()
            try:
                if kind == "initiation":
                    value = build_initiation_trace(
                        bundle, variant="baseline", start=size - 2, end=size,
                    )
                else:
                    value = build_association_explanation(
                        bundle, variant="baseline", frame=size - 1, track_id=1, detection_index=7,
                    )
                elapsed = time.perf_counter() - started
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            identity = value.pop("trace_id" if kind == "initiation" else "explanation_id")
            producer = value.pop("producer")
            semantic = canonical_json(value) + "\n"
            (output / f"{mode}-{size}-{kind}.json").write_text(semantic, encoding="utf-8")
            if mode == "checkout" and semantic != (
                output / f"baseline-{size}-{kind}.json"
            ).read_text(encoding="utf-8"):
                raise ValueError("diagnostic content changed beyond producer and content ID")
            results.append(dict(
                frames=size, kind=kind, peak_traced_bytes=peak,
                elapsed_with_tracemalloc_seconds=elapsed,
                semantic_sha256=hashlib.sha256(semantic.encode()).hexdigest(),
                diagnostic_id=identity, producer=producer,
            ))
            print(f"{mode} {kind} {size}: peak={peak} bytes, traced time={elapsed:.3f}s",
                  flush=True)
            del value, producer
        if snapshot(bundle) != before:
            raise ValueError("read-only diagnosis changed its input bundle")
    receipt = dict(mode=mode, python=platform.python_version(), numpy=np.__version__,
                   visiontrack=visiontrack.__version__, module=str(module), results=results,
                   inputs_unchanged=True, synthetic_only=True, accuracy_claim=False,
                   peak_is_python_tracemalloc_not_total_rss=True)
    (output / f"{mode}-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                               encoding="utf-8")


def snapshot(bundle: Path) -> dict[str, str]:
    return {p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in bundle.rglob("*") if p.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-python", type=Path)
    parser.add_argument("--baseline-version", choices=("0.5.0", "0.5.1"), default="0.5.0")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, nargs="+", default=[600, 6000])
    parser.add_argument("--worker", choices=("baseline", "checkout"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (len(args.frames) > 4 or len(set(args.frames)) != len(args.frames)
            or any(not 10 <= size <= 100_000 for size in args.frames)):
        parser.error("choose 1–4 distinct frame counts between 10 and 100000")
    if args.worker:
        worker(args.output, args.worker, args.frames, args.baseline_version)
        return
    if args.baseline_python is None:
        parser.error("--baseline-python is required")
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("keep measurement outputs outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    interpreters = (("baseline", args.baseline_python.resolve()), ("checkout", sys.executable))
    for mode, python in interpreters:
        subprocess.run([
            str(python), "-I", str(Path(__file__).resolve()), "--worker", mode,
            "--output", str(output), "--frames", *map(str, args.frames),
            "--baseline-version", args.baseline_version,
        ], check=True, cwd=output, timeout=600)
    old = json.loads((output / "baseline-receipt.json").read_text())
    new = json.loads((output / "checkout-receipt.json").read_text())
    if (old["python"], old["numpy"]) != (new["python"], new["numpy"]):
        raise ValueError("Python and NumPy versions differ; do not attribute memory to streaming")
    comparison = [{
        "frames": left["frames"], "kind": left["kind"],
        "baseline_peak_bytes": left["peak_traced_bytes"],
        "checkout_peak_bytes": right["peak_traced_bytes"],
        "reduction_fraction": 1 - right["peak_traced_bytes"] / left["peak_traced_bytes"],
        "semantic_sha256": left["semantic_sha256"],
    } for left, right in zip(old["results"], new["results"], strict=True)]
    (output / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n",
                                           encoding="utf-8")
    print(f"Exact diagnostic content agrees. Local receipt: {output / 'comparison.json'}")


if __name__ == "__main__":
    main()
