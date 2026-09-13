"""Static accessibility safeguards for the standalone learning modules."""

from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    ROOT / "learning" / "LEARNING_PATH.html",
    ROOT / "learning" / "CV_ROADMAP.html",
)


class _Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_head = False
        self.title_in_head = False
        self.ids: list[str] = []
        self.progressbars = 0
        self.live_regions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "head":
            self.in_head = True
        if tag == "title" and self.in_head:
            self.title_in_head = True
        if values.get("id"):
            self.ids.append(values["id"])
        if values.get("role") == "progressbar":
            self.progressbars += 1
        if values.get("aria-live"):
            self.live_regions += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.stem)
def test_learning_page_has_accessible_structure(page: Path) -> None:
    source = page.read_text()
    parser = _Structure()
    parser.feed(source)
    assert parser.title_in_head
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.progressbars == 1
    assert parser.live_regions >= 1
    assert 'class="skip-link" href="#main-content"' in source
    assert 'id="main-content" tabindex="-1"' in source


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.stem)
def test_learning_page_protects_motion_keyboard_and_mobile_users(page: Path) -> None:
    source = page.read_text()
    assert "prefers-reduced-motion: reduce" in source
    assert "animation: none !important" in source
    assert ".stage-nav a:focus-visible" in source
    assert "min-height: 44px" in source
    assert "@media (max-width: 560px)" in source
    assert ".stage-nav { flex-direction: column; }" in source
    assert "setAttribute('aria-valuenow'" in source
    assert '<svg class="chev" viewBox' not in source
    assert '<span class="box"><svg viewBox' not in source
