from __future__ import annotations

from pathlib import Path

import pytest

from experiments.dronetrafficza_source_audit import audit_files, audit_rows


def test_malformed_reference_and_late_events_block_comparison() -> None:
    result = audit_rows(
        [["10", "c"], ["11.t"], ["30", "t"]],
        [["12", "time", "2", "car", "1", "0", "rightleft_bottomtop", "0"]],
    )
    assert result["invalid_reference_lines"] == [2]
    assert result["reference_events_after_last_candidate_event"] == 1
    assert result["candidate_line_counts_valid_rows"] == {"2": 1}
    assert result["candidate_direction_counts_valid_rows"] == {"rightleft_bottomtop": 1}
    assert result["direct_event_comparison_ready"] is False
    assert result["dense_tracking_identity_truth_available"] is False
    assert result["admission"] == "hold"


def test_candidate_schema_and_empty_valid_stream_fail_closed() -> None:
    with pytest.raises(ValueError, match="no valid events"):
        audit_rows([["1", "c"]], [["2", "time", "2", "car", "1", "0", "direction"]])
    with pytest.raises(ValueError, match="both event streams"):
        audit_rows([], [["2", "time", "2", "car", "1", "0", "direction", "0"]])


def test_publisher_hash_mismatch_rejected_before_parsing(tmp_path: Path) -> None:
    reference = tmp_path / "groundTruth.csv"
    candidate = tmp_path / "OpenDataCam.csv"
    reference.write_text("10,c\n", encoding="utf-8")
    candidate.write_text("10,time,2,car,1,0,direction,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 differs"):
        audit_files(reference, candidate)
