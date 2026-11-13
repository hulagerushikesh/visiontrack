"""Run the paper's frozen experiment from a full clone and verify its results."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_METHOD = "4b44af0abb0c7448f6baf796e5cfa1062d52f6a6"
PUBLIC_BASELINE = "dfc0b6ccf7578ebdecd32c866f26792ff0e16851"
FROZEN_SUMMARY = ROOT / "experiments/initiation_threshold_v1_results.json"

# Run in a separate interpreter so imports come from the historical checkout.
REPLAY = """
import sys
from pathlib import Path

sys.path[:0] = ["src", "."]
from experiments import initiation_threshold

initiation_threshold.BASELINE = sys.argv[1]
initiation_threshold.execute(Path(sys.argv[2]))
"""


def verify(output: Path) -> None:
    saved = json.loads(FROZEN_SUMMARY.read_bytes())
    replay = json.loads((output / "summary.json").read_bytes())
    method = replay["method"]
    if method["revision"] != PUBLIC_METHOD or method["package"]["revision"] != PUBLIC_BASELINE:
        raise ValueError("Replay used unexpected Git revisions")
    environment = method["environment"]
    for summary in (saved, replay):
        del summary["method"]["revision"]
        del summary["method"]["package"]["revision"]
        del summary["method"]["environment"]
    expected_cases = saved.pop("cells")
    actual_cases = replay.pop("cells")
    if saved != replay:
        raise ValueError("Replay metadata differs from the frozen summary")
    if len(expected_cases) != len(actual_cases):
        raise ValueError(f"Expected {len(expected_cases)} pairs, found {len(actual_cases)}")
    for expected, actual in zip(expected_cases, actual_cases, strict=True):
        if expected != actual:
            fields = ", ".join(
                key for key in sorted(expected.keys() | actual.keys())
                if key not in expected or key not in actual or expected[key] != actual[key]
            )
            raise ValueError(
                f"Replay differs for {expected['case']} at score {expected['score']}, "
                f"speed {expected['speed']} ({fields}). Inspect {output}"
            )
    print(f"Verified {len(actual_cases)} pairs with exact output hashes.")
    print(f"Replay environment: {environment}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory outside both repos",
    )
    args = parser.parse_args()
    output = args.output.absolute()
    repositories = (ROOT, ROOT.parent / "visiontrack-cpp")
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or any(output.resolve().is_relative_to(repo) for repo in repositories)):
        parser.error("--output needs an existing parent and must be new and outside both repos")
    git = ["git", "-C", str(ROOT)]
    with TemporaryDirectory(prefix="visiontrack-paper-") as temporary:
        source = Path(temporary) / "source"
        subprocess.run(
            [*git, "worktree", "add", "--detach", str(source), PUBLIC_METHOD], check=True,
        )
        try:
            subprocess.run(
                [sys.executable, "-I", "-B", "-c", REPLAY, PUBLIC_BASELINE, str(output)],
                cwd=source, check=True,
            )
        finally:
            subprocess.run([*git, "worktree", "remove", str(source)], check=True)
    try:
        verify(output)
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
