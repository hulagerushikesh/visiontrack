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

---

# Phase 1 — execution plan

Phase 1 is the **C++ reference port**: same algorithm, same numbers, no
optimization. It exists to buy the right to optimize in Phase 2 — once a
parity harness exists, every later speedup is provably behaviour-preserving.
Optimizing first and checking later is how you ship a fast tracker that is
quietly wrong.

## Does it need a separate repo? Yes — and the coupling is now clean

Separate repo, `visiontrack-cpp`. Two reasons, one of which only became true
with v0.2.0:

1. **Identity.** VisionTrack's whole claim is a from-scratch tracker whose core
   is readable NumPy. A C++/CUDA core inside `src/visiontrack/` destroys that
   claim — a reader can no longer tell which implementation produced a number,
   and the repo acquires a compiler toolchain, a CMake build, platform wheels
   and a cross-compilation CI matrix that the reference implementation does not
   need.
2. **The oracle is now installable.** `visiontrack-mot` is on PyPI. The sibling
   repo can therefore depend on the reference the same way any third party
   would — `pip install visiontrack-mot==0.2.0` — instead of reaching across a
   sibling directory. The correctness oracle becomes a *pinned, versioned
   dependency*, which is exactly what an oracle should be. Before v0.2.0 this
   would have required a path dependency and the split would have been messier.

So the dependency runs one way and never back:

```
visiontrack (this repo)          visiontrack-cpp (sibling)
  NumPy reference        <-----    pip install visiontrack-mot==0.2.0
  eval/ + HOTA harness   <-----    imported as the scoring oracle
  data/cache/*.npz       <-----    read via $VISIONTRACK_CACHE (never copied)
```

**This repo changes not at all.** No submodule, no optional extra, no build
flag. If the sibling project is abandoned, nothing here rots.

The caches are the one shared asset. They are gitignored, large, and
regenerable, so the sibling reads them by path from an environment variable
rather than vendoring a copy.

## Toolchain — verified present on this machine

Checked 2026-09-08, nothing left to install:

| need | found |
|---|---|
| compiler | Apple clang 17.0.0, target `arm64-apple-darwin24.6.0` |
| build | CMake 4.0.0 |
| linear algebra | Eigen at `/opt/homebrew/opt/eigen` |
| bindings | pybind11 3.1.0 |
| host | M2, arm64, 8 cores |

Phase 1 is CPU-light — it compiles and runs one sequence at a time. It does not
repeat the yolox-x mistake of a multi-hour unattended job.

## Port surface — what is in, what is deliberately out

**In (~1,438 LOC of NumPy):**

| module | LOC | what ports |
|---|---|---|
| `core/geometry.py` | 177 | `iou_matrix`, `giou_matrix`, box-format conversions, `box_area`, `clip_boxes` |
| `core/kalman.py` | 268 | 8-state filter: `initiate`, `predict`, `project`, `update`, `gating_distance{,_batch}`, the height-scaled process/measurement noise |
| `core/assignment.py` | 181 | `_kuhn_munkres` O(n³), `linear_assignment`, `associate` |
| `tracking/track.py` | 177 | `Track` + the Tentative→Confirmed→Deleted FSM |
| `tracking/tracker.py` | 359 | `ByteTracker.update`, the two-stage `_match`, `_predict_all`, `_apply_match`, `_spawn` |
| `tracking/cost.py` | 165 | `build_association_cost` and its four gated terms |
| `tracking/config.py` | 111 | `TrackerConfig` as a plain struct |

**Out of Phase 1, on purpose:**

- **Appearance embedding.** ONNX/OSNet inference stays in Python. The C++ side
  accepts a precomputed `(n, d)` feature array, so `appearance_distance` ports
  as pure arithmetic and no ONNX runtime enters the C++ build. This keeps the
  binding surface to plain float arrays.
- **GMC and the learned motion residual.** Both are research extensions whose
  findings are already published; both are gated off in `TrackerConfig`.
  Porting them multiplies the parity surface for no throughput gain.
