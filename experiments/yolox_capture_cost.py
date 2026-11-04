"""Generated YOLOX decode/capture cost and prefix-coverage probe (not inference).

Run with --output NEW_DIRECTORY outside the checkout. Each case runs in a fresh
process; timed modes rotate order, and allocation/serialization are separate.
No model, image, labels, tracker tuning or accuracy claim is involved.
"""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CASES = ("sparse_416", "clustered_640", "reversed_640", "disjoint_640")


def fixture(case: str):
    """Authored, deterministic tensors; not a model's empirical distribution."""
    import numpy as np

    if case not in CASES:
        raise ValueError(f"unknown case: {case}")
    size = 416 if case == "sparse_416" else 640
    rng = np.random.default_rng(20261104)
    grids, strata = [], []
    for stride in (8, 16, 32):
        x, y = np.meshgrid(np.arange(size // stride), np.arange(size // stride))
        grids.append((np.stack((x, y), axis=-1).reshape(-1, 2) + .5) * stride)
        strata.extend([stride] * x.size)
    anchors = np.concatenate(grids)
    strata = np.asarray(strata)
    raw = np.zeros((len(anchors), 85), dtype=np.float32)
    raw[:, :2], raw[:, 2:4], raw[:, 4], raw[:, 5] = anchors, (2, 2), 1, .01
    if case in ("clustered_640", "reversed_640"):
        # Six nearest anchors from each stride, per target: 18 proposals/group.
        for group, (x, y) in enumerate((
            (120, 120), (320, 120), (520, 120), (120, 320),
            (520, 320), (120, 520), (320, 520), (520, 520),
        )):
            ids = np.concatenate([
                np.flatnonzero(strata == stride)[np.argsort(
                    ((anchors[strata == stride] - (x, y)) ** 2).sum(axis=1), kind="stable",
                )[:6]] for stride in (8, 16, 32)
            ])
            raw[ids, :2] = (x, y) + rng.uniform(-2, 2, (len(ids), 2))
            raw[ids, 2:4] = (32, 48)
            raw[ids, 5:] = 0
            # Unique scores, one winner/class per group; no score-tie ambiguity.
            raw[ids, 5 + group % 2] = .6 + (group * 18 + np.arange(18)) / 500
    else:
        count = 64 if size == 416 else 256
        ids = rng.choice(len(raw), count, replace=False)
        raw[ids, 5] = np.linspace(.6, .95, count)
    if case == "reversed_640":
        raw, strata, anchors = raw[::-1].copy(), strata[::-1].copy(), anchors[::-1].copy()
    quadrants = (anchors[:, 0] >= size / 2).astype(int) + 2 * (
        anchors[:, 1] >= size / 2).astype(int)
    return raw[None], strata, quadrants, size


def detection_hash(detections) -> str:
    rows = [dict(xyxy=d.xyxy.tolist(), score=d.score, class_id=d.class_id) for d in detections]
    return hashlib.sha256(encoded(rows)).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def coverage(capture, full, strides, quadrants) -> dict:
    """Denominators come from full capture, including wholly absent groups."""
    winners = [r for r in full.records if r.status == "returned"]
    eligible = [r for r in full.records if r.status != "confidence_filtered"]
    retained = {r.proposal_index: r for r in capture.records}
    multi = [r for r in winners if r.group_size >= 2]
    complete_multi = sum(r.proposal_index in retained and
                         retained[r.proposal_index].group_complete for r in multi)
    by_stratum = {}
    for name, labels in (("anchor_stride", strides), ("anchor_quadrant", quadrants)):
        by_stratum[name] = {
            str(label): dict(
                total_rows=int((labels == label).sum()),
                retained_rows=sum(labels[i] == label for i in retained),
                eligible_rows=sum(labels[r.proposal_index] == label for r in eligible),
                retained_eligible_rows=sum(labels[r.proposal_index] == label and
                                           r.proposal_index in retained for r in eligible),
            ) for label in sorted(set(labels.tolist()))
        }
    # Convert NumPy scalar counts to plain integers for strict JSON.
    by_stratum = {name: {label: {key: int(v) for key, v in row.items()}
                        for label, row in table.items()} for name, table in by_stratum.items()}
    return dict(
        eligible_rows=len(eligible),
        retained_eligible_rows=sum(r.proposal_index in retained for r in eligible),
        returned_winners=len(winners),
        retained_returned_winners=sum(r.proposal_index in retained for r in winners),
        multi_proposal_returned_groups=len(multi),
        complete_multi_proposal_returned_groups=complete_multi,
        singleton_returned_groups=sum(r.group_size == 1 for r in winners),
        strata=by_stratum,
    )


def summarize_ns(samples) -> dict:
    ordered = sorted(samples)
    return dict(samples_ns=samples, median_ns=ordered[len(ordered) // 2],
                min_ns=ordered[0], max_ns=ordered[-1])


def worker(case: str, repeats: int) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    import visiontrack
    from visiontrack.detection.yolox_onnx import YoloxDetector

    if Path(visiontrack.__file__).resolve() != ROOT / "src/visiontrack/__init__.py":
        raise ValueError("measurement must use checkout sources")
    paths = [Path(__file__).resolve(), *(ROOT / "src/visiontrack").rglob("*.py")]

    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(paths)}

    sources = hashes()
    raw, strides, quadrants, size = fixture(case)
    input_hash = hashlib.sha256(raw.tobytes()).hexdigest()
    # No session is executed: this deliberately excludes inference/preprocessing.
    session = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="unused")])
    detector = YoloxDetector("unused", input_size=size, class_filter={0}, session=session)
    return _measure(detector, raw, strides, quadrants, repeats, sources, hashes, input_hash)


