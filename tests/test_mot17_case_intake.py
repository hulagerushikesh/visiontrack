"""Tiny authored annotations test intake mechanics, not real tracking quality."""
import hashlib
import io
from zipfile import ZipFile

import numpy as np
import pytest

from experiments import mot17_case_intake as intake


def members():
    return {
        "seqinfo.ini": (b"[Sequence]\nname=MOT17-04-FRCNN\nseqLength=1050\n"
                        b"imWidth=1920\nimHeight=1080\nframeRate=30\n"),
        # Unsorted rows exercise the cache writer's frame-stream ordering.
        "det/det.txt": b"3,-1,12.2,20,10,30,0.8\n1,-1,10,20,10,30,1\n",
        "gt/gt.txt": b"3,1,12,20,10,30,1,1,0.5\n1,2,10,20,10,30,0,7,0\n",
    }


def npz(arrays, **changes):
    values = {**intake.METADATA, **arrays, **changes}
    stream = io.BytesIO()
    np.savez_compressed(stream, **values)
    return stream.getvalue()


def test_cache_matches_at_stored_precision_without_tolerance():
    arrays = intake.reference_arrays(members())
    assert arrays["det_frame"].tolist() == [1, 3]
    assert arrays["det_xyxy"][1, 2] == np.float32(22.2)
    assert arrays["gt_conf"].tolist() == [0, 1]  # ignore rows are retained
    intake.verify_cache(npz(arrays), arrays)
    altered = arrays["det_xyxy"].copy()
    altered[0, 0] = np.nextafter(altered[0, 0], np.float32(np.inf))
    with pytest.raises(ValueError, match="cache/source mismatch: det_xyxy"):
        intake.verify_cache(npz(arrays, det_xyxy=altered), arrays)


@pytest.mark.parametrize("change", ["dtype", "metadata", "metadata_type", "shape", "nan", "extra"])
def test_cache_corruption_refused(change):
    arrays = intake.reference_arrays(members())
    modifications = {
        "dtype": dict(gt_id=arrays["gt_id"].astype(np.int64)),
        "metadata": dict(frame_rate=25),
        "metadata_type": dict(schema_version=True),
        "shape": dict(det_frame=arrays["det_frame"].reshape(2, 1)),
        "nan": dict(det_score=np.array([np.nan, 0.8], dtype=np.float32)),
        "extra": dict(emb=np.zeros((2, 3))),
    }
    with pytest.raises(ValueError):
        intake.verify_cache(npz(arrays, **modifications[change]), arrays)


@pytest.mark.parametrize("suffix,row", [
    ("det/det.txt", b"1,-1,10,20,10,30,1.01\n"),
    ("det/det.txt", b"0,-1,10,20,10,30,1\n"),
    ("det/det.txt", b"1051,-1,10,20,10,30,1\n"),
    ("det/det.txt", b"1.5,-1,10,20,10,30,1\n"),
    ("det/det.txt", b"1,-1,10,20,0,30,1\n"),
    ("det/det.txt", b"1,-1,nan,20,10,30,1\n"),
    ("gt/gt.txt", b"1,0,10,20,10,30,1,1,1\n"),
    ("gt/gt.txt", b"1,1,10,20,10,30,2,1,1\n"),
    ("gt/gt.txt", b"1,1,10,20,10,30,1,1,1.1\n"),
    ("gt/gt.txt", b"1,1,10,20,10,30,1,1,1\n" * 2),
    ("det/det.txt", b"1,-1,10,20,10,30,1,-1,-1,-1\n"),
])
def test_source_rows_not_silently_repaired(suffix, row):
    with pytest.raises(ValueError):
        intake.reference_arrays({**members(), suffix: row})


def archive_bytes(values):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for key, value in values.items():
            archive.writestr(f"train/{intake.SEQUENCE}/{key}", value)
    return stream.getvalue()


def test_pinned_archive_required():
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        intake.source_members(archive_bytes(members()))


def test_missing_member_refused_even_with_known_fingerprint(monkeypatch):
    values = members()
    del values["gt/gt.txt"]
    raw = archive_bytes(values)
    monkeypatch.setattr(intake, "ARCHIVE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="missing or duplicate"):
        intake.source_members(raw)


def test_read_only_receipt_never_claims_accuracy_or_independent_review(tmp_path, monkeypatch):
    values = members()
    archive = tmp_path / "labels.zip"
    cache = tmp_path / "cache.npz"
    archive.write_bytes(archive_bytes(values))
    cache.write_bytes(npz(intake.reference_arrays(values)))
    monkeypatch.setattr(intake, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    receipt = intake.audit(cache, archive)
    assert receipt["decision"] == "admit_annotation_only_diagnostic"
    assert receipt["scoring_pedestrian_rows"] == 1
    assert receipt["non_scoring_rows"] == 1
    assert receipt["scoring_pedestrian_ids"] == 1
    for key in ("images_read", "tracker_executed", "independent_visual_review",
                "untouched_validation", "commercial_admission", "reentry_or_flow_count_truth"):
        assert receipt[key] is False
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_file_and_expanded_budgets_and_symlinks(tmp_path, monkeypatch):
    arrays = intake.reference_arrays(members())
    raw = npz(arrays)
    monkeypatch.setattr(intake, "MAX_BYTES", 16)
    with pytest.raises(ValueError, match="expanded cache"):
        intake.verify_cache(raw, arrays)
    path = tmp_path / "input"
    path.write_bytes(b"x" * 17)
    with pytest.raises(ValueError, match="byte budget"):
        intake.raw_file(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="non-symlink"):
        intake.raw_file(link)
