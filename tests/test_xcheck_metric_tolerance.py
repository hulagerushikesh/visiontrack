"""The end-to-end helper must not accept a relaxed post-hoc tolerance."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("value", ["0.003", "0", "nan", "inf"])
def test_loose_or_invalid_tolerance_rejected_before_data_access(value):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/xcheck_mot17_trackeval.py"), "--tol", value],
        cwd=root, text=True, capture_output=True, timeout=20)
    assert result.returncode == 2
    assert "no greater than 1e-10" in result.stderr
    assert "cache missing" not in result.stdout
