"""Observable contracts for the React research article migration."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_writeup_keeps_research_claims_and_evidence() -> None:
    page = (ROOT / "src/features/research-writeup/ResearchWriteup.tsx").read_text()
    for claim in (
        "163 (−13%)",
        "217 → 202, p&lt;0.05",
        "DanceTrack HOTA −0.043, +29 ID switches",
        "HOTA −0.205",
        "ID switches 40 → 400+",
        "1.4e-3",
    ):
        assert claim in page
    assert "/assets/appearance_mot17_stratified.png" in page
    assert "/assets/kalman_calibration.png" in page


def test_writeup_has_reading_navigation_and_direct_anchors() -> None:
    page = (ROOT / "src/features/research-writeup/ResearchWriteup.tsx").read_text()
    for section_id in ("setup", "appearance", "motion", "uncertainty", "takeaway"):
        assert f'["{section_id}",' in page
    assert "IntersectionObserver" in page
    assert "ReadingProgress" in page
    assert 'aria-label="Article sections"' in page
    assert "scroll-mt-28" in page


def test_writeup_uses_shared_shell_and_updates_document_metadata() -> None:
    app = (ROOT / "src/App.tsx").read_text()
    page = (ROOT / "src/features/research-writeup/ResearchWriteup.tsx").read_text()
    assert 'path===\'/writeup\'?<ResearchWriteup/>' in app
    assert "document.title" in page
    assert 'link[rel="canonical"]' in page
    assert "https://visiontrack.hulage.in/writeup" in page
