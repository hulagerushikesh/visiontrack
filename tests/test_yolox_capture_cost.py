"""Guard measurement inputs and full-population coverage denominators, not speed."""
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import yolox_capture_cost as probe
from visiontrack.detection.yolox_onnx import YoloxDetector


def decoder(size):
    session = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="unused")])
    return YoloxDetector("unused", input_size=size, class_filter={0}, session=session)


@pytest.mark.parametrize("case,total,eligible,returned", [
    ("sparse_416", 3549, 64, 64), ("disjoint_640", 8400, 256, 256),
    ("clustered_640", 8400, 144, 4), ("reversed_640", 8400, 144, 4),
])
def test_generated_inputs_have_fixed_population_without_model_inference(case, total, eligible,
                                                                      returned):
    raw, strides, quadrants, size = probe.fixture(case)
    original = raw.copy()
    assert raw.shape == (1, total, 85) and raw.dtype == np.float32
    assert np.array_equal(raw, probe.fixture(case)[0])
    assert set(strides) == {8, 16, 32} and set(quadrants) == {0, 1, 2, 3}
    detections, full = decoder(size)._decode_frame(raw, 1., total)
    assert len(detections) == returned
    assert full.total_proposals - full.confidence_filtered_count == eligible
    assert not full.grid_decode_applied and not full.transposed
    assert not full.truncated and all(r.group_complete is not False for r in full.records)
    assert np.array_equal(raw, original)
    assert probe.detection_hash(detections) == probe.detection_hash(decoder(size)._decode(raw, 1.))


def test_prefix_coverage_uses_full_denominator_even_when_all_winners_are_absent():
    raw, strides, quadrants, size = probe.fixture("clustered_640")
    model = decoder(size)
    _, full = model._decode_frame(raw, 1., len(strides))
    assert {r.group_size for r in full.records if r.status == "returned"} == {18}
    _, partial = model._decode_frame(raw, 1., 4096)
    actual = probe.coverage(partial, full, strides, quadrants)
    assert actual["returned_winners"] == actual["multi_proposal_returned_groups"] == 4
    assert actual["retained_returned_winners"] == 0
    assert actual["complete_multi_proposal_returned_groups"] == 0
    assert 0 < actual["retained_eligible_rows"] < actual["eligible_rows"] == 144
    assert actual["strata"]["anchor_stride"]["16"]["retained_rows"] == 0
    assert actual["strata"]["anchor_stride"]["32"]["retained_rows"] == 0
    # Zero capture does not convert absent groups into singleton/zero-spread evidence.
    _, zero = model._decode_frame(raw, 1., 0)
    counts = probe.coverage(zero, full, strides, quadrants)
    assert counts["multi_proposal_returned_groups"] == 4
    assert counts["retained_returned_winners"] == counts["singleton_returned_groups"] == 0


def test_reordering_preserves_detections_but_changes_capture_coverage():
    outputs, coverages = [], []
    for case in ("clustered_640", "reversed_640"):
        raw, strides, quadrants, size = probe.fixture(case)
        model = decoder(size)
        normal, full = model._decode_frame(raw, 1., len(strides))
        captured, partial = model._decode_frame(raw, 1., 4096)
        assert probe.detection_hash(normal) == probe.detection_hash(captured)
        outputs.append(probe.detection_hash(normal))
        coverages.append(probe.coverage(partial, full, strides, quadrants))
    assert outputs[0] == outputs[1]
    assert coverages[0]["retained_returned_winners"] == 0
    assert coverages[1]["retained_returned_winners"] == 4
    assert coverages[1]["complete_multi_proposal_returned_groups"] == 1


def test_full_capture_coverage_and_strata_do_not_drop_filtered_classes():
    raw, strides, quadrants, size = probe.fixture("clustered_640")
    _, full = decoder(size)._decode_frame(raw, 1., len(strides))
    actual = probe.coverage(full, full, strides, quadrants)
    assert actual["complete_multi_proposal_returned_groups"] == 4
    assert actual["retained_eligible_rows"] == actual["eligible_rows"] == 144
    for table in actual["strata"].values():
        assert sum(row["total_rows"] for row in table.values()) == 8400
        assert sum(row["retained_eligible_rows"] for row in table.values()) == 144
    assert full.class_filtered_count == 4
    assert full.nms_suppressed_count == 136
    assert probe.encoded(actual)  # NumPy integer counts cannot leak into the receipt.


def test_probe_refuses_unknown_case_and_non_finite_json():
    with pytest.raises(ValueError, match="unknown case"):
        probe.fixture("a_real_video")
    with pytest.raises(ValueError):
        probe.encoded({"score": float("nan")})
