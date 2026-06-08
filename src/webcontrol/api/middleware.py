import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from webcontrol.observability.context import set_request_id

logger = logging.getLogger("webcontrol.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get("x-request-id")
        request_id = set_request_id(incoming_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(duration_ms)

        session_id = request.path_params.get("session_id", "")
        path = request.url.path

        logger.info(
            "%s %s → %d (%sms)%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
            f" session={session_id}" if session_id else "",
        )

        return response
