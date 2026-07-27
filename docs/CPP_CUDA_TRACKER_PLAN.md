# Side plan — an optimized C++/CUDA ByteTrack (sibling project)

**Not a VisionTrack horizon.** This is a separate *performance-engineering*
project whose goal is throughput, not new research findings. It deliberately
lives outside this repo (a sibling `visiontrack-cpp`), because merging a C++/CUDA
core would break VisionTrack's "NumPy-only core" identity — the very thing that
makes the from-scratch claim legible.

## Why do it

The NumPy tracker is a *reference* implementation: correct and readable, ~200–2300
FPS on CPU. This project answers a different, interesting question: **how fast can
an honest ByteTrack go**, and what does the optimization actually buy? It's a
strong standalone portfolio piece (systems + GPU skills) and pairs naturally with
the study: *"here is the correct tracker, and here is the fast one, proven
identical."*

## The correctness gate (non-negotiable)

The C++/CUDA tracker must produce metrics **within tolerance of the NumPy
reference** on the same cached MOT17/DanceTrack detections. Parity first, speed
second — a faster tracker that changes the numbers is worthless here. The NumPy
core is the oracle.

## Architecture

```
visiontrack-cpp/
  core/        header-only C++: geometry (IoU/GIoU), Kalman (Eigen), assignment
  bind/        pybind11 module -> import visiontrack_cpp
  bench/       FPS vs #tracks, speedup table, parity report vs NumPy
  cuda/        optional GPU kernels (batched IoU/cost, Kalman GEMM)
```

- **Linear algebra:** Eigen (header-only) for the Kalman filter.
- **Bindings:** pybind11, so the same Python eval/HOTA harness scores the C++
  tracker — reusing this repo's `eval/` as the correctness oracle.

## Phases

1. **C++ reference port.** Port IoU/GIoU, the 8-state Kalman filter, the Hungarian
   solver, and the two-stage ByteTrack loop to C++. Gate: metrics match the NumPy
   reference on MOT17-09 within tolerance (reuse the existing caches + `eval/`).
2. **CPU optimization.** SIMD IoU/cost-matrix (ARM **NEON** on the M2, AVX on
   x86), batched Kalman predict, a fast assignment (LAPJV instead of the teaching
   O(n³) Hungarian), cache-friendly memory layout. Deliverable: a profiled
   speedup table + an FPS-vs-#tracks figure, all still parity-correct.
3. **GPU path (stretch).** Batched IoU/cost-matrix and Kalman predict as batched
   GEMM on the GPU; keep assignment on the CPU (Hungarian is irregular and small)
   or try a GPU auction algorithm. Measure the crossover point where GPU wins
   (large #tracks).
4. **Package + benchmark.** Publish `visiontrack-cpp`, a reproducible benchmark
   vs the NumPy core on identical detections, and a one-figure "correct == fast"
   parity + speedup story.

## The hardware caveat (read before starting)

The dev machine is a **MacBook M2 — no NVIDIA GPU, no CUDA**. So:
- **Phases 1–2 (C++ + NEON SIMD) are fully local** and are where most of the real
  speedup lives (IoU/cost-matrix + memory layout dominate, not the GPU).
- **Phase 3 CUDA needs a cloud GPU** (Colab / a rented instance) to build and
  test — it cannot be developed on the M2. An **Apple-GPU alternative** is Metal
  Performance Shaders, which *is* local, if the goal is "use the GPU I have"
  rather than "CUDA specifically".

**Recommendation:** start with Phases 1–2 (locally verifiable, most of the win),
and treat CUDA as an explicit cloud-GPU stretch or swap it for a Metal path.

## Honest expectations

The headline won't be "beats SOTA" — it'll be "an honest, parity-verified
ByteTrack at N× the throughput of the reference, with the speedup attributed to
specific optimizations." That attribution *is* the portfolio value.
