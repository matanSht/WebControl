from webcontrol.config import Settings
from webcontrol.core.action_executor import ActionExecutor
from webcontrol.core.browser_manager import BrowserManager
from webcontrol.core.page_parser import PageParser
from webcontrol.core.session_manager import SessionManager
from webcontrol.models.actions import (
    ClickRequest,
    ExecuteJsRequest,
    FillRequest,
    NavigateRequest,
    SelectRequest,
    SubmitRequest,
)
from webcontrol.models.page import PageContent
from webcontrol.models.responses import ActionResult, ScreenshotResult
from webcontrol.models.session import SessionCreate, SessionInfo


class WebControlService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._browser_manager = BrowserManager(settings)
        self._session_manager = SessionManager(self._browser_manager, settings)
        self._parser = PageParser()
        self._executor = ActionExecutor(self._parser, settings)

    async def startup(self) -> None:
        await self._browser_manager.startup()
        await self._session_manager.start_cleanup_loop()

    async def shutdown(self) -> None:
        await self._session_manager.stop_cleanup_loop()
        await self._session_manager.close_all()
        await self._browser_manager.shutdown()

    async def create_session(self, opts: SessionCreate) -> SessionInfo:
        session = await self._session_manager.create_session(opts, enable_tracing=opts.enable_tracing)
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
            return await self._executor.navigate(session, req)

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

    async def screenshot(self, session_id: str) -> ScreenshotResult:
        session = self._session_manager.get_session(session_id)
        async with session.lock:
            self._session_manager.touch_session(session)
            return await self._executor.screenshot(session)
