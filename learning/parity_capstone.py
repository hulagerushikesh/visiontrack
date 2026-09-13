"""Run the dataset-free NumPy-versus-C++ parity capstone.

The default layout expects ``visiontrack`` and ``visiontrack-cpp`` to be sibling
checkouts. Pass ``--cpp-repo`` when the C++ repository lives elsewhere.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CPP_TESTS = (
    "tests/test_parity_geometry.py",
    "tests/test_parity_kalman.py",
    "tests/test_parity_assignment.py",
    "tests/test_parity_tracker.py",
)


def default_cpp_repo() -> Path:
    return Path(__file__).resolve().parents[2] / "visiontrack-cpp"


def parity_command() -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", *CPP_TESTS, "-m", "not slow"]


def run(cpp_repo: Path) -> None:
    missing = [path for path in CPP_TESTS if not (cpp_repo / path).is_file()]
    if missing:
        raise SystemExit(
            f"C++ sibling not found at {cpp_repo}. "
            "Pass its checkout with --cpp-repo."
        )
    print(f"oracle: {Path(__file__).resolve().parents[1]}")
    print(f"candidate: {cpp_repo.resolve()}")
    print("gate: unit, FSM, cost, and synthetic trajectory parity (no datasets)")
    subprocess.run(parity_command(), cwd=cpp_repo, check=True)
    print("capstone: PASS — the C++ candidate preserves the NumPy contract")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpp-repo", type=Path, default=default_cpp_repo())
    run(parser.parse_args().cpp_repo)


if __name__ == "__main__":
    main()
