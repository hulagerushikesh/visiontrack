"""The frozen 0.3.0 candidate must remain truthful until publication."""

from __future__ import annotations

import re
from pathlib import Path

import visiontrack

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs/RELEASE_NOTES_0.3.0.md"


def test_frozen_release_scope_is_linked_and_candidate_versions_agree() -> None:
    notes = NOTES.read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readiness = (ROOT / "docs/RELEASE_READINESS.md").read_text(encoding="utf-8")
    navigation = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "Scope status: **frozen" in notes
    assert "Release status: **published on 2026-10-06**" in notes
    assert "Persistent recognition" in notes
    assert "Track IDs are temporary labels" in notes
    package_version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    assert package_version is not None
    assert package_version.group(1) == visiontrack.__version__ == "0.3.0"
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
    assert "[x] Bump both package version declarations" in notes
    assert "[x] Create and push `v0.3.0`" in notes


def test_release_candidate_uses_current_license_metadata() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'requires = ["setuptools>=77", "wheel"]' in project
    assert 'license = "MIT"' in project
    assert 'license-files = ["LICENSE"]' in project
    assert "License :: OSI Approved :: MIT License" not in project


def test_documentation_policy_has_no_missing_link_allowlist() -> None:
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert "A strict build is the release" in config
    assert "any new missing target must fail" in config
    assert "not_found: warn" in config


def test_release_workflows_use_node24_compatible_action_majors() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    workflows = ci + release

    assert "actions/checkout@v7" in ci
    assert "actions/setup-python@v7" in ci
    assert "actions/setup-node@v7" in ci
    assert "actions/checkout@v7" in release
    assert "actions/setup-python@v7" in release
    assert "actions/upload-artifact@v7" in release
    assert "actions/download-artifact@v8" in release
    for deprecated in (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/setup-node@v4",
        "actions/upload-artifact@v4",
        "actions/download-artifact@v4",
    ):
        assert deprecated not in workflows
