"""Prevent publication from a branch, mismatched version or unverified commit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_release
from scripts.check_release import successful_ci, validate_tag

REPO = "hulagerushikesh/visiontrack"
SHA = "a" * 40


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    (tmp_path / "src/visiontrack").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools"]\n\n'
        '[project]\nname = "visiontrack-mot"\nversion = "0.4.0"\n\n'
        '[tool.example]\nversion = "99.0.0"\n', encoding="utf-8")
    (tmp_path / "src/visiontrack/__init__.py").write_text(
        '__version__ = "0.4.0"\n', encoding="utf-8")
    (tmp_path / "docs/RELEASE_NOTES_0.4.0.md").write_text("Release scope\n", encoding="utf-8")
    return tmp_path


def run(**changes) -> dict:
    return {"id": 10, "head_sha": SHA, "head_branch": "main", "event": "push",
            "head_repository": {"full_name": REPO}, "status": "completed",
            "conclusion": "success", "run_attempt": 1,
            "html_url": "https://github.com/example/actions/runs/10", **changes}


def test_matching_candidate_tag_passes_without_importing_package(candidate: Path) -> None:
    with (candidate / "src/visiontrack/__init__.py").open("a", encoding="utf-8") as stream:
        stream.write('raise RuntimeError("must never execute candidate code")\n')
    assert validate_tag(candidate, "refs/tags/v0.4.0") == "0.4.0"


@pytest.mark.parametrize("ref", ["", "refs/heads/main", "refs/tags/0.4.0",
                                     "refs/tags/v0.4.0rc1", "refs/tags/v00.4.0"])
def test_branch_and_nonstable_refs_are_refused(candidate: Path, ref: str) -> None:
    with pytest.raises(ValueError, match="stable vX.Y.Z tag"):
        validate_tag(candidate, ref)


@pytest.mark.parametrize("file,text", [
    ("pyproject.toml", '[project]\nversion = "0.3.0"\n'),
    ("src/visiontrack/__init__.py", '__version__ = "0.3.0"\n'),
])
def test_mismatched_metadata_is_refused(candidate: Path, file: str, text: str) -> None:
    (candidate / file).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="agree exactly"):
        validate_tag(candidate, "refs/tags/v0.4.0")


def test_missing_notes_are_refused(candidate: Path) -> None:
    (candidate / "docs/RELEASE_NOTES_0.4.0.md").unlink()
    with pytest.raises(ValueError, match="release notes"):
        validate_tag(candidate, "refs/tags/v0.4.0")


def test_exact_successful_main_push_ci_is_accepted() -> None:
    assert successful_ci({"workflow_runs": [run()]}, REPO, SHA)["id"] == 10


@pytest.mark.parametrize("changes", [
    {"head_sha": "b" * 40}, {"event": "pull_request"}, {"head_branch": "feature"},
    {"head_repository": {"full_name": "someone/fork"}},
    {"head_repository": None},
])
def test_unrelated_ci_cannot_authorize_publication(changes: dict) -> None:
    with pytest.raises(ValueError, match="no main-push CI"):
        successful_ci({"workflow_runs": [run(**changes)]}, REPO, SHA)


@pytest.mark.parametrize("status,conclusion", [
    ("in_progress", None), ("queued", None), ("completed", "failure"),
    ("completed", "cancelled"), ("completed", "skipped"),
])
def test_later_failed_or_pending_ci_cannot_fall_back_to_old_success(
    status: str, conclusion: str | None,
) -> None:
    with pytest.raises(ValueError, match="not completed successfully"):
        successful_ci({"workflow_runs": [run(id=11, status=status, conclusion=conclusion),
                                         run()]}, REPO, SHA)


def test_pending_rerun_cannot_reuse_previous_attempt_success() -> None:
    with pytest.raises(ValueError, match="not completed successfully"):
        successful_ci({"workflow_runs": [run(), run(run_attempt=2, status="in_progress",
                                                   conclusion=None)]}, REPO, SHA)


@pytest.mark.parametrize("payload", [{}, {"workflow_runs": None}, {"workflow_runs": []}])
def test_missing_ci_is_refused(payload: dict) -> None:
    with pytest.raises(ValueError):
        successful_ci(payload, REPO, SHA)


def test_entrypoint_checks_checkout_and_exact_api_query_before_receipt(
    candidate: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setattr(check_release, "ROOT", candidate)
    monkeypatch.setenv("GITHUB_REF", "refs/tags/v0.4.0")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    calls = []

    def command(*args: str) -> str:
        calls.append(args)
        return SHA if args[0] == "git" else json.dumps({"workflow_runs": [run()]})

    monkeypatch.setattr(check_release, "command", command)
    check_release.main()
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["commit"] == SHA and receipt["publication_performed"] is False
    assert receipt["version"] == "0.4.0" and receipt["ci_run_id"] == 10
    assert calls == [
        ("git", "rev-parse", "HEAD"),
        ("gh", "api", "--method", "GET", f"repos/{REPO}/actions/workflows/ci.yml/runs",
         "-f", f"head_sha={SHA}", "-f", "branch=main", "-f", "event=push",
         "-f", "per_page=100"),
    ]


@pytest.mark.parametrize("sha,checkout,repo", [
    ("not-a-sha", SHA, REPO), (SHA, "b" * 40, REPO), (SHA, SHA, "someone/fork"),
])
def test_invalid_execution_context_cannot_query_ci(
    candidate: Path, monkeypatch: pytest.MonkeyPatch, sha: str, checkout: str, repo: str,
) -> None:
    monkeypatch.setattr(check_release, "ROOT", candidate)
    monkeypatch.setenv("GITHUB_REF", "refs/tags/v0.4.0")
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("GITHUB_REPOSITORY", repo)

    def command(*args: str) -> str:
        assert args == ("git", "rev-parse", "HEAD"), "invalid context reached network"
        return checkout

    monkeypatch.setattr(check_release, "command", command)
    with pytest.raises(ValueError):
        check_release.main()


def test_release_workflow_gates_build_and_publication() -> None:
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/release.yml").read_text())
    steps = workflow["jobs"]["build"]["steps"]
    guard = next(i for i, step in enumerate(steps)
                 if step.get("run") == "python scripts/check_release.py")
    build = next(i for i, step in enumerate(steps) if "python -m build" in step.get("run", ""))
    assert guard < build
    assert steps[guard]["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert workflow["permissions"]["actions"] == "read"
    assert workflow["jobs"]["publish"]["needs"] == "build"
