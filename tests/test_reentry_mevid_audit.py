"""Synthetic ZIPs exercise the metadata gate without downloading any dataset."""

import json
import sys
import zipfile

import pytest

from experiments.reentry_mevid_audit import FILES, PREFIX, main, summarize


def _files():
    return {
        "track_train_info.txt": "0e0 1e0 103 20 424\n2 2 103 20 424\n",
        "train_name.txt": (
            "0103O020C424T000F00000.jpg\n0103O020C424T000F00001.jpg\n0103O020C424T001F00000.jpg\n"
        ),
        "track_test_info.txt": "0 0 201 3 330\n1 1 201 3 330\n",
        "test_name.txt": "0201O003C330T000F00000.jpg\n0201O003C330T001F00000.jpg\n",
        "query_IDX.txt": "0e0\n",
    }


def _zip(tmp_path, values=None):
    path = tmp_path / "annotations.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (values or _files()).items():
            archive.writestr(PREFIX + name, content)
    return path


def test_metadata_is_aggregate_only_and_never_extracts_or_evaluates(tmp_path):
    path = _zip(tmp_path)
    result = summarize(path)
    assert result == summarize(path)
    assert result["train"] == {
        "track_metadata_rows": 2,
        "empty_chip_ranges": 0,
        "tracklets": 2,
        "listed_chips": 3,
        "participant_ids": 1,
        "cameras": 1,
        "participant_outfit_camera_groups": 1,
        "groups_with_multiple_tracklets": 1,
    }
    assert result["query_tracklets"] == result["gallery_tracklets"] == 1
    assert not result["empty_ranges_require_review"]
    assert result["upstream_participant_overlap"] == result["verified_reentry_events"] == 0
    assert result["identity_accuracy"] == "not_evaluated"
    assert result["same_camera_session_split"] == "not_established"
    output = json.dumps(result, allow_nan=False)
    for private_value in ("0103", "0201", "424", "330", str(path)):
        # The archive digest may coincidentally contain digits; inspect non-hash fields.
        assert private_value not in output.replace(result["archive_sha256"], "")
    assert list(tmp_path.iterdir()) == [path]


def test_empty_range_is_visible_not_silently_counted_as_a_tracklet(tmp_path):
    files = _files()
    files["track_train_info.txt"] = "0 1 103 20 424\n2 1 103 20 424\n2 2 103 20 424\n"
    result = summarize(_zip(tmp_path, files))
    assert result["train"]["track_metadata_rows"] == 3
    assert result["train"]["tracklets"] == 2
    assert result["train"]["empty_chip_ranges"] == 1
    assert result["empty_ranges_require_review"]


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("track_train_info.txt", "1 2 103 20 424\n"),
        ("track_train_info.txt", "0 2 103 20 424\n1 2 103 20 424\n"),
        ("track_train_info.txt", "0 1.5 103 20 424\n"),
        ("track_train_info.txt", "0 NaN 103 20 424\n"),
        ("track_train_info.txt", "0 Infinity 103 20 424\n"),
        ("track_train_info.txt", "0 -1 103 20 424\n"),
        ("track_train_info.txt", "0 1 103 20\n"),
        ("train_name.txt", "0103O020C424T000F00000.jpg\n"),
        ("train_name.txt", _files()["train_name.txt"] * 2),
        ("train_name.txt", _files()["train_name.txt"].replace("F00001", "F00000")),
        ("train_name.txt", _files()["train_name.txt"].replace("T001", "T000")),
        ("train_name.txt", _files()["train_name.txt"].replace("0103", "0104")),
        ("train_name.txt", "../image.jpg\n"),
        ("train_name.txt", "x" * 4097),
        ("query_IDX.txt", "0\n0\n"),
        ("query_IDX.txt", "2\n"),
        ("query_IDX.txt", ""),
    ],
)
def test_corrupt_or_ambiguous_tables_fail_closed(tmp_path, name, replacement):
    files = _files()
    files[name] = replacement
    with pytest.raises(ValueError):
        summarize(_zip(tmp_path, files))


def test_participant_split_leakage_and_empty_query_fail_closed(tmp_path):
    files = {
        name: value.replace("0201", "0103").replace("201 ", "103 ")
        for name, value in _files().items()
    }
    with pytest.raises(ValueError, match="cross"):
        summarize(_zip(tmp_path, files))
    files = _files()
    files["track_test_info.txt"] = "0 -0 201 3 330\n1 0 201 3 330\n1 1 201 3 330\n"
    files["query_IDX.txt"] = "1\n"
    with pytest.raises(ValueError, match="query"):
        summarize(_zip(tmp_path, files))


def test_unknown_missing_duplicate_or_oversized_members_rejected(tmp_path, monkeypatch):
    files = _files()
    files["../extra.txt"] = "not allowed"
    with pytest.raises(ValueError, match="five"):
        summarize(_zip(tmp_path, files))
    del files["../extra.txt"]
    del files[next(iter(FILES))]
    with pytest.raises(ValueError, match="five"):
        summarize(_zip(tmp_path, files))
    path = _zip(tmp_path)
    with pytest.warns(UserWarning), zipfile.ZipFile(path, "a") as archive:
        archive.writestr(PREFIX + "query_IDX.txt", "0\n")
    with pytest.raises(ValueError, match="five"):
        summarize(path)
    path = _zip(tmp_path)
    monkeypatch.setattr("experiments.reentry_mevid_audit.MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="ZIP exceeds"):
        summarize(path)


def test_cli_is_json_only_and_bounded_expansion_and_query_count(tmp_path, monkeypatch, capsys):
    path = _zip(tmp_path)
    monkeypatch.setattr(sys, "argv", ["audit", "--annotations", str(path)])
    main()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == summarize(path)
    with monkeypatch.context() as scoped:
        scoped.setattr("experiments.reentry_mevid_audit.MAX_MEMBER_BYTES", 1)
        with pytest.raises(ValueError, match="member"):
            summarize(path)
    with monkeypatch.context() as scoped:
        scoped.setattr("experiments.reentry_mevid_audit.MAX_TOTAL_BYTES", 1)
        with pytest.raises(ValueError, match="expanded"):
            summarize(path)
    files = _files()
    files["query_IDX.txt"] = "0\n" * 20_001
    with pytest.raises(ValueError, match="too many query"):
        summarize(_zip(tmp_path, files))
