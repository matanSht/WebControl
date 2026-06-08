from datetime import UTC, datetime

from webcontrol.core.block_detection import detect_block
from webcontrol.models.page import PageContent, PageElement


def _page(title: str = "", text: str = "", *, elements: int = 0) -> PageContent:
    return PageContent(
        url="https://example.com",
        title=title,
        text_content=text,
        elements=[
            PageElement(ref=f"e{i}", role="button", name="x") for i in range(elements)
        ],
        forms=[],
        links=[],
        timestamp=datetime.now(UTC),
    )


def test_returns_none_for_normal_page():
    page = _page("Amazon.com : iphone 17 case", "Results " * 50, elements=16)
    assert detect_block(200, page) is None


def test_flags_block_status_codes():
    page = _page("Some page", "ok", elements=3)
    assert detect_block(503, page) is not None
    assert detect_block(429, page) is not None
    assert detect_block(403, page) is not None


def test_flags_known_markers_case_insensitive():
    assert detect_block(200, _page("Robot Check", "Enter the characters you see"))
    assert detect_block(200, _page("Amazon.com", "Something Went Wrong"))
    assert detect_block(200, _page("Just a moment...", "Checking your browser"))
    assert detect_block(200, _page("Access Denied", "you don't have permission"))


def test_flags_empty_challenge_shell():
    # No interactive elements, almost no text, suspicious title.
    assert detect_block(200, _page("Just a moment...", "", elements=0))
    assert detect_block(None, _page("", "tiny", elements=0))


def test_does_not_flag_short_but_real_page_with_elements():
    # Short text is fine as long as there is interactive content.
    assert detect_block(200, _page("Login", "Sign in", elements=4)) is None


def test_marker_inside_text_content():
    page = _page("Welcome", "To discuss automated access to Amazon data please contact us")
    assert detect_block(200, page) is not None
