"""The frozen 0.3.0 scope must remain truthful until the release commit."""

from __future__ import annotations

import re
from pathlib import Path

import visiontrack

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs/RELEASE_NOTES_0.3.0.md"


def test_frozen_release_scope_is_linked_and_does_not_prematurely_bump_version() -> None:
    notes = NOTES.read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readiness = (ROOT / "docs/RELEASE_READINESS.md").read_text(encoding="utf-8")
    navigation = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "Scope status: **frozen" in notes
    assert "Release status: **not yet published**" in notes
    assert "Persistent recognition" in notes
    assert "Track IDs are temporary labels" in notes
    package_version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    assert package_version is not None
    assert package_version.group(1) == visiontrack.__version__ == "0.2.0"
    assert "RELEASE_NOTES_0.3.0.md" in readiness
    assert "RELEASE_NOTES_0.3.0.md" in navigation


def test_release_scope_names_stable_surfaces_and_remaining_gates() -> None:
    notes = NOTES.read_text(encoding="utf-8")
    for surface in (
        "Reliability Lab v1",
        "visiontrack lab-demo",
        "visiontrack lab-evidence",
        "visiontrack lab-decision",
        "visiontrack lab-decision-import",
        "visiontrack lab-playback",
        "visiontrack parity-contract",
        "visiontrack.tracker-parity/v1",
    ):
        assert surface in notes
    assert "[ ] Bump both package version declarations" in notes
    assert "[ ] Create and push `v0.3.0`" in notes
