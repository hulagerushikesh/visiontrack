"""Linear assignment (the Hungarian algorithm) implemented from scratch.

Data association in tracking is a minimum-cost bipartite matching: given a
cost matrix between tracks and detections, find the one-to-one assignment
that minimises total cost. ``scipy.optimize.linear_sum_assignment`` would do
this in one line, but the point of this module is to *own* the algorithm — it
is validated against SciPy in the test-suite rather than delegating to it.

:func:`linear_assignment` runs the O(n³) Kuhn–Munkres / Jonker–Volgenant
shortest-augmenting-path variant with dual potentials. It handles rectangular
matrices directly (no padding to a square with big-M costs, which is both
slower and numerically fragile).

:func:`associate` wraps the solver with the gating logic every tracker needs:
it forbids matches whose cost exceeds a threshold and returns the matched
pairs plus the leftover row/column indices.
"""
from __future__ import annotations

import numpy as np

__all__ = ["linear_assignment", "associate"]


def linear_assignment(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Solve the rectangular linear-sum-assignment problem (minimisation).

    Parameters
    ----------
    cost:
        ``(n, m)`` matrix of finite costs.

    Returns
    -------
    (row_ind, col_ind):
        Index arrays of length ``min(n, m)`` such that ``cost[row_ind,
        col_ind].sum()`` is minimal and each index appears at most once.
        Matches the contract of ``scipy.optimize.linear_sum_assignment``.
    """
    cost = np.asarray(cost, dtype=np.float64)
    if cost.size == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    if not np.all(np.isfinite(cost)):
        raise ValueError("cost matrix must be finite; gate before assignment")

    transposed = False
    if cost.shape[0] > cost.shape[1]:
        # The classic potentials formulation assumes rows <= cols. Transpose
        # tall matrices and swap the result back at the end.
        cost = cost.T
        transposed = True

    n, m = cost.shape  # n <= m
    row_for_col = _kuhn_munkres(cost)  # column j -> assigned row (or -1)

    rows = np.full(n, -1, dtype=np.int64)
    for j in range(m):
        i = row_for_col[j]
        if i != -1:
            rows[i] = j

    row_ind = np.arange(n, dtype=np.int64)
    col_ind = rows
    if transposed:
        row_ind, col_ind = col_ind, row_ind
    return row_ind, col_ind


def _kuhn_munkres(cost: np.ndarray) -> np.ndarray:
    """Core O(n³) solver for ``n x m`` cost with ``n <= m``.

    Returns an array ``p`` of length ``m`` where ``p[j]`` is the row matched
    to column ``j`` (1-indexed internally, ``-1`` for unmatched). Follows the
    standard shortest-augmenting-path Hungarian with potentials ``u`` (rows)
    and ``v`` (columns).
    """
    n, m = cost.shape
    INF = np.inf

    u = np.zeros(n + 1)
    v = np.zeros(m + 1)
    p = np.zeros(m + 1, dtype=np.int64)     # p[j] = row assigned to column j
    way = np.zeros(m + 1, dtype=np.int64)   # back-pointers for augmenting path

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = np.full(m + 1, INF)
        used = np.zeros(m + 1, dtype=bool)
        # Grow the alternating tree until we reach an unmatched column.
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = -1
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1, j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            # Re-weight potentials so the tightest edge becomes tight (0 slack).
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        # Flip the augmenting path, attaching row ``i`` to a free column.
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1

    result = np.full(m, -1, dtype=np.int64)
    for j in range(1, m + 1):
        if p[j] != 0:
            result[j - 1] = p[j] - 1
    return result


def associate(
    cost: np.ndarray,
    max_cost: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gated one-to-one association between rows and columns.

    Solves the assignment, then rejects any matched pair whose cost exceeds
    ``max_cost`` (those rows/columns are reported as unmatched instead).

    Parameters
    ----------
    cost:
        ``(n_rows, n_cols)`` cost matrix; lower is better.
    max_cost:
        Inclusive upper bound on the cost of an accepted match.

    Returns
    -------
    matches:
        ``(k, 2)`` array of ``(row, col)`` index pairs.
    unmatched_rows, unmatched_cols:
        1-D index arrays of rows/columns left unassigned.
    """
    cost = np.asarray(cost, dtype=np.float64)
    n_rows, n_cols = cost.shape

    if n_rows == 0 or n_cols == 0:
        return (
            np.empty((0, 2), dtype=np.int64),
            np.arange(n_rows, dtype=np.int64),
            np.arange(n_cols, dtype=np.int64),
        )

    row_ind, col_ind = linear_assignment(cost)

    matches = []
    matched_rows: set[int] = set()
    matched_cols: set[int] = set()
    for r, c in zip(row_ind, col_ind, strict=False):
        if cost[r, c] <= max_cost:
            matches.append((int(r), int(c)))
            matched_rows.add(int(r))
            matched_cols.add(int(c))

    unmatched_rows = np.array(
        [r for r in range(n_rows) if r not in matched_rows], dtype=np.int64
    )
    unmatched_cols = np.array(
        [c for c in range(n_cols) if c not in matched_cols], dtype=np.int64
    )
    matches_arr = (
        np.array(matches, dtype=np.int64) if matches else np.empty((0, 2), dtype=np.int64)
    )
    return matches_arr, unmatched_rows, unmatched_cols
