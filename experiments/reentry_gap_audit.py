"""List DanceTrack GT gap candidates without reading or exporting video frames.

Run ``python -m experiments.reentry_gap_audit --root /path/to/dancetrack/val``.
The output is an annotation audit, never a verified re-entry event list or
identity-restoration result. Sampling is stable under row and file ordering.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path

STRATA = ("1-9", "10-29", "30-99", "100+")


@dataclass(frozen=True, order=True)
class GapCandidate:
    sequence: str
    sequence_id: int
    last_seen_frame: int
    next_seen_frame: int
    missing_frames: int
    stratum: str


def _stratum(missing_frames: int) -> str:
    if missing_frames < 10:
        return STRATA[0]
    if missing_frames < 30:
        return STRATA[1]
    if missing_frames < 100:
        return STRATA[2]
    return STRATA[3]


def extract_gap_candidates(root: Path) -> tuple[list[GapCandidate], int, int]:
    """Return candidate absence windows, GT row count, and sequence-ID count.

    Identity IDs are meaningful only within one sequence. Duplicate frame-ID
    annotations and malformed rows fail closed instead of inflating counts.
    """
    files = sorted(root.glob("*/gt/gt.txt"))
    if not files:
        raise ValueError(f"no sequence/gt/gt.txt files below {root}")
    candidates: list[GapCandidate] = []
    rows = 0
    keys = 0
    for path in files:
        frames_by_id: dict[int, set[int]] = defaultdict(set)
        with path.open(newline="", encoding="utf-8") as handle:
            for line_number, row in enumerate(csv.reader(handle), start=1):
                if len(row) < 2:
                    raise ValueError(f"{path}:{line_number}: expected frame and identity ID")
                try:
                    frame = int(row[0])
                    identity = int(row[1])
                except ValueError as error:
                    raise ValueError(f"{path}:{line_number}: non-integer frame or ID") from error
                if frame < 1 or identity < 0:
                    raise ValueError(f"{path}:{line_number}: invalid frame or ID")
                if frame in frames_by_id[identity]:
                    raise ValueError(f"{path}:{line_number}: duplicate frame/ID")
                frames_by_id[identity].add(frame)
                rows += 1
        keys += len(frames_by_id)
        for identity, frames in frames_by_id.items():
            ordered = sorted(frames)
            for before, after in pairwise(ordered):
                missing = after - before - 1
                if missing:
                    candidates.append(
                        GapCandidate(
                            path.parent.parent.name,
                            identity,
                            before,
                            after,
                            missing,
                            _stratum(missing),
                        )
                    )
    return sorted(candidates), rows, keys


def _digest(events: list[GapCandidate]) -> str:
    payload = json.dumps([asdict(event) for event in events], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def summarize(root: Path, *, sample_per_stratum: int = 5) -> dict:
    """Freeze a hash-ranked audit sample before anyone inspects its frames."""
    if sample_per_stratum < 0:
        raise ValueError("sample_per_stratum must be nonnegative")
    candidates, rows, keys = extract_gap_candidates(root)
    by_stratum: dict[str, list[GapCandidate]] = {name: [] for name in STRATA}
    by_sequence = Counter()
    for event in candidates:
        by_stratum[event.stratum].append(event)
        by_sequence[event.sequence] += 1
    samples = {}
    for name, events in by_stratum.items():
        ranked = sorted(events, key=lambda event: (_digest([event]), event))
        samples[name] = [asdict(event) for event in ranked[:sample_per_stratum]]
    return {
        "label": "GT absence candidates only; visual re-entry truth not verified",
        "selection": "smallest SHA-256 of canonical event JSON within each duration stratum",
        "sample_per_stratum": sample_per_stratum,
        "sequence_count": len(list(root.glob("*/gt/gt.txt"))),
        "gt_rows": rows,
        "sequence_scoped_identity_keys": keys,
        "candidate_count": len(candidates),
        "candidate_sha256": _digest(candidates),
        "stratum_counts": {name: len(by_stratum[name]) for name in STRATA},
        "sequence_counts": dict(sorted(by_sequence.items())),
        "audit_sample": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Local validation split root")
    parser.add_argument("--sample-per-stratum", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(summarize(args.root, sample_per_stratum=args.sample_per_stratum), indent=2))


if __name__ == "__main__":
    main()
