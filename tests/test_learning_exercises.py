"""Keep the dataset-free learning exercises runnable and deterministic."""

from learning.exercises import EXERCISES


def test_all_learning_exercises(capsys) -> None:
    for exercise in EXERCISES.values():
        exercise()
    output = capsys.readouterr().out
    for name in EXERCISES:
        assert f"{name}: PASS" in output
