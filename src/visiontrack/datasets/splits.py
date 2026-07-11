"""Loader for the frozen MOT17 train/val split.

The split itself lives in ``data/splits/mot17_val_half.json`` (committed, so it
never drifts). This module just finds and reads it, and maps a sequence name
like ``MOT17-02-FRCNN`` back to its base video id ``MOT17-02`` (the three
public-detector variants share ground truth and therefore the same split).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Split", "load_split", "video_base_id", "find_splits_dir"]

_DETECTOR_SUFFIX = re.compile(r"-(DPM|FRCNN|SDP)$")


def video_base_id(seq_name: str) -> str:
    """``MOT17-02-FRCNN`` -> ``MOT17-02`` (strip the detector suffix)."""
    return _DETECTOR_SUFFIX.sub("", seq_name)


def find_splits_dir() -> Path:
    """Locate the committed ``data/splits`` directory.

    Honours ``VISIONTRACK_SPLITS`` if set, otherwise walks up from this file
    (works for an editable install from the repo) and finally falls back to
    ``./data/splits`` relative to the current working directory.
    """
    env = os.environ.get("VISIONTRACK_SPLITS")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "splits"
        if candidate.is_dir():
            return candidate
    return Path("data/splits")


@dataclass(slots=True)
class Split:
    """A frozen split: base-video-id -> inclusive frame ranges per subset."""

    name: str
    protocol: str
    sequences: dict[str, dict]  # video_id -> {"length", "train":[a,b], "val":[a,b]}

    def range_for(self, seq_name: str, subset: str) -> tuple[int, int]:
        """Inclusive ``(first, last)`` frame range for a sequence and subset.

        ``subset`` is ``"train"``, ``"val"`` or ``"all"`` (the full sequence).
        """
        vid = video_base_id(seq_name)
        entry = self.sequences.get(vid)
        if entry is None:
            raise KeyError(f"{seq_name} (video {vid}) is not in split '{self.name}'")
        if subset == "all":
            return (1, int(entry["length"]))
        if subset not in ("train", "val"):
            raise ValueError(f"unknown subset: {subset!r}")
        a, b = entry[subset]
        return (int(a), int(b))

    def video_ids(self) -> list[str]:
        return list(self.sequences.keys())


def load_split(name: str = "mot17_val_half") -> Split:
    """Read a committed split JSON by name (without the ``.json`` extension)."""
    path = find_splits_dir() / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"split file not found: {path} "
            f"(set VISIONTRACK_SPLITS to the directory containing {name}.json)"
        )
    data = json.loads(path.read_text())
    return Split(
        name=data.get("name", name),
        protocol=data.get("protocol", ""),
        sequences=data["sequences"],
    )