- **Every optimization.** No SIMD, no LAPJV, no memory-layout work. Phase 1
  ships the *teaching* O(n³) Hungarian on purpose, because Phase 2's headline
  is "LAPJV replaced it and the numbers did not move".

## The parity gate

Metric-level agreement is too weak a gate. Association is **discrete**: a
1e-16 difference in one cost entry can flip one assignment, which changes an ID,
which cascades through every later frame — and yet MOTA may barely move. A
tracker can be visibly wrong while scoring within tolerance.

So the gate is trajectory-level, in three tiers:

1. **Unit parity.** Each ported function against its NumPy original on randomized
   inputs, including degenerate ones (empty matrices, zero-area boxes,
   single-row/column cost matrices, tall vs wide). `atol=1e-12` for geometry,
   `1e-9` for the Kalman path.
2. **Trajectory parity (the real gate).** Run both trackers over
   **MOT17-09** and require the emitted `(frame, track_id, box)` stream to be
   **identical** — same IDs, same order, boxes within `1e-9`. All three detector
   variants (`DPM`, `FRCNN`, `SDP`) are cached, giving three independent cost
   landscapes for the price of one harness.
3. **Metric parity.** Only as a backstop: reuse this repo's `eval/` so HOTA,
   IDF1 and CLEAR-MOT are computed by the *same* code for both trackers.

### The tie-break trap — the single biggest parity risk

When two assignments have equal cost, the Hungarian solver's *implementation*
picks the winner, not the mathematics. Both implementations minimize the same
sum; they can legitimately return different optima. Two places in
`assignment.py` must be replicated exactly rather than merely correctly:

- **The transpose.** `linear_assignment` transposes when `rows > cols` and swaps
  the result back. That changes which equal-cost optimum is returned, so the
  C++ port must transpose on the same condition, not on its own convention.
- **Iteration order inside `_kuhn_munkres`.** Column and row scan order decides
  ties. It must match index-for-index.

If tier 2 fails, the diagnosis is a frame-indexed diff of the first divergent
assignment — not a loosened tolerance. Loosening the tolerance here would
convert a real bug into a passing test, which is the specific failure this gate
exists to prevent.

## Deliverables

```
visiontrack-cpp/
  CMakeLists.txt
  core/       header-only: geometry.hpp, kalman.hpp (Eigen), assignment.hpp,
              track.hpp, tracker.hpp, cost.hpp, config.hpp
  bind/       pybind11 module -> import visiontrack_cpp
  tests/      unit parity + trajectory parity vs visiontrack-mot
  bench/      FPS vs #tracks (Phase 2 fills this in)
  README.md   the parity report
```

Phase 1 is done when: `import visiontrack_cpp` works from Python, and the
trajectory-parity suite passes on all three MOT17-09 variants.

## Milestones

Each is independently verifiable, so the work can stop cleanly at any point.

| # | milestone | gate |
|---|---|---|
| 1 | Repo scaffold, CMake + pybind11, a trivial bound function | `import visiontrack_cpp` succeeds |
| 2 | Geometry ported | unit parity vs `core/geometry.py` |
| 3 | Kalman ported (Eigen) | unit parity incl. `gating_distance_batch` |
| 4 | Hungarian ported | unit parity **and** identical output on tied-cost matrices |
| 5 | Track FSM + `ByteTracker.update` | trajectory parity on one MOT17-09 variant |
| 6 | Parity harness + report | trajectory parity on all three variants |

Milestone 4 is the risky one and should be attacked with adversarial tied-cost
matrices from the start, not discovered at milestone 5 as a mystery ID swap.

## Honest expectations

Phase 1 produces **no speedup** and is not supposed to. A naive C++ port of
vectorized NumPy is often *slower*, because NumPy's inner loops are already
compiled BLAS-adjacent code while a first-draft C++ port is scalar. The
deliverable is the parity harness; the speed story starts in Phase 2 and is only
credible because Phase 1 built the thing that can prove it.

