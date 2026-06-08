from datetime import UTC, datetime

import pytest

from webcontrol.config import Settings
from webcontrol.core.errors import BlockedError
from webcontrol.core.navigation_escalation import NavigationEscalator
from webcontrol.models.actions import NavigateRequest
from webcontrol.models.page import PageContent, PageElement
from webcontrol.models.search import SearchResultItem
from webcontrol.observability.activity import SessionActivityLog


# --- fakes -------------------------------------------------------------------

def _blocked_page() -> PageContent:
    return PageContent(
        url="https://shop.example/s?k=x", title="Robot Check",
        text_content="Enter the characters you see below", elements=[],
        forms=[], links=[], timestamp=datetime.now(UTC),
    )


def _clean_page() -> PageContent:
    return PageContent(
        url="https://shop.example/s?k=x", title="Results",
        text_content="lots of products here " * 20,
        elements=[PageElement(ref="e1", role="link", name="A product")],
        forms=[], links=[], timestamp=datetime.now(UTC),
    )


class FakeMouse:
    async def move(self, *a, **k):
        return None


class FakePage:
    def __init__(self):
        self.mouse = FakeMouse()

    async def evaluate(self, *a, **k):
        return None


class FakeSession:
    def __init__(self):
        self.page = FakePage()
        self.ref_map = {}
        self.activity = SessionActivityLog()
        self.tracing_enabled = False
        self.name = "t"


class FakeExecutor:
    """Returns scripted (status, content) per attempt_navigate call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    async def attempt_navigate(self, session, url, wait_until):
        item = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return item

    async def get_page_content(self, session):
        # Reflect the most recent scripted page (behavioral re-parse).
        return self._script[min(self.calls - 1, len(self._script) - 1)][1]


class FakeSessionManager:
    def __init__(self):
        self.rebuilt = False

    async def rebuild_context(self, session, *, user_agent=None):
        self.rebuilt = True


class FakeSearchTier:
    provider_name = "exa"

    async def search(self, query, **kwargs):
        return [SearchResultItem(title="Hit", url="https://x", snippet="s", content="c")]


def _escalator(script, settings=None, search_tier=None):
    settings = settings or Settings()
    return NavigationEscalator(
        FakeExecutor(script), FakeSessionManager(), settings, search_tier
    ), settings


# --- tests -------------------------------------------------------------------

async def test_direct_tier_succeeds_fast():
    esc, _ = _escalator([(200, _clean_page())])
    result = await esc.navigate(FakeSession(), NavigateRequest(url="https://shop.example"))
    assert result.success and not result.blocked
    assert result.tier_used == "direct"


async def test_escalates_to_behavioral_when_direct_blocked():
    # direct -> blocked, behavioral -> clean
    esc, _ = _escalator([(200, _blocked_page()), (200, _clean_page())])
    result = await esc.navigate(FakeSession(), NavigateRequest(url="https://shop.example"))
    assert result.success and not result.blocked
    assert result.tier_used == "behavioral"


async def test_all_blocked_raises_blocked_error_by_default():
    esc, _ = _escalator([(200, _blocked_page())])  # always blocked
    with pytest.raises(BlockedError) as exc:
        await esc.navigate(FakeSession(), NavigateRequest(url="https://shop.example"))
    # no proxy configured -> only direct + behavioral attempted
    assert exc.value.tiers_tried == ["direct", "behavioral"]


async def test_fallback_to_search_returns_search_results():
    esc, _ = _escalator([(200, _blocked_page())], search_tier=FakeSearchTier())
    result = await esc.navigate(
        FakeSession(),
        NavigateRequest(url="https://shop.example/s?k=iphone", fallback_to_search=True),
    )
    assert result.success and result.blocked
    assert result.tier_used == "search"
    assert result.search_fallback is not None
    assert result.search_fallback.results[0].title == "Hit"


async def test_proxy_tier_runs_when_configured():
    settings = Settings(proxy_server="http://proxy:8080")
    sm = FakeSessionManager()
    esc = NavigationEscalator(
        FakeExecutor([(200, _blocked_page()), (200, _blocked_page()), (200, _clean_page())]),
        sm, settings, None,
    )
    result = await esc.navigate(FakeSession(), NavigateRequest(url="https://shop.example"))
    assert sm.rebuilt is True
    assert result.tier_used == "proxy"
    assert not result.blocked


async def test_escalate_false_raises_immediately_on_block():
    esc, _ = _escalator([(200, _blocked_page())])
    with pytest.raises(BlockedError) as exc:
        await esc.navigate(
            FakeSession(), NavigateRequest(url="https://shop.example", escalate=False)
        )
    assert exc.value.tiers_tried == ["direct"]
