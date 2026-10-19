"""Audit the official MEVID annotation ZIP without extracting or reading images.

This is source feasibility, not re-entry truth or a model comparison. The chip
indices are not source-video frame numbers, timestamps, or exit boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

PREFIX = "mevid-v1-annotation-data/"
FILES = frozenset(
    (
        "train_name.txt",
        "test_name.txt",
        "track_train_info.txt",
        "track_test_info.txt",
        "query_IDX.txt",
    )
)
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 160 * 1024 * 1024
CHIP = re.compile(r"(\d{4})O(\d{3})C(\d{3})T(\d{3})F(\d{5})\.jpg")


def _lines(archive: zipfile.ZipFile, name: str):
    with archive.open(PREFIX + name) as raw, io.TextIOWrapper(raw, encoding="ascii") as handle:
        while line := handle.readline(4097):
            if len(line) > 4096:
                raise ValueError("metadata line exceeds limit")
            yield line.strip()


def _integer(value: str) -> int:
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number > 10**9 or number != int(number):
            raise ValueError("expected bounded nonnegative integer metadata")
        return int(number)
    except InvalidOperation as exc:
        raise ValueError("invalid numeric metadata") from exc


def _partition(archive: zipfile.ZipFile, split: str) -> tuple[dict, set[int], set[int]]:
    tracks = []
    next_start = 0
    metadata_rows = 0
    empty_ranges: set[int] = set()
    for line in _lines(archive, f"track_{split}_info.txt"):
        values = line.split()
        if len(values) != 5:
            raise ValueError("track metadata needs five columns")
        start, end, person, outfit, camera = map(_integer, values)
        if start != next_start or end < start - 1:
            raise ValueError("chip ranges must be contiguous, ordered, and inclusive")
        metadata_rows += 1
        if end == start - 1:
            empty_ranges.add(metadata_rows - 1)
        else:
            tracks.append((start, end, person, outfit, camera))
        next_start = end + 1
        if metadata_rows > 20_000:
            raise ValueError("too many tracklets")
    if not tracks:
        raise ValueError("empty track metadata")

    index = 0
    track_index = 0
    track_key = None
    seen_tracklets = set()
    groups: Counter = Counter()
    for line in _lines(archive, f"{split}_name.txt"):
        if index >= next_start:
            raise ValueError("extra chip names beyond track ranges")
        start, end, person, outfit, camera = tracks[track_index]
        match = CHIP.fullmatch(line)
        if not match:
            raise ValueError("invalid chip basename")
        p, o, c, t, frame = map(int, match.groups())
        if (p, o, c) != (person, outfit, camera) or frame != index - start:
            raise ValueError("chip name does not match its track metadata or local frame")
        key = (p, o, c, t)
        if index == start:
            if key in seen_tracklets:
                raise ValueError("duplicate tracklet key")
            seen_tracklets.add(key)
            track_key = key
            groups[p, o, c] += 1
        elif key != track_key:
            raise ValueError("tracklet changes inside declared chip range")
        index += 1
        if index - 1 == end:
            track_index += 1
    if index != next_start:
        raise ValueError("missing chip names from track ranges")
    people = {track[2] for track in tracks}
    return (
        {
            "track_metadata_rows": metadata_rows,
            "empty_chip_ranges": len(empty_ranges),
            "tracklets": len(tracks),
            "listed_chips": index,
            "participant_ids": len(people),
            "cameras": len({track[4] for track in tracks}),
            "participant_outfit_camera_groups": len(groups),
            "groups_with_multiple_tracklets": sum(count > 1 for count in groups.values()),
        },
        people,
        empty_ranges,
    )


def summarize(path: Path) -> dict:
    """Validate bounded metadata and emit aggregates only; never extract files."""
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("annotation ZIP exceeds limit")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        expected = {PREFIX + name for name in FILES}
        names = [member.filename for member in members if not member.is_dir()]
        if set(names) != expected or len(names) != len(expected):
            raise ValueError("expected exactly the five official annotation files")
        if any(member.is_dir() and member.filename != PREFIX for member in members):
            raise ValueError("unexpected archive directory")
        if any(member.file_size > MAX_MEMBER_BYTES or member.flag_bits & 1 for member in members):
            raise ValueError("oversized or encrypted metadata member")
        if sum(member.file_size for member in members) > MAX_TOTAL_BYTES:
            raise ValueError("expanded metadata exceeds limit")
        train, train_people, _ = _partition(archive, "train")
        test, test_people, empty_test = _partition(archive, "test")
        if train_people & test_people:
            raise ValueError("participant IDs cross the upstream train/test split")
        queries = []
        for line in _lines(archive, "query_IDX.txt"):
            queries.append(_integer(line))
            if len(queries) > 20_000:
                raise ValueError("too many query indices")
        if (
            not queries
            or len(set(queries)) != len(queries)
            or max(queries) >= test["track_metadata_rows"]
            or set(queries) & empty_test
        ):
            raise ValueError("invalid or duplicate test query indices")
    return {
        "schema_version": 1,
        "label": "MEVID annotation-only feasibility; not re-entry truth or accuracy",
        "archive_sha256": digest.hexdigest(),
        "train": train,
        "test": test,
        "query_tracklets": len(queries),
        "gallery_tracklets": test["tracklets"] - len(queries),
        "empty_ranges_require_review": bool(train["empty_chip_ranges"] or empty_test),
        "upstream_participant_overlap": 0,
        "same_camera_session_split": "not_established",
        "source_video_timing_and_exit_boundaries": "not_provided_by_these_chip_tables",
        "verified_reentry_events": 0,
        "rights_and_privacy_clearance": "not_verified_by_software",
        "identity_accuracy": "not_evaluated",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotations", type=Path, required=True, help="Owner-local annotation ZIP"
    )
    args = parser.parse_args()
    print(json.dumps(summarize(args.annotations), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