def _measure(detector, raw, strides, quadrants, repeats, sources, hashes, input_hash):
    import numpy as np

    modes = {"ordinary": None, "counts_only": 0, "prefix_256": 256, "default_4096": 4096}
    if raw.shape[1] > 4096:
        modes["full"] = raw.shape[1]

    def decode(limit):
        return detector._decode_frame(raw, 1., limit)

    expected, full = decode(raw.shape[1])
    expected_hash = detection_hash(expected)
    del expected
    # Warm dispatch and allocators for every mode, outside the samples.
    for limit in modes.values():
        decode(limit)
    samples = {mode: [] for mode in modes}
    names = list(modes)
    for repeat in range(repeats):
        # Rotate which mode goes first; retain individual samples, not an FPS claim.
        for name in names[repeat % len(names):] + names[:repeat % len(names)]:
            started = time.perf_counter_ns()
            result = decode(modes[name])
            samples[name].append(time.perf_counter_ns() - started)
            del result
    measured = {}
    for name, limit in modes.items():
        gc.collect()
        tracemalloc.start()
        detections, capture = decode(limit)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if detection_hash(detections) != expected_hash:
            raise ValueError("capture changed returned detections")
        row = dict(limit=limit, decode=summarize_ns(samples[name]),
                   decode_traced_current_bytes=current, decode_traced_peak_bytes=peak,
                   output_sha256=expected_hash, returned_detections=len(detections))
        if capture is not None:
            serial_samples = []
            for _ in range(repeats):
                started = time.perf_counter_ns()
                payload = encoded(capture.to_dict())
                serial_samples.append(time.perf_counter_ns() - started)
                del payload
            gc.collect()
            tracemalloc.start()
            payload = encoded(capture.to_dict())
            _, serial_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            row.update(
                retained_rows=len(capture.records), truncated=capture.truncated,
                omitted_rows=capture.omitted_count, json_bytes=len(payload),
                gzip_bytes=len(gzip.compress(payload, mtime=0)),
                serialization=summarize_ns(serial_samples),
                serialization_traced_peak_bytes=serial_peak,
                coverage=coverage(capture, full, strides, quadrants),
            )
            del payload
        measured[name] = row
        del detections, capture
    if input_hash != hashlib.sha256(raw.tobytes()).hexdigest() or hashes() != sources:
        raise ValueError("input or sources changed during measurement")
    return dict(
        python=platform.python_version(), numpy=np.__version__, platform=platform.platform(),
        raw_shape=list(raw.shape), raw_dtype=str(raw.dtype), input_sha256=input_hash,
        input_size=detector.input_size, scale=1., conf_threshold=detector.conf_threshold,
        iou_threshold=detector.iou_threshold, class_filter=[0], repeats=repeats,
        source_sha256=sources, modes=measured,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 3 <= args.repeats <= 31 or args.repeats % 2 == 0:
        parser.error("repeats must be odd, between 3 and 31")
    if args.worker:
        args.output.write_bytes(encoded(worker(args.worker, args.repeats)) + b"\n")
        return
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("keep measurement outputs outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    cases = {}
    for case in CASES:
        path = output / f"{case}.json"
        subprocess.run([
            sys.executable, "-I", str(Path(__file__).resolve()), "--worker", case,
            "--repeats", str(args.repeats), "--output", str(path),
        ], check=True, cwd=output, timeout=300)
        cases[case] = json.loads(path.read_bytes())
        print(f"Measured {case}", flush=True)
    reference = cases[CASES[0]]
    for case in cases.values():
        for field in ("python", "numpy", "platform", "source_sha256"):
            if case[field] != reference[field]:
                raise ValueError(f"case runtimes or sources differ: {field}")
    if (cases["clustered_640"]["modes"]["ordinary"]["output_sha256"] !=
            cases["reversed_640"]["modes"]["ordinary"]["output_sha256"]):
        raise ValueError("row-order control changed detections")
    result = dict(
        schema="visiontrack.yolox-capture-cost/v1", cases=cases,
        synthetic_only=True, inference_measured=False, accuracy_claim=False,
        timings_include_tracemalloc=False, memory_is_not_process_rss=True,
        scope="decode only, single frame retained; separate to_dict/JSON allocation peak",
    )
    (output / "comparison.json").write_bytes(encoded(result) + b"\n")
    print(f"Exact detections agree. Receipt: {output / 'comparison.json'}")


if __name__ == "__main__":
    main()
