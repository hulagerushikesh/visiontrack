# Detector diagnostics: measured cost and research limits

Checkpoint **2026-11-04**. The [capture API](YOLOX_PROPOSAL_CAPTURE.md) now has
a reproducible generated-input cost/coverage probe and two bookkeeping
optimizations. This is checkout engineering, not a new PyPI release, model
benchmark, traffic result or tracking-accuracy improvement.

## What was measured

Four fixed, authored float32 tensors have 80 class columns and standard
416/640 input-grid row counts: 3,549 and 8,400. Cases contain 64 separated
eligible boxes, eight clusters of 18 proposals, the same clusters in reversed
row order, and 256 separated eligible boxes. Only class 0 is returned; mixed
classes exercise the existing post-suppression class filter.

Each case runs in a fresh process. Nine timed decode samples rotate mode order
after warm-up. Modes are ordinary decoding, counts-only, 256-row prefix, default
4,096-row prefix and full capture where the default truncates. Separate runs
measure allocation while retaining one result and serialization including
`to_dict`, compact sorted JSON and UTF-8 encoding. Gzip size is measured
separately; compression time is **not** part of the serialization timings.

Environment: CPython 3.12.9, NumPy 2.3.1, macOS 27 ARM64. No ONNX inference,
preprocessing, video, ground truth, tracker update, disk/network write throughput
or sustained multi-frame performance is measured. The input and full-capture
coverage reference are allocated before tracing. Python-traced allocations are
not process RSS. These workloads do not estimate real model-output frequency.

## Findings

Post-optimization medians on the generated **640 clustered** case:

| Mode | Decode ms | JSON serialization ms | JSON bytes | Gzip bytes | Retained traced allocation, including detections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary | 1.77 | — | — | — | 11,840 B |
| Counts only | 1.57 | 0.009 | 586 | 341 | 12,604 B |
| Prefix 256 | 2.20 | 1.43 | 74,961 | 2,697 | 107,004 B |
| Default 4,096 | 12.06 | 22.79 | 1,205,285 | 33,807 | 1,643,260 B |
| Full 8,400 | 23.76 | 47.45 | 2,476,823 | 73,380 | 3,364,956 B |

Small differences between ordinary and counts-only medians are measurement
variation, not evidence that adding capture accelerates ordinary decoding.
The decoder's shared temporary arrays dominate the 11,156,056 B traced peak in
this case; an unchanged peak does not imply free capture storage. Full-capture
JSON serialization has its own 9,791,416 B traced peak and is measured separately.
Do not add these non-concurrent peaks or describe either as a total-memory bound.

The full clustered record is about **2.48 MB per frame** before compression.
Even a hypothetical 100-frame saved sample would be about 248 MB of this JSON,
excluding images and filesystem overhead. This is storage arithmetic, not a
claim that a model can process those frames at any particular rate. Keep capture
opt-in; do not silently save every frame or recommend the full format for
continuous production logging.

### Prefix coverage is a separate limitation

Both clustered cases return the same four class-0 detections, byte-equivalent
in value/order. With a 4,096-row prefix:

| Row order | Eligible rows retained / all | Returned winners retained / all | Complete multi-proposal returned groups / all |
| --- | ---: | ---: | ---: |
| Grid order | 30 / 144 | 0 / 4 | 0 / 4 |
| Reversed control | 114 / 144 | 4 / 4 | 1 / 4 |
| Full capture, either order | 144 / 144 | 4 / 4 | 4 / 4 |

The original prefix contains only stride-8 rows, omitting every stride-16/32
row. Reversing rows is an authored control, not an alternative export claim.
It demonstrates dependence on row order, not the prevalence of this failure in
real models. A kept winner alone is insufficient: its suppressed members may
still be missing. Singleton groups are counted separately, never as zero-error
or zero-uncertainty evidence.

## Optimization and exact-behavior checks

Counts-only capture now skips record membership bookkeeping. With records,
membership indexes only actual suppression victims instead of scanning every
remaining candidate in Python. JSON conversion no longer recursively copies all
records twice. Ordinary decoder/NMS behavior, record order, metadata and the
prefix-selection policy remain unchanged.

For the generated 256-separated-box case, counts-only median decode falls from
14.15 to 10.46 ms (26% in this local run); ordinary decode is 10.15 ms in both
runs. Default-prefix JSON conversion falls from 35.40 to 23.76 ms. These are
bounded local measurements, not general speed guarantees. Full capture remains
costly; the optimizations do not solve prefix coverage or change its API default.

All 19 case/mode detection outputs, record sizes and coverage totals agree
before/after. Sixteen independent previous-commit/current capture comparisons
also match the complete serialized JSON bytes. A separate pre-capture-decoder
replay checks 800 detection comparisons and 800 downstream tracker updates
exactly. Tests cover missing groups, order dependence, filtered classes,
non-finite overlap semantics and detached serialization without timing thresholds.

The [compact measurement receipt](https://github.com/hulagerushikesh/visiontrack/blob/main/experiments/yolox_capture_cost_v1_result.json)
pins input hashes, executable/package hashes, runtime, medians, allocation and
coverage values. Full local receipts retain every timing sample. To rerun:

```bash
python -m experiments.yolox_capture_cost --output /new/path/capture-cost --repeats 9
pytest -q tests/test_yolox_capture_cost.py tests/test_yolox_proposals.py
```

The subprocess explicitly imports this checkout's `src`; it refuses changed
sources/inputs and mismatched runtime/source identities across cases. Existing
output directories are refused. A failed run is not a completed comparison.

## Next decision

Use full capture on a small, fixed offline frame set for the
[localization-signal audit design](LOCALIZATION_SIGNAL_AUDIT.md); report all
unsupported/missing groups and stream derived features rather than accumulating
full captures. No proposal signal enters association until it adds useful
information beyond score/class/size on independent checked data. Bath blocks
only the RoundaboutHD intake; generated arithmetic/tooling work can continue.
