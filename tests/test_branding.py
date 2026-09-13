"""Keep the VisionTrack identity available on React and standalone routes."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_react_entry_declares_brand_assets() -> None:
    entry = (ROOT / "index.html").read_text()
    assert 'rel="icon" href="/favicon.ico?v=2"' in entry
    assert 'rel="icon" href="/visiontrack-mark.svg?v=2"' in entry
    assert 'rel="manifest" href="/site.webmanifest?v=2"' in entry
    assert '"name":"VisionTrack"' in entry
    assert (ROOT / "assets" / "visiontrack-mark.svg").is_file()
    assert (ROOT / "assets" / "favicon.ico").is_file()
    assert (ROOT / "assets" / "apple-touch-icon.png").is_file()
    assert (ROOT / "assets" / "visiontrack-icon-512.png").is_file()
    assert (ROOT / "assets" / "site.webmanifest").is_file()


def test_standalone_learning_pages_declare_favicon() -> None:
    for name in ("LEARNING_PATH.html", "CV_ROADMAP.html"):
        page = (ROOT / "learning" / name).read_text()
        assert 'href="/assets/visiontrack-mark.svg"' in page
