"""Setup checks need no camera, real people, dataset, or installed FFmpeg."""

import copy
import json
import sys
from pathlib import Path

import pytest

from experiments import reentry_recording_check as check


def _metadata():
    return {
        "streams": [
            {
                "codec_type": "video",
                "width": 1280,
                "height": 720,
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "tags": {"location": "PRIVATE LOCATION"},
            }
        ],
        "format": {"duration": "2.5", "filename": "/private/owner.mov"},
    }


def test_summary_is_allowlisted_deterministic_and_does_not_admit_a_study():
    metadata = _metadata()
    before = copy.deepcopy(metadata)
    result = check.summarize(metadata)
    assert result == check.summarize(metadata)
    assert metadata == before
    assert result["reported_average_fps"] == result["reported_nominal_fps"] == "30"
    assert result["reported_duration_seconds"] == 2.5
    assert result["audio_streams"] == 0
    assert result["warnings"] == []
    assert result["frame_timing"] == "not_verified_from_metadata"
    assert result["rights_and_consent"] == "not_verified_by_software"
    assert result["identity_accuracy"] == "not_evaluated"
    assert result["study_admission"] == "not_granted"
    assert "PRIVATE" not in json.dumps(result)
    assert "/private" not in json.dumps(result)


def test_audio_and_unequal_fractional_rates_are_visible_not_corrected():
    metadata = _metadata()
    metadata["streams"].append({"codec_type": "audio"})
    metadata["streams"][0]["avg_frame_rate"] = "30000/1001"
    result = check.summarize(metadata)
    assert result["reported_average_fps"] == "30000/1001"
    assert result["audio_streams"] == 1
    assert result["warnings"] == [
        "audio_present_review_recording_settings",
        "reported_frame_rates_differ_check_timestamps",
    ]


@pytest.mark.parametrize(
    "value", [None, True, 30, "0/0", "NaN", "Infinity", "-1", "1001", "1" * 65]
)
def test_missing_or_invalid_rates_remain_unknown(value):
    metadata = _metadata()
    metadata["streams"][0]["avg_frame_rate"] = value
    result = check.summarize(metadata)
    assert result["reported_average_fps"] is None
    assert "frame_rate_metadata_missing" in result["warnings"]


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "-2", "0", "86401", {}])
def test_invalid_duration_does_not_become_zero_or_a_claim(value):
    metadata = _metadata()
    metadata["format"]["duration"] = value
    result = check.summarize(metadata)
    assert result["reported_duration_seconds"] is None
    assert "duration_metadata_missing_or_unsupported" in result["warnings"]


@pytest.mark.parametrize("streams", [None, [], [None], [{}], [{"codec_type": "video"}] * 17])
def test_invalid_or_ambiguous_streams_rejected(streams):
    with pytest.raises(ValueError):
        check.summarize({"streams": streams})


@pytest.mark.parametrize("width", [True, 0, -1, 16385, "1280", None])
def test_invalid_dimensions_rejected(width):
    metadata = _metadata()
    metadata["streams"][0]["width"] = width
    with pytest.raises(ValueError, match="dimensions"):
        check.summarize(metadata)


def test_probe_command_is_local_read_only_and_no_file_modified(tmp_path, monkeypatch):
    path = tmp_path / "PRIVATE video.MOV"
    path.write_bytes(b"synthetic placeholder")
    calls = []

    def probe(command):
        calls.append(command)
        return json.dumps(_metadata()).encode()

    monkeypatch.setattr(check, "_probe_output", probe)
    assert check.inspect_recording(path)["width"] == 1280
    command = calls[0]
    assert command[command.index("-protocol_whitelist") + 1] == "file"
    assert command[command.index("-format_whitelist") + 1] == "mov,matroska,webm,avi"
    assert command[-2:] == ["-i", str(path.resolve())]
    assert "tags" not in command[command.index("-show_entries") + 1]
    assert path.read_bytes() == b"synthetic placeholder"
    assert list(tmp_path.iterdir()) == [path]
    for bad in (tmp_path, tmp_path / "missing.mp4", Path("https://example.com/test.mp4")):
        with pytest.raises(ValueError):
            check.inspect_recording(bad)
    empty = tmp_path / "empty.mp4"
    empty.touch()
    with pytest.raises(ValueError, match="nonempty"):
        check.inspect_recording(empty)
    monkeypatch.setattr(check, "MAX_MEDIA_BYTES", 1)
    with pytest.raises(ValueError, match="2 GiB"):
        check.inspect_recording(path)
    assert len(calls) == 1


def test_probe_process_limits_errors_and_timeout(monkeypatch):
    assert check._probe_output([sys.executable, "-c", "print('ok')"]).strip() == b"ok"
    with pytest.raises(ValueError, match="failed"):
        check._probe_output([sys.executable, "-c", "raise SystemExit(1)"])
    monkeypatch.setattr(check, "MAX_OUTPUT_BYTES", 10)
    with pytest.raises(ValueError, match="output exceeds"):
        check._probe_output([sys.executable, "-c", "print('x' * 100)"])
    monkeypatch.setattr(check, "PROBE_SECONDS", 0.05)
    with pytest.raises(ValueError, match="timed out"):
        check._probe_output([sys.executable, "-c", "import time; time.sleep(2)"])


def test_cli_optional_manifest_comparison_does_not_prove_timing(monkeypatch, capsys):
    result = check.summarize(_metadata())
    monkeypatch.setattr(check, "inspect_recording", lambda path: copy.deepcopy(result))
    manifest = (
        Path(__file__).parents[1] / "experiments/examples/reentry_pilot_manifest.example.json"
    )
    assert check.main(["--video", "/private/test.mp4", "--manifest", str(manifest)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["reported_settings_match_manifest"]
    assert output["frame_timing"] == "not_verified_from_metadata"
    result["reported_average_fps"] = "30000/1001"
    assert check.main(["--video", "/private/test.mp4", "--manifest", str(manifest)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert not output["reported_settings_match_manifest"]
    assert "reported_settings_differ_from_frozen_manifest" in output["warnings"]


def test_cli_redacts_failure_details(monkeypatch, capsys):
    def fail(path):
        raise OSError("/private/SECRET/owner.mp4")

    monkeypatch.setattr(check, "inspect_recording", fail)
    assert check.main(["--video", "/private/SECRET/owner.mp4"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "SECRET" not in output.err
    assert "Recording check failed" in output.err


@pytest.mark.parametrize("raw", [b"not json", b"[]", b'{"streams":null}'])
def test_malformed_probe_output_rejected(tmp_path, monkeypatch, raw):
    path = tmp_path / "test.mp4"
    path.write_bytes(b"synthetic")
    monkeypatch.setattr(check, "_probe_output", lambda command: raw)
    with pytest.raises(ValueError):
        check.inspect_recording(path)


def test_missing_ffprobe_has_actionable_api_error(tmp_path, monkeypatch):
    path = tmp_path / "test.mp4"
    path.write_bytes(b"synthetic")

    def missing(command):
        raise FileNotFoundError("private details")

    monkeypatch.setattr(check, "_probe_output", missing)
    with pytest.raises(ValueError, match="install FFmpeg"):
        check.inspect_recording(path)
