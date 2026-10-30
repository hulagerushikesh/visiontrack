"""Fail closed unless a version tag targets the exact successful main CI commit.

Read-only pre-publication check. No tag, release or package is created here.
Uses the GitHub Actions environment and the runner's authenticated gh CLI.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_tag(root: Path, ref: str) -> str:
    """Read metadata without importing the candidate package or its dependencies."""
    match = re.fullmatch(r"refs/tags/v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", ref)
    if match is None:
        raise ValueError("release requires a stable vX.Y.Z tag; branch dispatch is refused")
    version = ".".join(match.groups())
    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(r"(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)", metadata)
    versions = re.findall(r'^version = "([^"]+)"$', project[1] if project else "", re.M)
    module = ast.parse((root / "src/visiontrack/__init__.py").read_text(encoding="utf-8"))
    imports = [ast.literal_eval(node.value) for node in module.body
               if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
    if versions != [version] or imports != [version]:
        raise ValueError("tag, project version and import version must agree exactly")
    if not (root / f"docs/RELEASE_NOTES_{version}.md").is_file():
        raise ValueError("version-specific release notes are missing")
    return version


def successful_ci(payload: dict, repository: str, sha: str) -> dict:
    """Require the newest matching main-push run, including its latest rerun state."""
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("invalid CI response")
    matches = [run for run in runs if run.get("head_sha") == sha
               and run.get("event") == "push" and run.get("head_branch") == "main"
               and (run.get("head_repository") or {}).get("full_name") == repository]
    if not matches:
        raise ValueError("no main-push CI run found for this exact commit")
    latest = max(matches, key=lambda run: (run["id"], run.get("run_attempt", 1)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ValueError("latest CI for this commit has not completed successfully; retry after CI")
    return latest


def command(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          check=True, timeout=60).stdout.strip()


def main() -> None:
    version = validate_tag(ROOT, os.environ.get("GITHUB_REF", ""))
    sha = os.environ.get("GITHUB_SHA", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or command("git", "rev-parse", "HEAD") != sha:
        raise ValueError("checked-out HEAD must match the exact GitHub commit")
    if repository != "hulagerushikesh/visiontrack":
        raise ValueError("publication check is restricted to the configured release repository")
    payload = json.loads(command(
        "gh", "api", "--method", "GET", f"repos/{repository}/actions/workflows/ci.yml/runs",
        "-f", f"head_sha={sha}", "-f", "branch=main", "-f", "event=push",
        "-f", "per_page=100",
    ))
    run = successful_ci(payload, repository, sha)
    print(json.dumps({"version": version, "commit": sha, "ci_run_id": run["id"],
                      "ci_run_attempt": run.get("run_attempt", 1),
                      "ci_url": run["html_url"], "publication_performed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
