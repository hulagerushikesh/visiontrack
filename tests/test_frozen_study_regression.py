"""Execute, do not weaken or reinterpret, the sealed historical regression suite."""
import os
import subprocess
import sys
from pathlib import Path

from tests.frozen_suite import FILES, REVISION

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_v1_studies_in_isolated_original_revision(tmp_path):
    checkout = tmp_path / "frozen-v1"
    # Local object sharing only, no network or new worktree on the user's branch.
    subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet",
                    str(ROOT), str(checkout)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(checkout),
                    "checkout", "--detach", "--quiet", REVISION],
                   check=True, capture_output=True, text=True)
    files = [f"tests/{name}" for name in FILES]
    assert len(files) == 22 and all((checkout / name).is_file() for name in files)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(checkout / "src"), str(checkout))))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short",
         "-o", "addopts=-m 'not slow'", *files],
        cwd=checkout, env=env, capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout[-24000:] + result.stderr[-8000:]
    print("Frozen v1 regression:", result.stdout.strip().splitlines()[-1])


def test_frozen_runner_still_rejects_changed_current_source():
    import pytest

    from experiments.traffic_protocol import load_frozen_protocol
    from experiments.traffic_runner import _verify_tree

    registration, _ = load_frozen_protocol()
    with pytest.raises(ValueError, match="source drift|unexpected package"):
        _verify_tree(ROOT, registration["baseline_revision"])
