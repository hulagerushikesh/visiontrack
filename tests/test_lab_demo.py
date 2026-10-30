"""The synthetic Lab onboarding path stays preview-first and fully verified."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from visiontrack.cli import main as cli_main
from visiontrack.lab import (
    build_initiation_trace,
    build_report_model,
    canonical_json,
    create_synthetic_lab,
    plan_synthetic_lab,
    read_failure_jsonl,
)
from visiontrack.lab import demo as demo_module


def test_synthetic_lab_plan_is_deterministic_and_read_only(tmp_path: Path) -> None:
    output = tmp_path / "onboarding"
    first = plan_synthetic_lab(output)
    second = plan_synthetic_lab(output)

    assert first == second
    assert first.output_root == output
    assert first.bundle_path.name == first.experiment_id
    assert first.report_path == first.bundle_path / "report/report.json"
    assert first.frame_count == 48
    assert first.object_count == 4
    assert first.seed == 7
    assert first.variants == ("bytetrack", "single-stage")
    assert first.detection_count > 0
    assert first.ground_truth_count > 0
    assert not output.exists()


def test_synthetic_lab_creation_produces_complete_verified_bundle(tmp_path: Path) -> None:
    output = tmp_path / "onboarding"
    plan = plan_synthetic_lab(output)

    report_path = create_synthetic_lab(output)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path == plan.report_path
    assert build_report_model(plan.bundle_path) == report
    assert (plan.bundle_path / "manifest.json").is_file()
    assert (plan.bundle_path / "source.json").is_file()
    assert (plan.bundle_path / "inputs/detections.jsonl").is_file()
    assert (plan.bundle_path / "inputs/ground_truth.jsonl").is_file()
    assert (plan.bundle_path / "comparison.json").is_file()
    assert (plan.bundle_path / "report/index.html").is_file()
    assert {variant["name"] for variant in report["variants"]} == set(plan.variants)
    assert report["decision"] == {
        "status": "not_selected",
        "accepted_variant": None,
        "reason": "requires_human_acceptance_decision",
    }
    for variant in plan.variants:
        run = plan.bundle_path / "runs" / variant
        assert (run / "run.json").is_file()
        assert (run / "tracks.jsonl").is_file()
        assert (run / "metrics.json").is_file()
        assert (run / "failures.jsonl").is_file()
        read_failure_jsonl(run / "failures.jsonl", frame_count=plan.frame_count)


def test_lab_demo_cli_previews_writes_and_refuses_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli-onboarding"
    arguments = ["lab-demo", str(output)]

    assert cli_main(arguments) == 0
    preview = capsys.readouterr()
    assert "Synthetic Reliability Lab preview" in preview.out
    assert "Preview only; nothing was written." in preview.out
    assert "bytetrack, single-stage" in preview.out
    assert not output.exists()

    assert cli_main([*arguments, "--write"]) == 0
    written = capsys.readouterr()
    assert "Created complete synthetic Reliability Lab bundle" in written.out
    assert "import report.json at /lab" in written.out
    assert output.is_dir()

    assert cli_main(arguments) == 2
    refused = capsys.readouterr()
    assert "refusing to replace existing output path" in refused.err


def test_synthetic_lab_publication_race_preserves_foreign_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "raced-output"
    original_generate = demo_module.generate_local_report

    def occupy_destination(bundle: Path) -> Path:
        report_path = original_generate(bundle)
        output.mkdir()
        (output / "foreign.txt").write_text("preserve me", encoding="utf-8")
        return report_path

    monkeypatch.setattr(demo_module, "generate_local_report", occupy_destination)

    with pytest.raises(FileExistsError, match="refusing to replace existing output path"):
        create_synthetic_lab(output)

    assert (output / "foreign.txt").read_text(encoding="utf-8") == "preserve me"
    assert not any(tmp_path.glob(".visiontrack-lab-demo-*"))


def test_initiation_demo_keeps_original_bundle_bytes_and_separate_imports(tmp_path: Path) -> None:
    original = create_synthetic_lab(tmp_path / "original").parent.parent
    report = create_synthetic_lab(tmp_path / "guided", with_initiation=True)
    bundle = report.parent.parent
    browser = bundle.parent / "try-in-browser"
    def snapshot(folder):
        return {
            str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()
        }
    assert snapshot(original) == snapshot(bundle)
    assert set(path.name for path in browser.iterdir()) == {
        "report.json", "initiation-trace.json", "START_HERE.txt",
    }
    assert (browser / "report.json").read_bytes() == report.read_bytes()
    trace = build_initiation_trace(bundle, variant="bytetrack", start=0, end=10)
    assert (browser / "initiation-trace.json").read_text() == canonical_json(trace) + "\n"
    assert trace["frames"][0]["public_track_ids"] == []
    assert trace["frames"][1]["public_track_ids"] == []
    assert trace["frames"][2]["public_track_ids"] == [1]
    guide = (browser / "START_HERE.txt").read_text()
    assert "Frame 0: ID 1: tentative, 1 hit. Public IDs: none." in guide
    assert "Frame 2: ID 1: confirmed, 3 hits" in guide
    assert "Skip Human review" in guide
    assert "not improved accuracy" in guide
    assert str(tmp_path) not in guide

    another = create_synthetic_lab(tmp_path / "repeat", with_initiation=True)
    assert snapshot(browser) == snapshot(another.parent.parent.parent / "try-in-browser")
    assert not (original.parent / "try-in-browser").exists()


def test_initiation_demo_cli_preview_lists_imports_without_writing(tmp_path, capsys) -> None:
    output = tmp_path / "with spaces"
    args = ["lab-demo", str(output), "--with-initiation"]
    assert cli_main(args) == 0
    preview = capsys.readouterr().out
    for filename in ("report.json", "initiation-trace.json", "START_HERE.txt"):
        assert str(output / "try-in-browser" / filename) in preview
    assert "frames 0–9" in preview
    assert not output.exists()
    assert cli_main([*args, "--write"]) == 0
    assert "same folder" in capsys.readouterr().out
    before = (output / "try-in-browser/initiation-trace.json").read_bytes()
    assert cli_main([*args, "--write"]) == 2
    assert "refusing to replace" in capsys.readouterr().err
    assert (output / "try-in-browser/initiation-trace.json").read_bytes() == before


def test_initiation_demo_failure_does_not_publish_partial_output(tmp_path, monkeypatch) -> None:
    def fail_trace(*args, **kwargs):
        raise ValueError("injected replay mismatch")

    from visiontrack.lab import initiation

    monkeypatch.setattr(initiation, "build_initiation_trace", fail_trace)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="replay mismatch"):
        create_synthetic_lab(output, with_initiation=True)
    assert not output.exists()
    assert not any(tmp_path.glob(".visiontrack-lab-demo-*"))


def test_initiation_demo_publication_failure_rolls_back_only_own_files(
    tmp_path, monkeypatch,
) -> None:
    output = tmp_path / "failed-publication"
    original_rename = Path.rename

    def fail_browser_publication(path, target):
        if path.name == "try-in-browser":
            (output / "foreign.txt").write_text("preserve me")
            raise OSError("injected publication failure")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_browser_publication)
    with pytest.raises(OSError, match="publication failure"):
        create_synthetic_lab(output, with_initiation=True)
    assert list(output.iterdir()) == [output / "foreign.txt"]
    assert (output / "foreign.txt").read_text() == "preserve me"
    assert not any(tmp_path.glob(".visiontrack-lab-demo-*"))
