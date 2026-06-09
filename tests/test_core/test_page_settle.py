import pytest
from playwright.async_api import Error as PlaywrightError

from webcontrol.config import Settings
from webcontrol.core.page_settle import SettleOptions, settle_page


def _fast_settings(**overrides) -> Settings:
    base = dict(
        page_settle_enabled=True,
        settle_timeout_ms=10,
        dom_stable_polls=2,
        dom_stable_interval_ms=1,
        scroll_steps=2,
        scroll_delay_ms=1,
    )
    base.update(overrides)
    return Settings(**base)


class FakePage:
    """Records settle interactions and scripts a sequence of DOM sizes."""

    def __init__(self, sizes=None, selector_error=False):
        self._sizes = list(sizes if sizes is not None else [100, 100, 100])
        self._size_idx = 0
        self.selector_error = selector_error
        self.networkidle_waited = False
        self.scrolled = False
        self.selector_waited = None
        self.size_reads = 0

    async def wait_for_selector(self, selector, state=None, timeout=None):
        self.selector_waited = selector
        if self.selector_error:
            raise PlaywrightError("selector timeout")

    async def wait_for_load_state(self, state, timeout=None):
        self.networkidle_waited = True

    async def evaluate(self, script, arg=None):
        if "scrollTo" in script:
            self.scrolled = True
            return None
        self.size_reads += 1
        idx = min(self._size_idx, len(self._sizes) - 1)
        self._size_idx += 1
        return self._sizes[idx]


@pytest.mark.asyncio
async def test_settle_disabled_is_noop():
    page = FakePage()
    await settle_page(page, SettleOptions(), _fast_settings(page_settle_enabled=False))
    assert page.networkidle_waited is False
    assert page.size_reads == 0
    assert page.scrolled is False


@pytest.mark.asyncio
async def test_dom_stability_returns_once_size_settles():
    # Grows once, then holds steady — two equal reads satisfy dom_stable_polls=2.
    page = FakePage(sizes=[100, 200, 200, 200])
    await settle_page(page, SettleOptions(), _fast_settings())
    assert page.networkidle_waited is True
    # 100 (set), 200 (reset), 200 (stable=1), 200 (stable=2 -> return)
    assert page.size_reads == 4


@pytest.mark.asyncio
async def test_unstable_dom_stops_at_poll_budget():
    # Size never repeats; the loop must bail at the hard budget, not hang.
    page = FakePage(sizes=[i * 10 for i in range(100)])
    await settle_page(page, SettleOptions(), _fast_settings())
    # target(2) * _STABILITY_POLL_BUDGET(6) = 12 reads max.
    assert page.size_reads == 12


@pytest.mark.asyncio
async def test_wait_for_selector_swallows_timeout():
    page = FakePage(selector_error=True)
    await settle_page(page, SettleOptions(wait_for_selector=".price"), _fast_settings())
    assert page.selector_waited == ".price"
    # A missing selector must not abort the rest of the settle.
    assert page.networkidle_waited is True


@pytest.mark.asyncio
async def test_scroll_to_load_triggers_scroll():
    page = FakePage()
    await settle_page(page, SettleOptions(scroll_to_load=True), _fast_settings())
    assert page.scrolled is True
