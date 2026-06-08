import hmac

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from webcontrol.config import Settings

UNPROTECTED_PATHS = frozenset({"/health", "/docs", "/openapi.json"})


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self._api_key = settings.api_key

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._api_key:
            return await call_next(request)

        if request.url.path in UNPROTECTED_PATHS:
            return await call_next(request)

        provided = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(provided, self._api_key):
            return Response(
                content='{"error": "Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)