---

## Phase 1 — outcome (2026-09-09)

Phase 1 is complete. All six milestones are done and the repo is at
[`hulagerushikesh/visiontrack-cpp`](https://github.com/hulagerushikesh/visiontrack-cpp).
This section records what the plan above got right and what it got wrong, since
a plan whose predictions are never checked is just a wish list.

### The gate passes

Both trackers produce **identical** `(frame, track_id, box, score)` streams over
the full 525 frames of MOT17-09, on all three detector variants — 7,545
observations, zero divergences. Boxes are compared bit-for-bit; the plan allowed
`1e-9`, but the port reaches equality, and a tolerance looser than the drift it
measures would absorb exactly what the gate exists to catch.

Tier 3 agrees too: HOTA, IDF1 and CLEAR-MOT computed for both trackers by this
repo's own `eval/` differ by **0.0**.

`parity/run_parity.py` in the sibling repo reproduces all of it and exits
non-zero on any divergence.

### What the plan got right

- **The tie-break trap was the real risk.** Four behaviours in the Hungarian
  port turned out to be load-bearing, all verified by deliberately breaking them:
  the `rows > cols` transpose condition, both strictly-less tie comparisons, and
  the slack expression order. The last nearly escaped — regrouping
  `cost - u - v` as `cost - (u + v)` changed the *values* in 82 of 2,400 random
  matrices and the *answer* in none, so it read as cosmetic, until a targeted
  search over mixed magnitudes with ULP-level ties found it flips the assignment
  ~5 times in 6,000.
- **Trajectory parity was the right gate.** Metric parity alone would have
  passed a wrong tracker; it is reported last and trusted least.

### What the plan got wrong

**Floating-point contraction was the biggest unlisted risk.** clang defaults to
`-ffp-contract=fast` at `-O2`/`-O3`, fusing `a + b*c` into one FMA that rounds
*once* where NumPy rounds twice. It broke parity on exactly the height-scaled
Kalman process-noise terms. `-ffp-contract=off` is now load-bearing. The mirror
case also exists and cannot be fixed: `appearance_distance` ends in a matmul
where **Accelerate** is the one fusing, and the port cannot follow.

**"No speedup, possibly slower" was wrong** — measured, 36–53× on real sequences
and 68–84× from 5 to 400 simultaneous objects. The premise was that "NumPy's
inner loops are already compiled BLAS-adjacent code". Profiling shows that is
not true of this tracker's hot path:

- `_kuhn_munkres` is a hand-written O(n³) triple loop in **pure Python**, and the
  largest single entry in the profile. No vectorization anywhere in it.
- The per-track calls run on 4- and 8-element arrays — `xyah_to_xyxy` ~8,850
  times per 60 frames, `kalman.update` ~2,950 — where NumPy's fixed per-call cost
  dwarfs the arithmetic.

Two easier explanations were tested and rejected: `Detection` construction (at
most 3% of a frame) and NumPy per-call overhead on small matrices (which would
predict the advantage collapsing as the problem grows; it stays flat).

### Consequence for Phase 2

The intended headline — *"LAPJV replaced the O(n³) Hungarian and the numbers did
not move"* — needs revising. Much of what LAPJV was expected to win was
interpreter overhead the C++ port has already removed, so the remaining
algorithmic gain should be expected to be **smaller** than assumed. It now has a
fair baseline and a gate that fails on a single flipped association, which is
what Phase 1 was actually for.

---

## Phases 2 and 4 — outcome (2026-09-09)

Phase 2 (CPU optimization) and Phase 4 (package + benchmark) are both done.
Phase 3 (GPU) is not started and cannot be, on this machine — see *The hardware
caveat* above, which the plan got exactly right.

### Phase 2 — the headroom was the finding

The plan expected SIMD IoU, batched Kalman predict, LAPJV and memory-layout
work to compound into a meaningful speedup over the Phase 1 port. Five
optimizations were implemented and measured. Almost none of them paid.

The reason is a rule the plan did not contain, and which turned out to govern
everything: **an optimization is legal here only if every floating-point
operation still happens in the same order, on the same values, with the same
rounding.** That is what "identical to the oracle" means once you write it out.
Its corollary forecloses most of the standard playbook — SIMD *across*
independent problems is legal, SIMD *within* a reduction is not, because
vectorizing a sum reassociates it.

The one attempt that survived was hoisting two per-row allocations out of the
Hungarian solver: one allocation instead of *n*, touching no arithmetic. The
measured effect was below the noise floor, and an analytic bound (0.25 µs per
allocation → 0.13% of a frame) is the only honest way to state it.

LAPJV is the instructive failure. The plan's intended headline was *"LAPJV
replaced the O(n³) Hungarian and the numbers did not move"*. It was implemented
correctly — including a bug worth recording: the textbook column reduction is
valid for square problems and invalid for rectangular ones, because the
rectangular dual requires `v_j ≤ 0`; 714 of 1,826 test matrices came back
suboptimal, every failure rectangular. Once fixed, it produced **no measurable
speedup**, and the mechanism is that all nine solver disagreements on real data
fell on pairs the gate discards anyway. Predicted wrong by me, then measured.

`PHASE2.md` in the sibling repo has the full catalogue. A list of optimizations
that did not work, with the measurements showing why, is the more useful
artifact.

### Phase 4 — the deliverables, and what measuring properly cost

All three deliverables exist: `bench/compare.py` (reproducible benchmark on
identical detections), `bench/speedup.svg` (the one figure), and a packaged
`visiontrack-cpp` 0.1.0 — sdist and wheel, `twine check` clean, verified by
installing into a clean venv. The PyPI upload itself needs the account token
and is the one step left.

The benchmark's design decision is that it will not report a ratio it has not
verified: same detections into both trackers, full output streams compared
bit-for-bit, and only then a timing. No flag skips it. **100,765 observations,
0 differences**, then **55–74×** on the real MOT17-09 variants and **71–91×**
synthetic.

Building it turned up something the plan could not have predicted, and which is
the most transferable result of the whole exercise: **the parity harness had
been under-reporting the port by ~21%.** It runs both trackers in one loop,
frame by frame — which the gate requires, since the two must see identical state
at identical times. But NumPy's allocations evict the C++ tracker's working set
between calls. That costs the port ~2 µs on a 9.5 µs frame and costs NumPy 0.3%
of a 700 µs frame. The bias is asymmetric and lands entirely on the smaller
number.

So an instrument built to prove *agreement* was quietly biased when asked about
*speed*, in the direction that understated the result. Three candidate causes
were measured before the right one was accepted; timer placement, the obvious
suspect, accounted for 1%.

Phase 4 also established that parity is not an artifact of one machine's Eigen:
a build against a pinned Eigen 3.4.0, installed from the sdist into a clean
venv, passes the full suite and the trajectory gate with zero divergences —
matching the 3.5.0 result exactly. Two versions is two data points, not a
guarantee, which is why the dependency is pinned rather than floating.

### Scoring the plan

| the plan said | outcome |
|---|---|
| Phase 3 needs a cloud GPU; cannot be developed on the M2 | ✅ correct, and unchanged |
| Phase 2 SIMD/LAPJV/layout work would compound into a real speedup | ❌ the parity rule forbids most of it; the headroom is small |
| "LAPJV replaced the Hungarian and the numbers did not move" | ✅ true, for a reason the plan did not anticipate |
| the headline would be "N× throughput with the speedup attributed to specific optimizations" | ⚠️ the N× is real and attributed — but to *removing the interpreter*, not to any Phase 2 optimization |
| "that attribution is the portfolio value" | ✅ still the right call, and the negative results carry more of it than the positive ones |
