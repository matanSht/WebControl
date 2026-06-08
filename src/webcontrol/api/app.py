from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from webcontrol.api.auth import ApiKeyMiddleware
from webcontrol.api.middleware import RequestLoggingMiddleware
from webcontrol.api.routes_actions import router as actions_router
from webcontrol.api.routes_observability import router as observability_router
from webcontrol.api.routes_search import router as search_router
from webcontrol.api.routes_sessions import router as sessions_router
from webcontrol.config import Settings
from webcontrol.core.errors import (
    ActionError,
    ElementNotFoundError,
    MaxSessionsError,
    NavigationError,
    SearchError,
    SearchNotConfiguredError,
    SessionNotFoundError,
)
from webcontrol.core.service import WebControlService
from webcontrol.logging import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        service = WebControlService(settings)
        await service.startup()
        app.state.service = service
        yield
        await service.shutdown()

    app = FastAPI(
        title="WebControl",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ApiKeyMiddleware, settings=settings)
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")
    app.include_router(observability_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
        return JSONResponse(status_code=404, content={"error": str(exc)})

    @app.exception_handler(ElementNotFoundError)
    async def element_not_found_handler(request: Request, exc: ElementNotFoundError):
        return JSONResponse(status_code=422, content={"error": str(exc)})

    @app.exception_handler(MaxSessionsError)
    async def max_sessions_handler(request: Request, exc: MaxSessionsError):
        return JSONResponse(status_code=409, content={"error": str(exc)})

    @app.exception_handler(NavigationError)
    async def navigation_error_handler(request: Request, exc: NavigationError):
        return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.exception_handler(ActionError)
    async def action_error_handler(request: Request, exc: ActionError):
        return JSONResponse(status_code=422, content={"error": str(exc)})

    @app.exception_handler(SearchNotConfiguredError)
    async def search_not_configured_handler(request: Request, exc: SearchNotConfiguredError):
        return JSONResponse(status_code=503, content={"error": str(exc)})

    @app.exception_handler(SearchError)
    async def search_error_handler(request: Request, exc: SearchError):
        return JSONResponse(status_code=502, content={"error": str(exc)})

    return app
