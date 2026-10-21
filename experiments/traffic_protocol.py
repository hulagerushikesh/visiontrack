"""Read-only integrity preflight for the frozen traffic mechanism recipe.

This is not a general experiment-config validator or a tracker runner. It only
accepts the two exact checked-in v1 artifacts; amendments need a new version.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ("experiments/traffic_protocol_v1.json", "docs/TRAFFIC_RELIABILITY_PROTOCOL.md")
LOCK = ROOT / "experiments/traffic_protocol_v1.sha256"
MAX_BYTES = 256 * 1024


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("protocol artifact exceeds size limit")
    return data


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate protocol key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite protocol constant: {value}")


def load_frozen_protocol(root: Path = ROOT) -> tuple[dict, dict[str, str]]:
    """Verify raw recipe/doc bytes against the version-controlled SHA-256 lock.

    ``root`` is injectable for isolated tests, not supplied by the CLI. There are
    no user-chosen artifact paths, result writes, inference or network calls.
    The lock is a Git-reviewed checksum, not an independent trust authority.
    """
    lines = _read_bounded(root / LOCK.relative_to(ROOT)).decode("ascii").splitlines()
    if len(lines) != len(ARTIFACTS):
        raise ValueError("protocol lock must contain exactly two artifacts")
    digests = {}
    payloads = {}
    for line, expected in zip(lines, ARTIFACTS, strict=True):
        digest, separator, filename = line.partition("  ")
        if separator != "  " or filename != expected:
            raise ValueError("unexpected protocol lock path or order")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid protocol SHA-256")
        data = _read_bounded(root / expected)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"frozen artifact changed: {expected}")
        digests[expected] = digest
        payloads[expected] = data
    spec = json.loads(
        payloads[ARTIFACTS[0]],
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(spec, dict) or spec.get("protocol_id") != "visiontrack.traffic-mechanism/v1":
        raise ValueError("unexpected protocol ID")
    return spec, digests


def main() -> int:
    """Print integrity status only; do not execute even development tracking."""
    try:
        spec, digests = load_frozen_protocol()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Protocol integrity check failed: {exc}")
        return 2
    print(spec["protocol_id"])
    for name, digest in digests.items():
        print(f"{digest}  {name}")
    print("Recipe integrity verified; no tracker run, results, or real-data validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
