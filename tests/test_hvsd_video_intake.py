"""The intake must reject misleading frame timing and geometry metadata."""
from __future__ import annotations

import pytest

from experiments.hvsd_video_intake import summarize_probe


def payload(times: list[str]) -> dict:
    return {"streams": [{"width": 704, "height": 432, "nb_frames": len(times)}],
            "frames": [{"width": 704, "height": 432,
                        "best_effort_timestamp_time": time} for time in times]}


def test_timing_summary_counts_irregular_gaps() -> None:
    result = summarize_probe(payload(["0", "0.04", "0.08", "0.16", "0.20"]))
    assert result["decoded_frames"] == 5
    assert result["median_frame_gap_seconds"] == 0.04
    assert result["gaps_over_5pct_from_median"] == 1


@pytest.mark.parametrize("times", [["0", "0", "0.04"], ["0", "-0.01"],
                                    ["0", "nan"], ["0", "inf"]])
def test_bad_timestamps_fail_closed(times: list[str]) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        summarize_probe(payload(times))


def test_dimension_change_fails_closed() -> None:
    sample = payload(["0", "0.04"])
    sample["frames"][1]["width"] = 640
    with pytest.raises(ValueError, match="dimensions"):
        summarize_probe(sample)
