"""Offline transport/admission tests; never download training pixels in CI."""
import io
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from experiments import mot17_review_frames as frames


class Response(io.BytesIO):
    def __init__(self, payload=b"", status=200, headers=None, url=frames.URL):
        super().__init__(payload)
        self.status, self.headers, self.url = status, headers or {}, url

    def geturl(self):
        return self.url


def transport(payload, monkeypatch, alter=None):
    calls = []

    def open_url(request, timeout):
        assert timeout == 30 and request.full_url == frames.URL
        calls.append(request)
        if request.get_method() == "HEAD":
            return Response(headers={"Content-Length": str(len(payload)),
                                     "ETag": '"fixed-object"', "Accept-Ranges": "bytes"})
        assert request.headers["If-match"] == '"fixed-object"'
        assert request.headers["Accept-encoding"] == "identity"
        start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["Range"]).groups())
        response = Response(payload[start:end + 1], status=206, headers={
            "Content-Range": f"bytes {start}-{end}/{len(payload)}",
            "Content-Length": str(end - start + 1), "ETag": '"fixed-object"'})
        return alter(response) if alter else response

    monkeypatch.setattr(frames, "urlopen", open_url)
    return calls


def test_range_reader_seek_zip_crc_and_no_full_archive_read(monkeypatch):
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("selected", b"exact selected bytes")
        archive.writestr("unselected", b"do not extract")
    calls = transport(output.getvalue(), monkeypatch)
    with frames.RangeReader() as remote, ZipFile(remote) as archive:
        assert frames.read_member(archive, "selected") == b"exact selected bytes"
        assert remote.transferred <= frames.MAX_TRANSFER
        assert remote.requests == len(calls) - 1
        assert remote.readable() and remote.seekable()
        remote.seek(0)
        assert remote.read(4) == b"PK\x03\x04"
        remote.seek(-4, 2)
        assert remote.tell() == len(output.getvalue()) - 4
        remote.seek(4, 1)
        assert remote.read() == b""


@pytest.mark.parametrize("field,value,message", [
    ("status", 200, "partial response"),
    ("url", "https://other.example/archive", "partial response"),
    ("ETag", '"changed"', "object changed"),
    ("Content-Range", "bytes 0-1/10", "range mismatch"),
    ("Content-Length", "99", "length mismatch"),
    ("Content-Encoding", "gzip", "encoded response"),
])
def test_response_must_be_exact_conditional_range(monkeypatch, field, value, message):
    def alter(response):
        if field in ("status", "url"):
            setattr(response, field, value)
        else:
            response.headers[field] = value
        return response

    transport(b"0123456789", monkeypatch, alter)
    with frames.RangeReader() as remote, pytest.raises(ValueError, match=message):
        remote.read(3)


def test_truncated_response_is_not_accepted(monkeypatch):
    def truncate(response):
        return Response(b"x", 206, response.headers)

    transport(b"0123456789", monkeypatch, truncate)
    with frames.RangeReader() as remote, pytest.raises(ValueError, match="truncated"):
        remote.read(3)


def test_transport_budgets_and_seeks_fail_before_request(monkeypatch):
    calls = transport(b"0123456789", monkeypatch)
    with frames.RangeReader() as remote:
        for args in ((-1,), (11,), (0, 3)):
            with pytest.raises(ValueError, match="seek"):
                remote.seek(*args)
        monkeypatch.setattr(frames, "MAX_READ", 2)
        with pytest.raises(ValueError, match="transfer budget"):
            remote.read(3)
        monkeypatch.setattr(frames, "MAX_TRANSFER", 1)
        with pytest.raises(ValueError, match="transfer budget"):
            remote.read(2)
        monkeypatch.setattr(frames, "MAX_REQUESTS", 0)
        with pytest.raises(ValueError, match="request budget"):
            remote.read(1)
    assert len(calls) == 1  # HEAD only


