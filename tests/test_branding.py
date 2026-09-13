"""Keep the VisionTrack identity available on React and standalone routes."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_react_entry_declares_brand_assets() -> None:
    entry = (ROOT / "index.html").read_text()
    assert 'rel="icon" href="/visiontrack-mark.svg"' in entry
    assert 'rel="manifest" href="/site.webmanifest"' in entry
    assert '"name":"VisionTrack"' in entry
    assert (ROOT / "assets" / "visiontrack-mark.svg").is_file()
    assert (ROOT / "assets" / "site.webmanifest").is_file()


def test_standalone_learning_pages_declare_favicon() -> None:
    for name in ("LEARNING_PATH.html", "CV_ROADMAP.html"):
        page = (ROOT / "learning" / name).read_text()
        assert 'href="/assets/visiontrack-mark.svg"' in page
