"""Navigation escalation ladder — climb robustness tiers until a page loads
without an anti-bot block, then report honestly which tier won.

Ladder (with no proxy configured, the proxy tier is skipped entirely):

    direct  -> behavioral -> [proxy] -> terminal

- **direct**: the stealth-hardened context as-is (fast path).
- **behavioral**: same page, but add human-like signals — a random jitter
  delay, a ``networkidle`` settle, and a scroll + mouse nudge — then re-check.
- **proxy**: rebuild the session context through ``WC_PROXY_SERVER`` (defeats the
  datacenter-IP signal) with a rotated UA. Only runs when a proxy is configured.
- **terminal**: every browser tier was blocked. Either raise ``BlockedError``
  (default) or, when the request opts in via ``fallback_to_search``, return the
  read-only search-index (Tier S) results.

Every attempt is recorded in the session activity log so the escalation is
visible in ``get_session_activity``.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone

from playwright.async_api import Error as PlaywrightError

from webcontrol.config import Settings
from webcontrol.core.action_executor import ActionExecutor
from webcontrol.core.block_detection import detect_block
from webcontrol.core.errors import BlockedError, NavigationError
from webcontrol.core.search_tier import SearchTier
from webcontrol.core.session_manager import BrowserSession, SessionManager
from webcontrol.models.actions import NavigateRequest
from webcontrol.models.page import PageContent
from webcontrol.models.responses import ActionResult
from webcontrol.models.search import SearchResult
from webcontrol.observability.timing import Timer

logger = logging.getLogger("webcontrol.escalation")

# A second realistic UA, distinct from stealth.DEFAULT_USER_AGENT, used when the
# proxy tier rebuilds the context — a fresh IP plus a fresh fingerprint.
_PROXY_TIER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class NavigationEscalator:
    def __init__(
        self,
        executor: ActionExecutor,
        session_manager: SessionManager,
        settings: Settings,
        search_tier: SearchTier | None = None,
    ) -> None:
        self._executor = executor
        self._sessions = session_manager
        self._settings = settings
        self._search_tier = search_tier

    async def navigate(self, session: BrowserSession, req: NavigateRequest) -> ActionResult:
        tiers_tried: list[str] = []
        last_reason = ""

        # --- Tier 0: direct (stealth context as-is) -------------------------
        status, content, reason = await self._attempt(session, req.url, req.wait_until, "direct")
        tiers_tried.append("direct")
        if reason is None:
            return self._ok(content, "direct")
        last_reason = reason

        if not (req.escalate and self._settings.navigation_escalation):
            return await self._terminal(session, req, content, last_reason, tiers_tried)

        # --- Tier 1: behavioral (human-like signals, longer settle) ---------
        content, reason = await self._behavioral(session, req)
        tiers_tried.append("behavioral")
        if reason is None:
            return self._ok(content, "behavioral")
        last_reason = reason

        # --- Tier 2: proxy (rebuild context through WC_PROXY_SERVER) ---------
        if self._settings.proxy_server:
            content, reason = await self._proxy(session, req)
            tiers_tried.append("proxy")
            if reason is None:
                return self._ok(content, "proxy")
            last_reason = reason

        # --- Terminal ---------------------------------------------------------
        return await self._terminal(session, req, content, last_reason, tiers_tried)

    # -- tier implementations -------------------------------------------------

    async def _behavioral(
        self, session: BrowserSession, req: NavigateRequest
    ) -> tuple[PageContent, str | None]:
        jitter = random.uniform(0, self._settings.behavioral_jitter_ms / 1000)
        await asyncio.sleep(jitter)
        status, content, reason = await self._attempt(
            session, req.url, "networkidle", "behavioral"
        )
        if reason is None:
            return content, None
        # Add human-like interaction, then re-parse and re-check the same page.
        try:
            await session.page.mouse.move(random.randint(200, 800), random.randint(200, 600))
            await session.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await asyncio.sleep(random.uniform(0.3, 0.8))
            content = await self._executor.get_page_content(session)
        except PlaywrightError as e:
            logger.debug("behavioral interaction failed: %s", e)
            return content, reason
        return content, detect_block(status, content)

    async def _proxy(
        self, session: BrowserSession, req: NavigateRequest
    ) -> tuple[PageContent, str | None]:
        await self._sessions.rebuild_context(session, user_agent=_PROXY_TIER_USER_AGENT)
        _, content, reason = await self._attempt(session, req.url, req.wait_until, "proxy")
        return content, reason

    async def _attempt(
        self, session: BrowserSession, url: str, wait_until: str, tier: str
    ) -> tuple[int | None, PageContent, str | None]:
        """Run one navigation attempt; return (status, content, block_reason)."""
        with Timer() as t:
            try:
                status, content = await self._executor.attempt_navigate(session, url, wait_until)
            except PlaywrightError as e:
                session.activity.record(
                    action=f"navigate:{tier}", url=url, duration_ms=t.elapsed_ms,
                    success=False, error=str(e)[:200],
                )
                raise NavigationError(f"Navigation failed: {e}") from e
        reason = detect_block(status, content)
        session.activity.record(
            action=f"navigate:{tier}", url=url, duration_ms=t.elapsed_ms,
            success=reason is None, error=reason,
        )
        logger.info(
            "navigate tier=%s url=%s status=%s blocked=%s elements=%d duration_ms=%.1f",
            tier, url, status, reason is not None, len(content.elements), t.elapsed_ms,
        )
        return status, content, reason

    # -- result builders ------------------------------------------------------

    def _ok(self, content: PageContent, tier: str) -> ActionResult:
        return ActionResult(success=True, page_content=content, blocked=False, tier_used=tier)

    async def _terminal(
        self,
        session: BrowserSession,
        req: NavigateRequest,
        content: PageContent,
        reason: str,
        tiers_tried: list[str],
    ) -> ActionResult:
        if req.fallback_to_search and self._search_tier is not None:
            items = await self._search_tier.search(req.url)
            fallback = SearchResult(
                success=True,
                query=req.url,
                provider=self._search_tier.provider_name,
                tier_used="search",
                results=items,
                timestamp=datetime.now(timezone.utc),
            )
            logger.info("navigate fell back to search tier: url=%s results=%d", req.url, len(items))
            return ActionResult(
                success=True,
                page_content=content,
                blocked=True,
                tier_used="search",
                block_reason=reason,
                search_fallback=fallback,
            )
        raise BlockedError(req.url, reason, tiers_tried)
