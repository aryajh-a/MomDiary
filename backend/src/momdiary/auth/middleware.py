"""ASGI middlewares for auth — feature 006.

* `OriginCsrfMiddleware`: rejects state-changing requests whose `Origin`
  (or `Referer` if Origin is absent) is not in the configured allow-list.
  Combined with SameSite=Lax cookies this provides the v1 CSRF defense
  (research §R3 — no double-submit token in v1).
* `AuthLogContextMiddleware`: appends `user_id` / `baby_id` to structlog
  contextvars once the auth deps have resolved them onto `request.state`.
"""

from __future__ import annotations

from urllib.parse import urlparse

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from momdiary.config import get_settings
from momdiary.observability.middleware import current_correlation_id

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _same_origin(value: str | None, allowed: list[str]) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in allowed


class OriginCsrfMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests with an off-origin Origin/Referer."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Allow same-server tooling (no Origin/Referer at all) only in dev.
        settings = get_settings()
        allowed = settings.allowed_origins_list
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if origin is None and referer is None:
            if settings.momdiary_app_env == "prod":
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "csrf_blocked",
                        "message": "Missing Origin/Referer.",
                        "correlation_id": current_correlation_id() or "unknown",
                    },
                )
            return await call_next(request)

        if origin is not None and not _same_origin(origin, allowed):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_blocked",
                    "message": "Cross-origin request rejected.",
                    "correlation_id": current_correlation_id() or "unknown",
                },
            )
        if origin is None and referer is not None and not _same_origin(referer, allowed):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_blocked",
                    "message": "Cross-origin request rejected.",
                    "correlation_id": current_correlation_id() or "unknown",
                },
            )

        return await call_next(request)


class AuthLogContextMiddleware(BaseHTTPMiddleware):
    """Bind user_id + baby_id into structlog contextvars after deps run."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        user_id = getattr(request.state, "user_id", None)
        baby_id = getattr(request.state, "baby_id", None)
        bind: dict[str, object] = {}
        if user_id is not None:
            bind["user_id"] = user_id
        if baby_id is not None:
            bind["baby_id"] = baby_id
        if bind:
            structlog.contextvars.bind_contextvars(**bind)
        return response
