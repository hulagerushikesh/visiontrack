"""GT gap extraction remains deterministic and does not infer re-entry truth."""

import pytest

from experiments.reentry_gap_audit import extract_gap_candidates, summarize


def _gt(root, sequence: str, lines: str) -> None:
    path = root / sequence / "gt" / "gt.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lines)


def test_gaps_are_sequence_scoped_and_sample_is_order_independent(tmp_path) -> None:
    _gt(tmp_path, "seq-a", "13,1\n1,1\n3,1\n5,2\n15,1\n")
    _gt(tmp_path, "seq-b", "40,1\n1,1\n")
    events, rows, keys = extract_gap_candidates(tmp_path)
    assert (rows, keys) == (7, 3)
    assert [(e.sequence, e.sequence_id, e.missing_frames, e.stratum) for e in events] == [
        ("seq-a", 1, 1, "1-9"),
        ("seq-a", 1, 9, "1-9"),
        ("seq-a", 1, 1, "1-9"),
        ("seq-b", 1, 38, "30-99"),
    ]
    first = summarize(tmp_path, sample_per_stratum=1)
    _gt(tmp_path, "seq-a", "15,1\n5,2\n3,1\n1,1\n13,1\n")
    assert summarize(tmp_path, sample_per_stratum=1) == first
    assert first["candidate_count"] == 4
    assert len(first["audit_sample"]["1-9"]) == 1


def test_missing_input_and_duplicate_or_malformed_rows_fail_closed(tmp_path) -> None:
    with pytest.raises(ValueError, match="no sequence"):
        extract_gap_candidates(tmp_path)
    _gt(tmp_path, "seq-a", "1,1\n1,1\n")
    with pytest.raises(ValueError, match="duplicate"):
        extract_gap_candidates(tmp_path)
    _gt(tmp_path, "seq-a", "x,1\n")
    with pytest.raises(ValueError, match="non-integer"):
        extract_gap_candidates(tmp_path)
    _gt(tmp_path, "seq-a", "0,1\n")
    with pytest.raises(ValueError, match="invalid"):
        extract_gap_candidates(tmp_path)


def test_empty_annotations_are_not_false_evidence(tmp_path) -> None:
    _gt(tmp_path, "seq-a", "")
    result = summarize(tmp_path)
    assert result["sequence_count"] == 1
    assert result["candidate_count"] == 0
    assert result["stratum_counts"] == {"1-9": 0, "10-29": 0, "30-99": 0, "100+": 0}
