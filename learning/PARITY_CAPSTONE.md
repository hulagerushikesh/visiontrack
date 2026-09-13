# NumPy-versus-C++ parity capstone

## Question

Can an optimized C++ tracker preserve the NumPy reference contract—not merely
similar metrics, but the same geometry, state estimation, assignment decisions,
lifecycle transitions, and complete synthetic output trajectories?

## Prerequisites

- Finish the four [dataset-free exercises](EXERCISES.md).
- Keep `visiontrack` and `visiontrack-cpp` as sibling checkouts, or know the C++
  checkout path.
- Install both repositories in the same development environment.

## Run the gate

From the `visiontrack` repository:

```bash
python learning/parity_capstone.py
```

For a different checkout layout:

```bash
python learning/parity_capstone.py --cpp-repo /path/to/visiontrack-cpp
```

The capstone deliberately excludes real MOT data. It runs the C++ repository's
geometry, Kalman, assignment, lifecycle/cost, and synthetic trajectory parity
tests. Expected result: `171 passed`, followed by `capstone: PASS`.

## Explain the evidence

Before calling the port equivalent, answer these questions:

1. Why can matching HOTA or MOTA still hide a different identity trajectory?
2. Which operations may use numerical tolerances, and which discrete outputs
   must match exactly?
3. Why does one changed assignment propagate beyond the frame where it occurs?
4. Why must the NumPy implementation remain the oracle rather than letting both
   repositories evolve independently?

Use the C++ repository's `parity/REPORT.md` to compare unit, trajectory, and
metric parity. The strongest claim is trajectory parity; metrics are only the
backstop.

## Controlled failure

Read `visiontrack-cpp/tests/test_parity_harness.py`, especially the one-ULP
mutation test. Explain why a trustworthy gate must demonstrate that it detects
a known divergence. Do not weaken tolerances to make a failure disappear; find
the first divergent frame and identify the violated contract.

## Completion outcome

You are finished when the gate passes and you can defend why the evidence is
stronger than “the C++ version gets similar benchmark scores.”
