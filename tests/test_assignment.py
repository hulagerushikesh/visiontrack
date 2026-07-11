import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from visiontrack.core.assignment import associate, linear_assignment


def _cost_of(cost, rows, cols):
    return cost[rows, cols].sum()


@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("shape", [(1, 1), (3, 3), (4, 6), (7, 3), (10, 10), (2, 9)])
def test_matches_scipy_optimal_cost(seed, shape):
    """Our Hungarian must reach the same optimal cost as SciPy's."""
    rng = np.random.default_rng(seed * 100 + shape[0])
    cost = rng.uniform(0, 100, size=shape)

    r_ours, c_ours = linear_assignment(cost)
    r_sci, c_sci = linear_sum_assignment(cost)

    # Optimal total cost must match exactly (assignment may differ on ties).
    assert _cost_of(cost, r_ours, c_ours) == pytest.approx(
        _cost_of(cost, r_sci, c_sci), abs=1e-6
    )
    # Result is a valid partial permutation.
    assert len(set(r_ours.tolist())) == len(r_ours)
    assert len(set(c_ours.tolist())) == len(c_ours)
    assert len(r_ours) == min(shape)


def test_negative_costs_allowed():
    rng = np.random.default_rng(0)
    cost = rng.uniform(-50, 50, size=(5, 5))
    r, c = linear_assignment(cost)
    r_s, c_s = linear_sum_assignment(cost)
    assert _cost_of(cost, r, c) == pytest.approx(_cost_of(cost, r_s, c_s))


def test_empty_matrix():
    r, c = linear_assignment(np.zeros((0, 0)))
    assert r.size == 0 and c.size == 0


def test_non_finite_rejected():
    with pytest.raises(ValueError):
        linear_assignment(np.array([[np.inf, 1.0], [1.0, 1.0]]))


def test_associate_gates_by_max_cost():
    # Two clearly-good matches on the diagonal, one impossible pairing.
    cost = np.array(
        [
            [0.1, 5.0, 5.0],
            [5.0, 0.2, 5.0],
            [5.0, 5.0, 9.0],  # best option (9.0) still exceeds the gate
        ]
    )
    matches, un_rows, un_cols = associate(cost, max_cost=1.0)
    pairs = {tuple(m) for m in matches.tolist()}
    assert (0, 0) in pairs and (1, 1) in pairs
    assert 2 in un_rows.tolist()
    assert 2 in un_cols.tolist()


def test_associate_empty_inputs():
    matches, ur, uc = associate(np.zeros((0, 3)), max_cost=1.0)
    assert matches.shape == (0, 2)
    assert ur.tolist() == []
    assert uc.tolist() == [0, 1, 2]
