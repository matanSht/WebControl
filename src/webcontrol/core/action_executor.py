import base64
import logging
from datetime import UTC, datetime

from playwright.async_api import Error as PlaywrightError

from webcontrol.config import Settings
from webcontrol.core.errors import ActionError, ElementNotFoundError, NavigationError
from webcontrol.core.page_parser import PageParser
from webcontrol.core.page_settle import SettleOptions, settle_page
from webcontrol.core.retry import with_retry
from webcontrol.core.session_manager import BrowserSession
from webcontrol.models.actions import (
    ClickRequest,
    ExecuteJsRequest,
    ExtractRequest,
    FillRequest,
    NavigateRequest,
    SelectRequest,
    SubmitRequest,
)
from webcontrol.models.page import PageContent
from webcontrol.models.responses import (
    AccessibilityResult,
    ActionResult,
    ExtractResult,
    HtmlResult,
    ScreenshotResult,
)
from webcontrol.observability.timing import Timer

logger = logging.getLogger("webcontrol.actions")


class ActionExecutor:
    def __init__(self, parser: PageParser, settings: Settings):
        self._parser = parser
        self._settings = settings

    async def attempt_navigate(
        self,
        session: BrowserSession,
        url: str,
        wait_until: str,
        settle: SettleOptions | None = None,
    ) -> tuple[int | None, PageContent]:
        """Navigate and parse, returning the HTTP status and page content.

        Unlike ``navigate`` this does NOT decide success or record activity —
        block detection and per-tier accounting are the escalator's job (see
        core/navigation_escalation.py). It still retries hard Playwright errors
        and raises ``NavigationError`` when the page genuinely fails to load.
        The HTTP status is the key signal a bot wall hides behind (a 200 block
        page), so it is captured from the goto response and returned.

        When ``settle`` is provided, async / JS-rendered content is given a
        bounded chance to land before the DOM is snapshotted (see
        core/page_settle.py); without it the page is parsed immediately.
        """
        response = await with_retry(
            lambda: session.page.goto(url, wait_until=wait_until),
            retries=self._settings.navigation_retries,
            delay_ms=self._settings.retry_delay_ms,
            operation=f"navigate({url})",
        )
        status = response.status if response is not None else None
        if settle is not None:
            await settle_page(session.page, settle, self._settings)
        content = await self._parser.parse(session)
        return status, content

    async def navigate(self, session: BrowserSession, req: NavigateRequest) -> ActionResult:
        with Timer() as t:
            try:
                status, content = await self.attempt_navigate(session, req.url, req.wait_until)
            except PlaywrightError as e:
                session.activity.record(
                    action="navigate", url=req.url, duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise NavigationError(f"Navigation failed: {e}") from e

        session.activity.record(action="navigate", url=req.url, duration_ms=t.elapsed_ms, success=True)
        logger.info(
            "navigate url=%s status=%s elements=%d forms=%d duration_ms=%.1f",
            req.url, status, len(content.elements), len(content.forms), t.elapsed_ms,
        )
        return ActionResult(success=True, page_content=content)

    async def click(self, session: BrowserSession, req: ClickRequest) -> ActionResult:
        locator = self._resolve_ref(session, req.ref)
        with Timer() as t:
            try:
                await with_retry(
                    lambda: locator.click(click_count=req.click_count, button=req.button),
                    retries=self._settings.action_retries,
                    delay_ms=self._settings.retry_delay_ms,
                    operation=f"click({req.ref})",
                )
            except PlaywrightError as e:
                session.activity.record(
                    action="click", ref=req.ref, duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Click failed on '{req.ref}': {e}") from e

            content = await self._parser.parse(session)

        session.activity.record(action="click", ref=req.ref, duration_ms=t.elapsed_ms, success=True)
        logger.debug("click ref=%s duration_ms=%.1f", req.ref, t.elapsed_ms)
        return ActionResult(success=True, page_content=content)

    async def fill(self, session: BrowserSession, req: FillRequest) -> ActionResult:
        locator = self._resolve_ref(session, req.ref)
        with Timer() as t:
            try:
                await with_retry(
                    lambda: locator.fill(req.value),
                    retries=self._settings.action_retries,
                    delay_ms=self._settings.retry_delay_ms,
                    operation=f"fill({req.ref})",
                )
            except PlaywrightError as e:
                session.activity.record(
                    action="fill", ref=req.ref, duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Fill failed on '{req.ref}': {e}") from e

            content = await self._parser.parse(session)

        session.activity.record(action="fill", ref=req.ref, duration_ms=t.elapsed_ms, success=True)
        logger.debug("fill ref=%s duration_ms=%.1f", req.ref, t.elapsed_ms)
        return ActionResult(success=True, page_content=content)

    async def select(self, session: BrowserSession, req: SelectRequest) -> ActionResult:
        locator = self._resolve_ref(session, req.ref)
        with Timer() as t:
            try:
                await with_retry(
                    lambda: locator.select_option(req.value),
                    retries=self._settings.action_retries,
                    delay_ms=self._settings.retry_delay_ms,
                    operation=f"select({req.ref})",
                )
            except PlaywrightError as e:
                session.activity.record(
                    action="select", ref=req.ref, duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Select failed on '{req.ref}': {e}") from e

            content = await self._parser.parse(session)

        session.activity.record(action="select", ref=req.ref, duration_ms=t.elapsed_ms, success=True)
        logger.debug("select ref=%s duration_ms=%.1f", req.ref, t.elapsed_ms)
        return ActionResult(success=True, page_content=content)

    async def submit(self, session: BrowserSession, req: SubmitRequest) -> ActionResult:
        locator = self._resolve_ref(session, req.ref)
        with Timer() as t:
            try:
                await locator.evaluate("el => { if (el.form) el.form.submit(); else el.click(); }")
            except PlaywrightError as e:
                session.activity.record(
                    action="submit", ref=req.ref, duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Submit failed on '{req.ref}': {e}") from e

            try:
                await session.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightError:
                pass

            content = await self._parser.parse(session)

        session.activity.record(action="submit", ref=req.ref, duration_ms=t.elapsed_ms, success=True)
        logger.debug("submit ref=%s duration_ms=%.1f", req.ref, t.elapsed_ms)
        return ActionResult(success=True, page_content=content)

    async def execute_js(self, session: BrowserSession, req: ExecuteJsRequest) -> ActionResult:
        with Timer() as t:
            try:
                await session.page.evaluate(req.script, req.args if req.args else None)
            except PlaywrightError as e:
                session.activity.record(
                    action="execute_js", duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"JS execution failed: {e}") from e

            content = await self._parser.parse(session)

        session.activity.record(action="execute_js", duration_ms=t.elapsed_ms, success=True)
        logger.debug("execute_js duration_ms=%.1f", t.elapsed_ms)
        return ActionResult(success=True, page_content=content)

    async def get_page_content(self, session: BrowserSession) -> PageContent:
        with Timer() as t:
            content = await self._parser.parse(session)

        session.activity.record(action="get_page_content", duration_ms=t.elapsed_ms, success=True)
        logger.debug(
            "get_page_content elements=%d forms=%d links=%d duration_ms=%.1f",
            len(content.elements), len(content.forms), len(content.links), t.elapsed_ms,
        )
        return content

    async def extract(self, session: BrowserSession, req: ExtractRequest) -> ExtractResult:
        """Pull structured rows from the page via CSS selectors.

        Unlike the parsed PageContent (which truncates body text and caps element
        counts), this reads exactly the fields asked for from every matching row
        — the reliable path for repeated data like prices, titles, and ratings on
        search-result and catalog pages.
        """
        limit = min(req.limit, self._settings.max_extract_rows)
        with Timer() as t:
            try:
                rows = await session.page.eval_on_selector_all(
                    req.selector,
                    """(elements, { fields, limit, maxChars }) =>
                        elements.slice(0, limit).map((el) => {
                            const row = {};
                            for (const f of fields) {
                                const target = f.selector ? el.querySelector(f.selector) : el;
                                if (!target) {
                                    row[f.name] = null;
                                    continue;
                                }
                                let val = f.attribute
                                    ? target.getAttribute(f.attribute)
                                    : (target.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (val != null && val.length > maxChars) {
                                    val = val.slice(0, maxChars);
                                }
                                row[f.name] = val;
                            }
                            return row;
                        })""",
                    {
                        "fields": [f.model_dump() for f in req.fields],
                        "limit": limit,
                        "maxChars": self._settings.extract_max_field_chars,
                    },
                )
            except PlaywrightError as e:
                session.activity.record(
                    action="extract", duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Extract failed for selector '{req.selector}': {e}") from e

        session.activity.record(action="extract", duration_ms=t.elapsed_ms, success=True)
        logger.debug(
            "extract selector=%s rows=%d duration_ms=%.1f",
            req.selector, len(rows), t.elapsed_ms,
        )
        return ExtractResult(
            success=True,
            selector=req.selector,
            count=len(rows),
            rows=rows,
            timestamp=datetime.now(UTC),
        )

    async def get_html(self, session: BrowserSession) -> HtmlResult:
        """Return the full rendered HTML — the full-fidelity fallback for when
        the curated PageContent misses something."""
        with Timer() as t:
            try:
                html = await session.page.content()
            except PlaywrightError as e:
                session.activity.record(
                    action="get_html", duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Get HTML failed: {e}") from e
            cap = self._settings.html_max_chars
            truncated = len(html) > cap
            if truncated:
                html = html[:cap]

        session.activity.record(action="get_html", duration_ms=t.elapsed_ms, success=True)
        logger.debug(
            "get_html chars=%d truncated=%s duration_ms=%.1f", len(html), truncated, t.elapsed_ms
        )
        return HtmlResult(
            success=True,
            url=session.page.url,
            html=html,
            truncated=truncated,
            timestamp=datetime.now(UTC),
        )

    async def get_accessibility_tree(self, session: BrowserSession) -> AccessibilityResult:
        """Return the page's ARIA snapshot — the real accessibility tree as YAML,
        a full-fidelity alternative view when the curated snapshot misses content."""
        with Timer() as t:
            try:
                snapshot = await session.page.locator("body").aria_snapshot()
            except PlaywrightError as e:
                session.activity.record(
                    action="get_accessibility_tree",
                    duration_ms=t.elapsed_ms, success=False, error=str(e)[:200],
                )
                raise ActionError(f"Accessibility snapshot failed: {e}") from e

        session.activity.record(
            action="get_accessibility_tree", duration_ms=t.elapsed_ms, success=True
        )
        logger.debug("get_accessibility_tree duration_ms=%.1f", t.elapsed_ms)
        return AccessibilityResult(
            success=True,
            url=session.page.url,
            snapshot=snapshot,
            timestamp=datetime.now(UTC),
        )

    async def screenshot(self, session: BrowserSession) -> ScreenshotResult:
        with Timer() as t:
            try:
                raw = await session.page.screenshot(type="png")
                encoded = base64.b64encode(raw).decode()
            except PlaywrightError as e:
                session.activity.record(
                    action="screenshot", duration_ms=t.elapsed_ms, success=False, error=str(e)[:200]
                )
                raise ActionError(f"Screenshot failed: {e}") from e

        session.activity.record(action="screenshot", duration_ms=t.elapsed_ms, success=True)
        logger.debug("screenshot size_bytes=%d duration_ms=%.1f", len(raw), t.elapsed_ms)
        return ScreenshotResult(success=True, screenshot_base64=encoded)

    def _resolve_ref(self, session: BrowserSession, ref: str):
        locator = session.ref_map.get(ref)
        if locator is None:
            raise ElementNotFoundError(ref)
        return locator
