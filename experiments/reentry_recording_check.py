"""Inspect one local recording's technical metadata, never its tracking accuracy.

No camera is opened, media displayed, file modified, or network protocol enabled.
Reported frame rates cannot establish constant frame timing or consent. Use a
short empty-room setup clip first; populated outputs stay outside Git.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import selectors
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

from experiments.reentry_pilot_preflight import load_manifest

MAX_MEDIA_BYTES = 2 * 1024**3
MAX_OUTPUT_BYTES = 64 * 1024
PROBE_SECONDS = 20
SUFFIXES = frozenset((".mp4", ".mov", ".mkv", ".webm", ".avi"))


def _probe_output(command: list[str]) -> bytes:
    """Bound probe wall time and stdout while suppressing private stderr paths."""
    with subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    ) as process:
        try:
            deadline = time.monotonic() + PROBE_SECONDS
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise ValueError("local metadata probe timed out")
                    chunk = os.read(process.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > MAX_OUTPUT_BYTES:
                        raise ValueError("local metadata probe output exceeds limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("local metadata probe timed out")
            try:
                code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("local metadata probe timed out") from exc
            if code:
                raise ValueError("local metadata probe failed; check the file and container")
            return bytes(output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def _rate(value: object) -> Fraction | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        rate = Fraction(value)
        return rate if 0 < rate <= 1000 else None
    except (ValueError, ZeroDivisionError):
        return None


def summarize(metadata: dict) -> dict:
    """Allowlist technical fields; never copy filenames, tags, or locations."""
    streams = metadata.get("streams")
    if (
        not isinstance(streams, list)
        or len(streams) > 16
        or any(not isinstance(stream, dict) for stream in streams)
    ):
        raise ValueError("expected a bounded stream list")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ValueError("recording must have exactly one video stream")
    video = videos[0]
    width, height = video.get("width"), video.get("height")
    if any(type(value) is not int or not 0 < value <= 16384 for value in (width, height)):
        raise ValueError("invalid video dimensions")
    nominal = _rate(video.get("r_frame_rate"))
    average = _rate(video.get("avg_frame_rate"))
    audio = sum(stream.get("codec_type") == "audio" for stream in streams)
    duration = None
    container = metadata.get("format", {})
    if isinstance(container, dict):
        try:
            number = float(container.get("duration", "nan"))
            if math.isfinite(number) and 0 < number <= 86400:
                duration = number
        except (ValueError, TypeError, OverflowError):
            pass
    warnings = []
    if audio:
        warnings.append("audio_present_review_recording_settings")
    if nominal is None or average is None:
        warnings.append("frame_rate_metadata_missing")
    elif nominal != average:
        warnings.append("reported_frame_rates_differ_check_timestamps")
    if duration is None:
        warnings.append("duration_metadata_missing_or_unsupported")
    return {
        "schema_version": 1,
        "purpose": "recording_setup_metadata_only",
        "width": width,
        "height": height,
        "reported_nominal_fps": str(nominal) if nominal is not None else None,
        "reported_average_fps": str(average) if average is not None else None,
        "reported_duration_seconds": duration,
        "audio_streams": audio,
        "warnings": warnings,
        "frame_timing": "not_verified_from_metadata",
        "rights_and_consent": "not_verified_by_software",
        "scene_and_exit_visibility": "requires_human_review",
        "identity_accuracy": "not_evaluated",
        "study_admission": "not_granted",
    }


def inspect_recording(path: Path) -> dict:
    """Probe an explicitly selected regular local file, not a camera or URL."""
    if path.suffix.lower() not in SUFFIXES or not path.is_file():
        raise ValueError("select an existing local MP4, MOV, MKV, WebM, or AVI file")
    if not 0 < path.stat().st_size <= MAX_MEDIA_BYTES:
        raise ValueError("recording must be nonempty and at most 2 GiB")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        "mov,matroska,webm,avi",
        "-probesize",
        "2097152",
        "-analyzeduration",
        "5000000",
        "-show_entries",
        "stream=codec_type,width,height,r_frame_rate,avg_frame_rate:format=duration",
        "-of",
        "json",
        "-i",
        str(path.resolve()),
    ]
    try:
        raw = _probe_output(command)
    except FileNotFoundError as exc:
        raise ValueError(
            "ffprobe is not installed; install FFmpeg before this optional check"
        ) from exc
    try:
        metadata = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid local probe metadata") from exc
    if not isinstance(metadata, dict):
        raise ValueError("expected a probe metadata object")
    return summarize(metadata)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="One private local recording")
    parser.add_argument("--manifest", type=Path, help="Optional existing frozen study manifest")
    args = parser.parse_args(argv)
    try:
        result = inspect_recording(args.video)
        if args.manifest:
            manifest = load_manifest(args.manifest)
            result["manifest_sha256"] = manifest.fingerprint
            result["reported_settings_match_manifest"] = (
                result["width"] == manifest.width
                and result["height"] == manifest.height
                and _rate(result["reported_average_fps"]) == manifest.frame_rate
                and _rate(result["reported_nominal_fps"]) == manifest.frame_rate
            )
            if not result["reported_settings_match_manifest"]:
                result["warnings"].append("reported_settings_differ_from_frozen_manifest")
    except (OSError, ValueError):
        # Do not echo filesystem paths, metadata, or underlying exception details.
        print(
            "Recording check failed. Check the local file, ffprobe, and optional manifest.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
