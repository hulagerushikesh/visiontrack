"""Dataset preprocessing parity is separate from evaluator-formula parity."""
import ast
import subprocess
from pathlib import Path

import numpy as np
import pytest

from experiments.mot17_metric_crosscheck import reference_api
from experiments.mot17_preprocessing_audit import local_row, reference_rows
from tests.frozen_suite import frozen_tree
from tests.test_mot17_preprocessing_audit import BOX, row
from visiontrack.eval import mot17


def test_threshold_before_assignment_counterexample(monkeypatch):
    pytest.importorskip("trackeval")
    te, _, _ = reference_api()
    matrix = np.array([[.9, .49], [.5, 0.]])
    original = row([1, 7], predictions=[BOX, BOX])
    monkeypatch.setattr(mot17, "metric_iou", lambda *args: matrix.copy())
    expected = reference_rows([original], te, lambda *args, **kwargs: matrix.copy())[0]
    assert local_row(original) == expected
    assert expected["track_ids"] == [1, 2]
    # Historical preprocessor uses tracker x GT orientation, and thresholds after assignment.
    monkeypatch.setattr(mot17, "iou_matrix", lambda *args: matrix.T.copy())
    assert local_row(original, policy=mot17.LEGACY_MOT17_PREPROCESSING)["track_ids"] == [2]


@pytest.mark.parametrize("seed", range(8))
def test_crowded_mixed_class_inputs_match_independent_reference(seed):
    pytest.importorskip("trackeval")
    te, iou, _ = reference_api()
    rng = np.random.default_rng(seed)
    rows = []
    for frame in range(1, 21):
        centers = rng.uniform(0, 40, size=(15, 2))
        sizes = rng.uniform(4, 20, size=(15, 2))
        boxes = np.column_stack((centers, centers + sizes))
        predictions = boxes + rng.normal(0, 2, boxes.shape)
        predictions[:, 2:] = np.maximum(predictions[:, 2:], predictions[:, :2] + .1)
        original = row(classes=rng.integers(1, 14, size=15).tolist(),
                       flags=rng.integers(0, 2, size=15).tolist(), boxes=boxes.tolist(),
                       predictions=predictions.tolist(), frame=frame,
                       ids=rng.permutation(np.arange(1, 16) * 7).tolist())
        rows.append(original)
    reference = reference_rows(rows, te, iou)
    assert [local_row(r) for r in rows] == reference


@pytest.mark.parametrize("threshold", [0, -1, np.nan, np.inf, 1.01])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ValueError, match="threshold"):
        mot17.preprocess_frame(np.array([BOX]), np.array([1]), np.array([1]),
                               np.array([1]), np.array([BOX]), np.array([7]), threshold)


def test_unknown_policy_rejected():
    with pytest.raises(ValueError, match="unknown MOT17"):
        local_row(row(), policy="future-policy")


def test_legacy_body_is_structurally_identical_to_pre_correction_source():
    root = Path(__file__).resolve().parents[1]
    old = subprocess.check_output(
        ["git", "show", f"{frozen_tree('69f319c72d3ef3083934af90f29b1cada30ff75b')}:"
         "src/visiontrack/eval/mot17.py"], cwd=root, text=True)
    new = (root / "src/visiontrack/eval/mot17.py").read_text()

    def body(source, name):
        function = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == name)
        return [ast.dump(n) for n in function.body[1:]]  # Provenance docstring differs.

    assert body(old, "preprocess_frame") == body(new, "_legacy_preprocess_frame")
