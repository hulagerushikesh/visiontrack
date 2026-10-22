"""Read-only registration preflight; no new inputs, tracker runs or file writes.

The new registration references, but never modifies, the opened traffic v1
characterization. Checksums protect reviewed bytes, not against malicious edits
to both an artifact and its version-controlled lock. This is not a run gate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.traffic_protocol import (
    ROOT,
    _read_bounded,
    _reject_constant,
    _unique_pairs,
    load_frozen_protocol,
)

ARTIFACTS = (
    "experiments/box_gate_protocol_v1.json",
    "docs/BOX_GATE_ABLATION_PROTOCOL.md",
)
LOCK = "experiments/box_gate_protocol_v1.sha256"
INHERITED = (
    "frame_grid", "world_roi", "projection", "ideal_box", "observation_error",
    "conditions", "tracker_config", "anchors", "crossing", "diagnostics",
)


def load_registration(root: Path = ROOT) -> tuple[dict, dict[str, str]]:
    """Verify the two exact artifacts and their pinned parent recipe.

    Injectable root supports isolated tests, not arbitrary CLI paths. Parent
    validation is integrity-only: it does not reopen the consumed held-out run.
    The returned registration is not directly accepted by any existing runner.
    """
    lines = _read_bounded(root / LOCK).decode("ascii").splitlines()
    if len(lines) != len(ARTIFACTS):
        raise ValueError("registration lock must contain exactly two artifacts")
    payloads, hashes = {}, {}
    for line, expected in zip(lines, ARTIFACTS, strict=True):
        digest, separator, name = line.partition("  ")
        if separator != "  " or name != expected:
            raise ValueError("unexpected registration lock path or order")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid registration SHA-256")
        data = _read_bounded(root / expected)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"registered artifact changed: {expected}")
        hashes[expected], payloads[expected] = digest, data
    spec = json.loads(
        payloads[ARTIFACTS[0]],
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(spec, dict) or spec.get("protocol_id") != "visiontrack.box-gate-ablation/v1":
        raise ValueError("unexpected registration ID")
    parent, parent_hashes = load_frozen_protocol(root)
    if spec.get("parent_artifacts") != parent_hashes:
        raise ValueError("registration parent bytes differ")
    if spec.get("baseline_revision") != parent["baseline_revision"]:
        raise ValueError("registration baseline differs")
    if spec.get("inherit_unchanged") != list(INHERITED):
        raise ValueError("registration inheritance differs")
    if spec.get("variants") != [
        {"id": "baseline", "config_patch": {}},
        {"id": "gate_off", "config_patch": {"use_mahalanobis_gating": False}},
    ]:
        raise ValueError("registration must change only the one gate setting")
    return spec, {**parent_hashes, **hashes}


def main() -> int:
    try:
        spec, hashes = load_registration()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Registration integrity check failed: {exc}")
        return 2
    print(spec["protocol_id"])
    for name, digest in hashes.items():
        print(f"{digest}  {name}")
    print("Registration verified; no new random inputs, tracker runs or results.")
    print("Implementation harness and new held-out opening are not yet frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