def test_weak_etag_is_refused(monkeypatch):
    monkeypatch.setattr(frames, "urlopen", lambda *a, **k: Response(headers={
        "Accept-Ranges": "bytes", "Content-Length": "100", "ETag": 'W/"weak"'}))
    with pytest.raises(ValueError, match="strong ETag"):
        frames.RangeReader()


def test_missing_duplicate_or_oversized_zip_member_refused():
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("duplicate", b"a")
        with pytest.warns(UserWarning):
            archive.writestr("duplicate", b"b")
        archive.writestr("large", b"abcd")
    with ZipFile(output) as archive:
        for name in ("missing", "duplicate"):
            with pytest.raises(ValueError, match="missing or duplicate"):
                frames.read_member(archive, name)
        with pytest.raises(ValueError, match="exceeds budget"):
            frames.read_member(archive, "large", maximum=3)


def test_preview_is_fixed_offline_no_review_or_distribution_claim(monkeypatch):
    monkeypatch.setattr(frames, "urlopen", lambda *a, **k: pytest.fail("preview made network call"))
    value = frames.preview()
    assert value["source_window"] == [36, 57]
    assert len(value["members"]) == 22
    assert value["members"][0].endswith("/000036.jpg")
    assert not value["public_redistribution_approved"]
    assert not value["independent_review_completed"]


def test_existing_or_repository_output_refused_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "urlopen", lambda *a, **k: pytest.fail("network call"))
    with pytest.raises(ValueError, match="new output"):
        frames.acquire(tmp_path / "labels", tmp_path)
    with pytest.raises(ValueError, match="outside repository"):
        frames.acquire(tmp_path / "labels", frames.Path(__file__).parent / "new-pixel-output")


def test_successful_acquisition_uses_exact_annotations_and_22_members(tmp_path, monkeypatch):
    annotations = {"seqinfo.ini": b"metadata", "det/det.txt": b"detections", "gt/gt.txt": b"GT"}
    payload = io.BytesIO()
    with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
        for suffix, raw in annotations.items():
            archive.writestr(f"{frames.PREFIX}/{suffix}", raw)
        for member in frames.MEMBERS:
            archive.writestr(member, b"synthetic transport fixture, not real image evidence")
    transport(payload.getvalue(), monkeypatch)
    monkeypatch.setattr(frames, "source_members", lambda raw: annotations)
    monkeypatch.setattr(frames, "check_jpeg", lambda raw: None)
    labels = tmp_path / "labels.zip"
    labels.write_bytes(b"pinned synthetic labels")
    output = tmp_path / "acquired"
    frames.acquire(labels, output)
    receipt = json.loads((output / "acquisition.json").read_text())
    assert len(receipt["files"]) == 22
    assert receipt["annotation_members_exact"]
    assert receipt["full_archive_sha256"] is None
    assert not receipt["independently_published_image_hashes"]
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest) == 24
    for name, entry in manifest.items():
        assert frames.sha(output / name) == entry["sha256"]
    with pytest.raises(ValueError, match="new output"):
        frames.acquire(labels, output)


def test_different_annotations_retain_failure_receipt_without_images(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr(f"{frames.PREFIX}/seqinfo.ini", b"different")
    transport(payload.getvalue(), monkeypatch)
    monkeypatch.setattr(frames, "source_members", lambda raw: {"seqinfo.ini": b"admitted"})
    labels = tmp_path / "labels"
    labels.write_bytes(b"fixture")
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="annotations differ"):
        frames.acquire(labels, output)
    assert (output / "failure.json").is_file()
    assert not (output / "manifest.json").exists()
    assert not list(output.glob("*.jpg"))


def test_non_jpeg_or_wrong_dimensions_refused():
    from PIL import Image

    with pytest.raises(ValueError, match="JPEG source"):
        frames.check_jpeg(b"not a JPEG")
    raw = io.BytesIO()
    Image.new("RGB", (4, 3)).save(raw, format="JPEG")
    with pytest.raises(ValueError, match="dimensions"):
        frames.check_jpeg(raw.getvalue())
