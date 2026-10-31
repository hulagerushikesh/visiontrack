"""Exact historical test inventory; new tests are never ignored by a wildcard."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

REVISION = "121c755c7bc587c4484d535760c61259664b0333"
METADATA = Path(__file__).parent / "fixtures/frozen_git_metadata_v1.json"
METADATA_SHA256 = "7d3f08e358c2f3a76af7ab49f6ed7a5bce0f143eac909ae6d7ffc97ad97bf314"


def frozen_metadata(path=METADATA):
    """Read sealed original commit headers, never alternate source or results."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != METADATA_SHA256:
        raise ValueError("frozen Git metadata changed")
    payload = json.loads(data)
    assert payload["schema"] == "visiontrack.frozen-git-metadata/v1"
    assert payload["tip"] == REVISION
    for revision, content in payload["commits"].items():
        raw = content.encode()
        digest = hashlib.sha1(b"commit " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if digest != revision:
            raise ValueError("frozen commit identity changed")
    return payload["commits"]


def frozen_tree(revision):
    """Return the original content-addressed tree, also reachable in current main."""
    return frozen_metadata()[revision].splitlines()[0].removeprefix("tree ")


def restore_frozen_metadata(checkout):
    """Restore exact Git objects only inside a disposable regression clone.

    Main's rewritten history contains every original source tree unchanged.
    These headers restore original identities/ancestry without a network fetch,
    replacement refs, altered evidence, or edits to the user's repository.
    """
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"}
    commits = frozen_metadata()
    for revision, content in commits.items():
        tree = content.splitlines()[0].removeprefix("tree ")
        subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", f"{tree}^{{tree}}"],
                       env=env, check=True, capture_output=True, timeout=30)
        result = subprocess.run(
            ["git", "-C", str(checkout), "hash-object", "-t", "commit", "-w", "--stdin"],
            input=content.encode(), env=env, check=True, capture_output=True, timeout=30)
        assert result.stdout.decode().strip() == revision


FILES = (
    "test_box_gate_audit.py",
    "test_box_gate_combined_audit.py",
    "test_box_gate_decision.py",
    "test_box_gate_diagnosis.py",
    "test_box_gate_execution.py",
    "test_box_gate_holdout.py",
    "test_box_gate_protocol.py",
    "test_box_gate_report.py",
    "test_box_gate_runner.py",
    "test_box_gate_scene.py",
    "test_box_gate_scoring.py",
    "test_box_gate_trace.py",
    "test_box_gate_trace_audit.py",
    "test_box_gate_trace_replay.py",
    "test_mot17_case_baseline.py",
    "test_traffic_crossing.py",
    "test_traffic_diagnostics.py",
    "test_traffic_holdout.py",
    "test_traffic_protocol.py",
    "test_traffic_report.py",
    "test_traffic_runner.py",
    "test_traffic_scene.py",
)
