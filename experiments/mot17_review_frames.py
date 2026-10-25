"""Acquire only the fixed first-switch review window from the official ZIP.

Preview is offline. --write uses bounded, conditional HTTP ranges, never a full
archive download or extractall. Local non-commercial research only; no upload,
tracker execution, identity inference or permission to publish dataset pixels.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from experiments.mot17_case_baseline import sha, write_json
from experiments.mot17_case_intake import SEQUENCE, raw_file, require, source_members

URL = "https://motchallenge.net/data/MOT17.zip"
WINDOW = (36, 57)  # fixed by the v2 prior-match rule, not selected from pixels
PREFIX = f"MOT17/train/{SEQUENCE}"
MEMBERS = tuple(f"{PREFIX}/img1/{frame:06d}.jpg"
                for frame in range(WINDOW[0], WINDOW[1] + 1))
MAX_TRANSFER = 32 * 1024 * 1024
MAX_READ = 8 * 1024 * 1024
MAX_REQUESTS = 128
MAX_MEMBER = 8 * 1024 * 1024


class RangeReader(io.RawIOBase):
    """Seekable remote bytes with a fixed object identity and hard transfer caps."""

    def __init__(self):
        super().__init__()
        with urlopen(Request(URL, method="HEAD", headers={"Accept-Encoding": "identity"}),
                     timeout=30) as response:
            require(response.status == 200 and response.geturl() == URL,
                    "official archive HEAD required without redirects")
            require(response.headers.get("Accept-Ranges") == "bytes", "range support required")
            self.size = int(response.headers["Content-Length"])
            self.etag = response.headers.get("ETag", "")
        require(0 < self.size < 16 * 1024**3, "unexpected archive size")
        require(self.etag.startswith('"') and self.etag.endswith('"'), "strong ETag required")
        self.position = self.transferred = self.requests = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        require(whence in (0, 1, 2), "invalid seek origin")
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        require(0 <= position <= self.size, "seek outside archive")
        self.position = position
        return position

    def read(self, size=-1):
        size = self.size - self.position if size is None or size < 0 else size
        size = min(size, self.size - self.position)
        if not size:
            return b""
        require(size <= MAX_READ and self.transferred + size <= MAX_TRANSFER,
                "archive transfer budget exceeded")
        require(self.requests < MAX_REQUESTS, "archive request budget exceeded")
        start, end = self.position, self.position + size - 1
        headers = {"Range": f"bytes={start}-{end}", "If-Match": self.etag,
                   "Accept-Encoding": "identity"}
        self.requests += 1
        with urlopen(Request(URL, headers=headers), timeout=30) as response:
            require(response.status == 206 and response.geturl() == URL,
                    "exact partial response required; full download refused")
            require(response.headers.get("ETag") == self.etag, "archive object changed")
            require(response.headers.get("Content-Range") == f"bytes {start}-{end}/{self.size}",
                    "response range mismatch")
            require(response.headers.get("Content-Encoding", "identity") == "identity",
                    "encoded response refused")
            require(int(response.headers["Content-Length"]) == size, "response length mismatch")
            payload = response.read(size + 1)
        require(len(payload) == size, "truncated or oversized partial response")
        self.transferred += size
        self.position += size
        return payload


def read_member(archive, name, maximum=MAX_MEMBER):
    entries = [entry for entry in archive.infolist() if entry.filename == name]
    require(len(entries) == 1, "missing or duplicate selected ZIP member")
    entry = entries[0]
    require(0 < entry.file_size <= maximum and entry.compress_size <= MAX_READ,
            "selected ZIP member exceeds budget")
    require(not entry.flag_bits & 1 and entry.compress_type in (ZIP_STORED, ZIP_DEFLATED),
            "unsupported ZIP member encoding")
    with archive.open(entry) as stream:
        payload = stream.read(maximum + 1)
    require(len(payload) == entry.file_size, "selected ZIP member length mismatch")
    # ZipFile checks the member CRC on the complete bounded read. CRC is not
    # cryptographic authenticity; HTTPS, object identity and per-file hashes
    # document acquisition, not an independently published image checksum.
    return payload


def check_jpeg(payload):
    from PIL import Image

    require(payload.startswith(b"\xff\xd8"), "JPEG source required")
    with Image.open(io.BytesIO(payload)) as image:
        require(image.format == "JPEG" and image.size == (1920, 1080),
                "unexpected source image format/dimensions")
        image.verify()


def preview():
    return dict(schema="visiontrack.mot17-review-frames/v1", sequence=SEQUENCE,
                source_url=URL, source_window=list(WINDOW), members=list(MEMBERS),
                purpose="local non-commercial first-switch visual/reference review",
                dataset_license="CC BY-NC-SA 3.0; additional rights may apply",
                license_url="https://creativecommons.org/licenses/by-nc-sa/3.0/",
                attribution="MOTChallenge; Milan et al., MOT16 (2016), arXiv:1603.00831",
                public_redistribution_approved=False, independent_review_completed=False,
                transfer_budget_bytes=MAX_TRANSFER, request_budget=MAX_REQUESTS)


def acquire(labels, output):
    root = Path(__file__).resolve().parents[1]
    require(not output.exists() and not output.is_symlink(), "new output directory required")
    require(output.parent.is_dir(), "existing output parent required")
    require(not output.resolve().is_relative_to(root),
            "dataset pixels must stay outside repository")
    labels_before = sha(labels)
    annotations = source_members(raw_file(labels))
    output.mkdir()
    write_json(output / "method.json", dict(
        **preview(), source_sha256=sha(Path(__file__)), labels_sha256=labels_before,
        annotation_sha256={n: hashlib.sha256(p).hexdigest() for n, p in annotations.items()}))
    try:
        records = {}
        with RangeReader() as remote, ZipFile(remote) as archive:
            for suffix, expected in annotations.items():
                payload = read_member(archive, f"{PREFIX}/{suffix}")
                require(payload == expected, "full archive annotations differ from admitted labels")
            for member in MEMBERS:
                payload = read_member(archive, member, maximum=2 * 1024 * 1024)
                check_jpeg(payload)
                name = Path(member).name
                with (output / name).open("xb") as stream:
                    stream.write(payload)
                records[name] = dict(source_member=member, bytes=len(payload),
                                     sha256=hashlib.sha256(payload).hexdigest())
                print(f"Acquired source frame {int(Path(member).stem)}", flush=True)
            acquisition = dict(archive_size=remote.size, archive_etag=remote.etag,
                               transferred_bytes=remote.transferred, requests=remote.requests)
        require(sha(labels) == labels_before, "local annotation archive changed")
        write_json(output / "acquisition.json", dict(
            **acquisition, files=records, annotation_members_exact=True,
            full_archive_sha256=None, independently_published_image_hashes=False,
            scope="22 local source JPEGs only; no independent visual review or tracker change"))
        write_json(output / "manifest.json", {
            p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(output.iterdir()) if p.is_file()})
    except Exception as error:
        write_json(output / "failure.json", dict(type=type(error).__name__, message=str(error),
                                                acquisition_complete=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(json.dumps(preview(), indent=2))
    else:
        require(args.labels is not None and args.output is not None, "labels and output required")
        acquire(args.labels, args.output)


if __name__ == "__main__":
    main()
