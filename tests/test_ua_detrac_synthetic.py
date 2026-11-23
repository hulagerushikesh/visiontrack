"""The made-up timing set is readable by the UA-DETRAC runner and deterministic."""
import experiments.ua_detrac_gate as u
import experiments.ua_detrac_synthetic as s


def test_synthetic_set_has_requested_size_and_passes_format_check(tmp_path):
    summary = s.build(tmp_path / "a", sequences=3, total_frames=300, per_frame=4.0)
    assert summary["sequences"] == 3
    report = u.check(tmp_path / "a")
    assert report["sequences"] == 3
    assert sum(item["frames"] for item in report["per_sequence"].values()) <= 300
    assert report["detection_sets"]["chosen"] == "R-CNN"


def test_synthetic_set_is_byte_identical_for_one_seed(tmp_path):
    s.build(tmp_path / "a", sequences=2, total_frames=120, per_frame=3.0, seed=4)
    s.build(tmp_path / "b", sequences=2, total_frames=120, per_frame=3.0, seed=4)
    files_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*.*"))
    files_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*.*"))
    assert files_a == files_b and files_a
    for rel in files_a:
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()
