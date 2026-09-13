"""Unit checks for the cross-repository learning capstone runner."""

import sys
from pathlib import Path

from learning.parity_capstone import CPP_TESTS, default_cpp_repo, parity_command


def test_capstone_defaults_to_cpp_sibling() -> None:
    assert default_cpp_repo().name == "visiontrack-cpp"
    assert default_cpp_repo().parent == Path(__file__).resolve().parents[2]


def test_capstone_runs_only_dataset_free_parity_tests() -> None:
    command = parity_command()
    assert command[:4] == [sys.executable, "-m", "pytest", "-q"]
    assert all(test in command for test in CPP_TESTS)
    assert command[-2:] == ["-m", "not slow"]
