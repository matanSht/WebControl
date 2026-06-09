from datetime import datetime, timezone

from webcontrol.config import Settings
from webcontrol.core.action_executor import ActionExecutor
from webcontrol.core.browser_manager import BrowserManager
from webcontrol.core.errors import SearchNotConfiguredError
from webcontrol.core.navigation_escalation import NavigationEscalator
from webcontrol.core.page_parser import PageParser
from webcontrol.core.search_tier import SearchTier
from webcontrol.core.session_manager import SessionManager
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
from webcontrol.models.search import SearchRequest, SearchResult
from webcontrol.models.session import SessionCreate, SessionInfo


class WebControlService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._browser_manager = BrowserManager(settings)
        self._session_manager = SessionManager(self._browser_manager, settings)
        self._parser = PageParser(settings)
        self._executor = ActionExecutor(self._parser, settings)
        # Tier S is built eagerly so a missing key fails fast at startup.
        self._search_tier: SearchTier | None = (
            SearchTier(settings) if settings.search_tier_enabled else None
        )
        self._escalator = NavigationEscalator(
            self._executor, self._session_manager, settings, self._search_tier
        )

    async def startup(self) -> None:
        await self._browser_manager.startup()
        await self._session_manager.start_cleanup_loop()

    async def shutdown(self) -> None:
        await self._session_manager.stop_cleanup_loop()
        await self._session_manager.close_all()
        await self._browser_manager.shutdown()
        if self._search_tier is not None:
            await self._search_tier.aclose()

    async def search(self, req: SearchRequest) -> SearchResult:
        if self._search_tier is None:
            raise SearchNotConfiguredError()
        items = await self._search_tier.search(
            req.query,
            max_results=req.max_results,
            fetch_contents=req.fetch_contents,
        )
        return SearchResult(
            success=True,
            query=req.query,
            provider=self._search_tier.provider_name,
            results=items,
            timestamp=datetime.now(timezone.utc),
        )

    async def create_session(self, opts: SessionCreate) -> SessionInfo:
        session = await self._session_manager.create_session(
            opts, enable_tracing=opts.enable_tracing
        )
        return SessionInfo(
            id=session.id,
            name=session.name,
            created_at=session.created_at,
            last_active=session.last_active,
            ttl_seconds=session.ttl_seconds,
            current_url=None,
            is_alive=True,
        )

    def list_sessions(self) -> list[SessionInfo]:
        return self._session_manager.list_sessions()

    async def close_session(self, session_id: str) -> None:
        await self._session_manager.close_session(session_id)

    async def get_session_activity(self, session_id: str, limit: int = 50) -> list[dict]:
        session = self._session_manager.get_session(session_id)
        return session.activity.get_entries(limit)

    def get_session_stats(self, session_id: str) -> dict:
        session = self._session_manager.get_session(session_id)
        return session.activity.get_stats()

    async def export_trace(self, session_id: str, path: str) -> str:
        return await self._session_manager.export_trace(session_id, path)

    async def navigate(self, session_id: str, req: NavigateRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._escalator.navigate(session, req)

    async def get_page_content(self, session_id: str) -> PageContent:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.get_page_content(session)

    async def click(self, session_id: str, req: ClickRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.click(session, req)

    async def fill(self, session_id: str, req: FillRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.fill(session, req)

    async def select(self, session_id: str, req: SelectRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.select(session, req)

    async def submit(self, session_id: str, req: SubmitRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.submit(session, req)

    async def execute_js(self, session_id: str, req: ExecuteJsRequest) -> ActionResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.execute_js(session, req)

    async def extract(self, session_id: str, req: ExtractRequest) -> ExtractResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.extract(session, req)

    async def get_html(self, session_id: str) -> HtmlResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.get_html(session)

    async def get_accessibility_tree(self, session_id: str) -> AccessibilityResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.get_accessibility_tree(session)

    async def screenshot(self, session_id: str) -> ScreenshotResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.screenshot(session)
