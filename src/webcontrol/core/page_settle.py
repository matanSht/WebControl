"""Wait for async / JS-rendered content to land before the parser snapshots.

Many sites return HTTP 200 with only a shell, then hydrate the real content
(prices, listings, ratings) via later XHR or on-scroll lazy loaders. If the
parser reads the DOM the moment ``goto()`` returns, that content is missing.
This module bridges the gap with bounded, best-effort steps:

  1. wait for an optional caller-supplied selector (the content you want),
  2. optionally auto-scroll to fire on-scroll / IntersectionObserver loaders,
  3. settle on ``networkidle``,
  4. poll DOM size until it stops growing.

Every step swallows timeouts: settling is an enhancement, never a failure mode.
A page that never goes idle still gets parsed — just no earlier than it would
have been without settling.
"""

import asyncio
import logging
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from webcontrol.config import Settings

logger = logging.getLogger("webcontrol.settle")

# Hard ceiling on stability polls relative to the configured target, so a page
# whose DOM never stabilises (live tickers, animations) cannot stall the parse.
_STABILITY_POLL_BUDGET = 6


@dataclass(frozen=True)
class SettleOptions:
    """Per-navigation knobs for how aggressively to wait for content."""

    wait_for_selector: str | None = None
    scroll_to_load: bool = False


async def settle_page(page: Page, opts: SettleOptions, settings: Settings) -> None:
    """Best-effort wait for the page's async content before it is parsed."""
    if not settings.page_settle_enabled:
        return
    if opts.wait_for_selector:
        await _wait_for_selector(page, opts.wait_for_selector, settings)
    if opts.scroll_to_load:
        await _scroll_to_load(page, settings)
    await _wait_networkidle(page, settings)
    await _wait_dom_stable(page, settings)


async def _wait_for_selector(page: Page, selector: str, settings: Settings) -> None:
    try:
        await page.wait_for_selector(selector, state="visible", timeout=settings.settle_timeout_ms)
    except PlaywrightError as e:
        logger.debug("settle: selector %r did not appear: %s", selector, e)


async def _wait_networkidle(page: Page, settings: Settings) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=settings.settle_timeout_ms)
    except PlaywrightError as e:
        logger.debug("settle: networkidle not reached: %s", e)


async def _scroll_to_load(page: Page, settings: Settings) -> None:
    """Scroll top-to-bottom in steps to trigger lazy / on-scroll content."""
    try:
        await page.evaluate(
            """async ({ steps, delay }) => {
                const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
                for (let i = 1; i <= steps; i++) {
                    window.scrollTo(0, (document.body.scrollHeight * i) / steps);
                    await sleep(delay);
                }
                window.scrollTo(0, 0);
            }""",
            {"steps": settings.scroll_steps, "delay": settings.scroll_delay_ms},
        )
    except PlaywrightError as e:
        logger.debug("settle: scroll-to-load failed: %s", e)


async def _wait_dom_stable(page: Page, settings: Settings) -> None:
    """Poll DOM size until it stops growing or the poll budget is exhausted."""
    target = max(1, settings.dom_stable_polls)
    stable = 0
    last = -1
    for _ in range(target * _STABILITY_POLL_BUDGET):
        try:
            size = await page.evaluate("() => (document.body ? document.body.innerHTML.length : 0)")
        except PlaywrightError as e:
            logger.debug("settle: DOM size read failed: %s", e)
            return
        if size == last:
            stable += 1
            if stable >= target:
                return
        else:
            stable = 0
            last = size
        await asyncio.sleep(settings.dom_stable_interval_ms / 1000)
