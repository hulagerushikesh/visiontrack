"""Keep the VisionTrack identity available on React and standalone routes."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_react_entry_declares_brand_assets() -> None:
    entry = (ROOT / "index.html").read_text()
    assert 'rel="icon" href="/favicon.ico?v=3"' in entry
    assert 'rel="icon" href="/visiontrack-mark.svg?v=3"' in entry
    assert 'rel="manifest" href="/site.webmanifest?v=3"' in entry
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


def test_learning_and_demo_pages_use_the_shared_light_shell() -> None:
    pages = (
        ROOT / "learning" / "LEARNING_PATH.html",
        ROOT / "learning" / "CV_ROADMAP.html",
        ROOT / "viz" / "webdemo" / "index.template.html",
        ROOT / "viz" / "webdemo" / "index.html",
    )
    for path in pages:
        page = path.read_text()
        assert 'content="light"' in page
        assert 'href="/assets/site.css"' in page
        assert 'src="/assets/site.js"' in page
        assert 'class="site-nav"' in page
        assert "prefers-color-scheme: dark" not in page
        assert 'data-theme="dark"' not in page


def test_standalone_shell_uses_shared_product_navigation() -> None:
    script = (ROOT / "assets" / "site.js").read_text()
    for label, route in (
        ("Live tracker", "/live"),
        ("Learn", "/teaching"),
        ("Research", "/writeup"),
        ("Results", "/benchmark"),
        ("Docs", "/docs/"),
    ):
        assert label in script
        assert route in script
    assert 'root.setAttribute("data-theme", "light")' in script
    assert "btn.remove()" in script


def test_docs_have_a_product_exit_and_custom_reading_theme() -> None:
    config = (ROOT / "mkdocs.yml").read_text()
    index = (ROOT / "docs" / "index.md").read_text()
    stylesheet = ROOT / "docs" / "stylesheets" / "visiontrack.css"
    assert '"← VisionTrack home": https://visiontrack.hulage.in/' in config
    assert "stylesheets/visiontrack.css" in config
    assert "Back to the product" in index
    assert stylesheet.is_file()


def test_home_preview_is_explicitly_simulated() -> None:
    app = (ROOT / "src" / "App.tsx").read_text()
    assert "SIMULATED · PIPELINE PREVIEW" in app
    assert "Illustrative data" in app
    assert "Open real tracker" in app
