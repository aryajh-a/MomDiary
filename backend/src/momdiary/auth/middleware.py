"""ASGI middlewares for auth — feature 008.

Cookie parsing and the legacy Origin/Referer CSRF check are retired now
that bearer-token JWT auth is the only path. This module retains only the
structlog enrichment shim that binds auth fields once the
`get_current_user` / `require_active_baby` dependencies have populated
`request.state`.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuthLogContextMiddleware(BaseHTTPMiddleware):
    """Bind user_id + clerk_user_id + baby_id into structlog contextvars."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        bind: dict[str, object] = {"auth_mode": "clerk_jwt"}
        for attr in ("user_id", "clerk_user_id", "baby_id", "email_verified"):
            value = getattr(request.state, attr, None)
            if value is not None:
                bind[attr] = value
        structlog.contextvars.bind_contextvars(**bind)
        return response


__all__ = ["AuthLogContextMiddleware"]
