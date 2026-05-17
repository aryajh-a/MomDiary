"""Correlation-id ASGI middleware (FR-013)."""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

_correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "momdiary_correlation_id", default=None
)

CORRELATION_HEADER = "X-Correlation-ID"


def current_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def set_correlation_id(value: str) -> None:
    _correlation_id_ctx.set(value)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generates (or accepts) a correlation id per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        incoming = request.headers.get(CORRELATION_HEADER)
        cid = incoming or str(uuid.uuid4())
        token = _correlation_id_ctx.set(cid)
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        started = time.perf_counter()
        logger.info(
            "http.request.started",
            method=request.method,
            path=request.url.path,
            correlation_provided=incoming is not None,
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "http.request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=elapsed_ms,
            )
            raise
        finally:
            _correlation_id_ctx.reset(token)
            structlog.contextvars.unbind_contextvars("correlation_id")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "http.request.finished",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=elapsed_ms,
        )
        response.headers[CORRELATION_HEADER] = cid
        return response
