"""Read-only source and timing check for the publisher-hosted HVSD V1 clips.

This checks local bytes and decode metadata. It does not certify the labels,
privacy, camera geometry, or the quality of any detector or tracker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from statistics import median
from zipfile import ZipFile

ARCHIVE_SHA256 = "e32476f77547bf3498835e74b78317794ab1ba78f78023b647f2d02f9a89e9c0"
MEMBERS = ("Dataset/day.mp4", "Dataset/night.mp4", "Dataset/rain.mp4")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), "regular non-symlink file required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_member(archive: ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(name) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_probe(payload: dict) -> dict:
    streams = payload.get("streams", [])
    frames = payload.get("frames", [])
    require(len(streams) == 1 and len(frames) >= 2, "one video stream and >=2 frames required")
    stream = streams[0]
    width, height = int(stream["width"]), int(stream["height"])
    require(width > 0 and height > 0, "invalid stream dimensions")
    require(all(int(f["width"]) == width and int(f["height"]) == height for f in frames),
            "frame dimensions changed")
    pts = [float(frame["best_effort_timestamp_time"]) for frame in frames]
    require(all(0 <= value < float("inf") for value in pts), "invalid frame timestamp")
    gaps = [right - left for left, right in zip(pts, pts[1:], strict=False)]
    require(all(gap > 0 for gap in gaps), "non-increasing frame timestamp")
    nominal = median(gaps)
    reported = int(stream["nb_frames"]) if "nb_frames" in stream else None
    return {
        "width": width,
        "height": height,
        "decoded_frames": len(frames),
        "stream_reported_frames": reported,
        "stream_count_matches_decoded": reported is None or reported == len(frames),
        "first_pts_seconds": pts[0],
        "last_pts_seconds": pts[-1],
        "median_frame_gap_seconds": round(nominal, 6),
        "min_frame_gap_seconds": round(min(gaps), 6),
        "max_frame_gap_seconds": round(max(gaps), 6),
        "gaps_over_5pct_from_median": sum(abs(gap - nominal) > 0.05 * nominal for gap in gaps),
    }


def probe_video(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
               "-show_frames", "-show_entries",
               "stream=width,height,nb_frames:frame=best_effort_timestamp_time,width,height",
               "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)
    return summarize_probe(json.loads(result.stdout))


def audit(archive_path: Path, video_dir: Path) -> dict:
    require(sha256_file(archive_path) == ARCHIVE_SHA256, "HVSD archive fingerprint mismatch")
    clips = []
    with ZipFile(archive_path) as archive:
        names = [item.filename for item in archive.infolist()]
        require(len(names) == len(set(names)), "duplicate archive members")
        require(set(names) == set(MEMBERS) | {"Dataset/"}, "unexpected archive members")
        for name in MEMBERS:
            video_path = video_dir / Path(name).name
            video_hash = sha256_file(video_path)
            require(video_hash == sha256_member(archive, name), f"source/video mismatch: {name}")
            item = archive.getinfo(name)
            require(video_path.stat().st_size == item.file_size, f"size mismatch: {name}")
            clip = {"member": name, "bytes": item.file_size, "sha256": video_hash}
            clip.update(probe_video(video_path))
            # Keep a discrepant publisher clip visible in the source report;
            # downstream protocols must use decoded timestamps, not header FPS.
            clips.append(clip)
    return {
        "dataset": "HVSD V1",
        "archive_sha256": ARCHIVE_SHA256,
        "clips": clips,
        "independent_dense_ground_truth_present": False,
        "tracking_outcome_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--video-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive, args.video_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
