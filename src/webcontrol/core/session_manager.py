import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from playwright.async_api import BrowserContext, Locator, Page
from playwright.async_api import Response as PlaywrightResponse

from webcontrol.config import Settings
from webcontrol.core.browser_manager import BrowserManager
from webcontrol.core.errors import MaxSessionsError, SessionNotFoundError
from webcontrol.core.stealth import STEALTH_INIT_SCRIPT, stealth_context_options
from webcontrol.models.session import SessionCreate, SessionInfo
from webcontrol.observability.activity import SessionActivityLog
from webcontrol.observability.network import CapturedResponse, NetworkCapture, parse_body

logger = logging.getLogger("webcontrol.sessions")


@dataclass
class BrowserSession:
    id: str
    name: str | None
    context: BrowserContext
    page: Page
    created_at: datetime
    last_active: datetime
    ttl_seconds: int
    tracing_enabled: bool = False
    ref_map: dict[str, Locator] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    activity: SessionActivityLog = field(default_factory=SessionActivityLog)
    network: NetworkCapture = field(default_factory=NetworkCapture)


class SessionManager:
    def __init__(self, browser_manager: BrowserManager, settings: Settings):
        self._browser_manager = browser_manager
        self._settings = settings
        self._sessions: dict[str, BrowserSession] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_loop(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def _build_context_opts(
        self,
        opts: SessionCreate,
        *,
        user_agent_override: str | None = None,
    ) -> dict:
        # Stealth defaults first, so explicit options below win.
        context_opts: dict = stealth_context_options(self._settings)
        context_opts["viewport"] = {
            "width": opts.viewport_width or self._settings.viewport_width,
            "height": opts.viewport_height or self._settings.viewport_height,
        }
        ua = user_agent_override or opts.user_agent
        if ua:
            context_opts["user_agent"] = ua
        if self._settings.proxy_server:
            context_opts["proxy"] = self._proxy_opts()
        return context_opts

    def _proxy_opts(self) -> dict:
        proxy: dict = {"server": self._settings.proxy_server}
        if self._settings.proxy_username:
            proxy["username"] = self._settings.proxy_username
            proxy["password"] = self._settings.proxy_password
        return proxy

    async def _new_context_and_page(
        self,
        context_opts: dict,
        enable_tracing: bool,
        network: NetworkCapture | None = None,
    ) -> tuple[BrowserContext, Page]:
        context = await self._browser_manager.browser.new_context(**context_opts)
        if self._settings.stealth_enabled:
            await context.add_init_script(STEALTH_INIT_SCRIPT)
        if enable_tracing:
            await context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = await context.new_page()
        page.set_default_timeout(self._settings.action_timeout_ms)
        page.set_default_navigation_timeout(self._settings.navigation_timeout_ms)
        if network is not None:
            self._attach_network_listener(page, network)
        return context, page

    def _attach_network_listener(self, page: Page, network: NetworkCapture) -> None:
        page.on("response", lambda response: self._on_response(response, network))

    def _on_response(self, response: PlaywrightResponse, network: NetworkCapture) -> None:
        # Cheap synchronous filter first, so a disabled/irrelevant response never
        # spawns a body-read task.
        try:
            if not network.enabled:
                return
            content_type = response.headers.get("content-type", "")
            if not network.matches(
                response.url, response.request.resource_type, content_type
            ):
                return
        except Exception:
            return
        task = asyncio.create_task(self._capture_body(response, network, content_type))
        network.track(task)

    async def _capture_body(
        self, response: PlaywrightResponse, network: NetworkCapture, content_type: str
    ) -> None:
        try:
            text = await response.text()
        except Exception:
            return  # body unavailable (redirect, aborted, already gone) — skip
        network.record(
            CapturedResponse(
                timestamp=datetime.now(UTC),
                url=response.url,
                status=response.status,
                method=response.request.method,
                resource_type=response.request.resource_type,
                content_type=content_type,
                body=parse_body(text, content_type, network.max_body_chars),
            )
        )

    async def create_session(self, opts: SessionCreate, enable_tracing: bool = False) -> BrowserSession:
        if len(self._sessions) >= self._settings.max_sessions:
            raise MaxSessionsError(self._settings.max_sessions)

        context_opts = self._build_context_opts(opts)
        network = NetworkCapture(
            max_entries=self._settings.network_capture_max_entries,
            max_body_chars=self._settings.network_capture_max_body_chars,
        )
        context, page = await self._new_context_and_page(context_opts, enable_tracing, network)

        now = datetime.now(UTC)
        session = BrowserSession(
            id=str(uuid.uuid4()),
            name=opts.name,
            context=context,
            page=page,
            created_at=now,
            last_active=now,
            ttl_seconds=opts.ttl_seconds or self._settings.default_session_ttl_seconds,
            tracing_enabled=enable_tracing,
            network=network,
        )
        self._sessions[session.id] = session
        logger.info("Session created: id=%s name=%s tracing=%s", session.id, session.name, enable_tracing)
        return session

    async def rebuild_context(
        self, session: BrowserSession, *, user_agent: str | None = None
    ) -> None:
        """Replace a session's browser context in place (e.g. to add a proxy).

        Builds a fresh context (stealth + proxy from settings, optional UA
        override), swaps it onto the session, and closes the old one. The
        ref_map is cleared because the old Locators belong to the closed page.
        Used by the proxy escalation tier in core/navigation_escalation.py.
        """
        opts = SessionCreate(name=session.name)
        context_opts = self._build_context_opts(opts, user_agent_override=user_agent)
        new_context, new_page = await self._new_context_and_page(
            context_opts, session.tracing_enabled, session.network
        )
        old_context = session.context
        session.context = new_context
        session.page = new_page
        session.ref_map = {}
        try:
            await old_context.close()
        except Exception as e:  # closing the discarded context must never fail the rebuild
            logger.warning("Failed to close old context during rebuild: %s", e)
        logger.info("Session context rebuilt: id=%s proxy=%s", session.id, bool(self._settings.proxy_server))

    def get_session(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def touch_session(self, session: BrowserSession) -> None:
        session.last_active = datetime.now(UTC)

    def list_sessions(self) -> list[SessionInfo]:
        return [self._to_info(s) for s in self._sessions.values()]

    async def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFoundError(session_id)
        if session.tracing_enabled:
            await session.context.tracing.stop()
        await session.context.close()
        logger.info("Session closed: id=%s actions_performed=%d", session_id, session.activity.get_stats()["total_actions"])

    async def export_trace(self, session_id: str, path: str) -> str:
        session = self.get_session(session_id)
        if not session.tracing_enabled:
            raise ValueError(f"Tracing not enabled for session {session_id}")
        await session.context.tracing.stop(path=path)
        await session.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        logger.info("Trace exported: session=%s path=%s", session_id, path)
        return path

    async def close_all(self) -> None:
        for session in list(self._sessions.values()):
            if session.tracing_enabled:
                await session.context.tracing.stop()
            await session.context.close()
        self._sessions.clear()

    def _to_info(self, session: BrowserSession) -> SessionInfo:
        return SessionInfo(
            id=session.id,
            name=session.name,
            created_at=session.created_at,
            last_active=session.last_active,
            ttl_seconds=session.ttl_seconds,
            current_url=session.page.url if session.page.url != "about:blank" else None,
            is_alive=True,
        )

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = datetime.now(UTC)
            expired = [
                sid
                for sid, s in self._sessions.items()
                if (now - s.last_active).total_seconds() > s.ttl_seconds
            ]
            for sid in expired:
                session = self._sessions.pop(sid, None)
                if session is not None:
                    if session.tracing_enabled:
                        await session.context.tracing.stop()
                    await session.context.close()
                    logger.info("Session expired: id=%s (TTL %ds)", sid, session.ttl_seconds)
