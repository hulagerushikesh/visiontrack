"""Freeze/integrity checks only: no tracker outcomes or held-out replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from experiments import traffic_protocol
from experiments.traffic_protocol import ARTIFACTS, MAX_BYTES, ROOT, load_frozen_protocol
from visiontrack.tracking.config import TrackerConfig


def test_frozen_recipe_and_preflight_are_read_only(capsys, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("protocol integrity preflight must not construct a tracker or RNG")

    monkeypatch.setattr("visiontrack.tracking.tracker.ByteTracker.__init__", forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    monkeypatch.setattr(np.random, "PCG64", forbidden)
    assert traffic_protocol.main() == 0
    output = capsys.readouterr().out
    assert "visiontrack.traffic-mechanism/v1" in output
    assert "no tracker run" in output
    spec, hashes = load_frozen_protocol()
    assert set(hashes) == set(ARTIFACTS)
    assert spec["execution_policy"]["candidate_interventions"] == []
    assert all(
        value is False
        for key, value in spec["execution_policy"].items()
        if key != "candidate_interventions"
    )


def test_all_tracker_fields_are_explicit_and_advanced_cues_disabled() -> None:
    spec, _ = load_frozen_protocol()
    config = spec["tracker_config"]
    assert asdict(TrackerConfig(**config)) == config
    assert set(config) == set(asdict(TrackerConfig()))
    assert config["w_iou"] == 1
    assert config["w_app"] == config["w_unc"] == config["w_ocm"] == 0
    assert not config["use_gmc"] and not config["use_oru"]
    assert config["motion_residual_path"] is None


def test_split_scenarios_seeds_and_conditions_are_fully_paired_and_disjoint() -> None:
    spec, _ = load_frozen_protocol()
    dev, heldout = (spec["splits"][name] for name in ("development", "heldout"))
    for field in ("seeds", "scenarios"):
        assert set(dev[field]).isdisjoint(heldout[field])
        assert len(dev[field]) == len(set(dev[field]))
        assert len(heldout[field]) == len(set(heldout[field]))
    assert set(dev["scenarios"] + heldout["scenarios"]) == set(spec["scenarios"])
    assert len(dev["seeds"]) == len(heldout["seeds"]) == 10
    assert len(dev["scenarios"]) == len(heldout["scenarios"]) == 3
    assert [(c["projection"], c["box_error"]) for c in spec["conditions"]] == [
        ("affine", False),
        ("perspective", False),
        ("affine", True),
        ("perspective", True),
    ]
    assert spec["observation_error"]["miss_rate"] == 0
    assert spec["observation_error"]["false_positive_rate"] == 0
    assert spec["ideal_box"]["appearance"] is None


@pytest.mark.parametrize("projection", ["affine", "perspective"])
def test_planned_input_geometry_has_valid_projection_and_bounded_boxes(projection) -> None:
    """Check the recipe's equations, not a future generator implementation.

    Only input geometry is inspected, including held-out paths. No tracking,
    random observations, scores or algorithm comparisons are generated.
    Worst-case independent edge shifts bound every allowed jitter realization.
    """
    spec, _ = load_frozen_protocol()
    grid, model = spec["frame_grid"], spec["ideal_box"]
    settings = spec["projection"]
    matrix = np.array(settings[projection], dtype=np.float64)
    assert abs(np.linalg.det(matrix)) > settings["min_abs_determinant"]
    inverse = np.linalg.inv(matrix)
    fractions = np.arange(grid["frames"], dtype=np.float64) / (grid["frames"] - 1)
    for objects in spec["scenarios"].values():
        assert len({o["object_id"] for o in objects}) == len(objects)
        for obj in objects:
            start, end = np.asarray(obj["start"]), np.asarray(obj["end"])
            points = start + fractions[:, None] * (end - start)
            assert np.all((points[:, 0] >= -6) & (points[:, 0] <= 6))
            assert np.all((points[:, 1] >= 0) & (points[:, 1] <= 20))
            homogeneous = np.column_stack((points, np.ones(grid["frames"]))) @ matrix.T
            denominator = homogeneous[:, 2]
            assert np.all(denominator > settings["min_positive_denominator"])
            uv = homogeneous[:, :2] / denominator[:, None]
            back = np.column_stack((uv, np.ones(grid["frames"]))) @ inverse.T
            assert np.all(back[:, 2] > settings["min_positive_denominator"])
            np.testing.assert_allclose(
                back[:, :2] / back[:, 2, None],
                points,
                rtol=0,
                atol=settings["roundtrip_absolute_tolerance"],
            )
            width = model["width_scale"] * model["world_width"] / denominator
            height = model["height_scale"] * model["world_height"] / denominator
            jitter = spec["observation_error"]["edge_jitter_fraction"]
            assert np.all(uv[:, 0] - width * (0.5 + jitter) > 0)
            assert np.all(uv[:, 0] + width * (0.5 + jitter) < grid["width"])
            assert np.all(uv[:, 1] - height * (1 + jitter) > 0)
            assert np.all(uv[:, 1] + height * jitter < grid["height"])
            for name in ("bottom_truncation", "top_truncation"):
                pulse = spec["observation_error"][name]
                assert 0 <= pulse["start_frame"] < pulse["stop_frame_exclusive"] <= 300
                assert 1 - 2 * jitter - pulse["ideal_height_fraction"] > 0


def _copy_artifacts(destination: Path) -> None:
    for name in (*ARTIFACTS, "experiments/traffic_protocol_v1.sha256"):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())


@pytest.mark.parametrize("name", ARTIFACTS)
def test_changes_to_either_artifact_are_rejected(tmp_path, name) -> None:
    _copy_artifacts(tmp_path)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="frozen artifact changed"):
        load_frozen_protocol(tmp_path)


@pytest.mark.parametrize("content", ["", "x\n", "0" * 64 + "  ../../private\n" + "x\n"])
def test_invalid_lock_cannot_redirect_artifact_reads(tmp_path, content) -> None:
    _copy_artifacts(tmp_path)
    (tmp_path / "experiments/traffic_protocol_v1.sha256").write_text(content)
    with pytest.raises(ValueError, match="protocol lock"):
        load_frozen_protocol(tmp_path)


@pytest.mark.parametrize(
    "payload, message",
    [
        (b'{"protocol_id":"a","protocol_id":"b"}', "duplicate"),
        (b'{"value":NaN}', "nonfinite"),
        (b'{"value":Infinity}', "nonfinite"),
        (b"[]", "protocol ID"),
        (b'{"protocol_id":"v2"}', "protocol ID"),
        (b"{", "property name"),
    ],
)
def test_json_rejections_even_with_matching_checksum(tmp_path, payload, message) -> None:
    _copy_artifacts(tmp_path)
    (tmp_path / ARTIFACTS[0]).write_bytes(payload)
    lines = (tmp_path / "experiments/traffic_protocol_v1.sha256").read_text().splitlines()
    lines[0] = hashlib.sha256(payload).hexdigest() + "  " + ARTIFACTS[0]
    (tmp_path / "experiments/traffic_protocol_v1.sha256").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match=message):
        load_frozen_protocol(tmp_path)


def test_artifact_size_is_bounded(tmp_path) -> None:
    _copy_artifacts(tmp_path)
    (tmp_path / ARTIFACTS[0]).write_bytes(b" " * (MAX_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        load_frozen_protocol(tmp_path)


def test_invalid_digest_and_cli_failure(tmp_path, monkeypatch, capsys) -> None:
    _copy_artifacts(tmp_path)
    lock = tmp_path / "experiments/traffic_protocol_v1.sha256"
    lock.write_text(lock.read_text().replace("3a6d", "XXXX", 1))
    with pytest.raises(ValueError, match="invalid protocol SHA"):
        load_frozen_protocol(tmp_path)
    monkeypatch.setattr(
        traffic_protocol, "load_frozen_protocol", lambda: load_frozen_protocol(tmp_path)
    )
    assert traffic_protocol.main() == 2
    assert "failed" in capsys.readouterr().out


def test_json_has_no_result_payload() -> None:
    spec, _ = load_frozen_protocol()
    assert "results" not in spec
    assert "expected_observations" not in spec
    # JSON can be serialized without nonfinite values; this is not performance evidence.
    json.dumps(spec, allow_nan=False)
