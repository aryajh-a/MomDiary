"""Authentication primitives — feature 006.

Public surface:

* `hasher.PasswordHasherService` — Argon2id hashing (research §R1).
* `sessions.SessionService` — opaque-token rolling sessions (research §R2).
* `dependencies.current_user`, `current_session` — FastAPI dependencies.
* `dependencies.active_baby_id` — resolves the per-request active baby
  using `X-Active-Baby-Id` header override → `users.active_baby_id` →
  `409 no_active_baby` (research §R7).
* `middleware.AuthLogContextMiddleware` — enriches structlog with user_id +
  baby_id; performs the Origin/Referer CSRF check (research §R3).
"""

from momdiary.auth.dependencies import (
    AuthContext,
    current_user,
    require_active_baby,
)
from momdiary.auth.hasher import PasswordHasherService
from momdiary.auth.sessions import SessionService

__all__ = [
    "AuthContext",
    "PasswordHasherService",
    "SessionService",
    "current_user",
    "require_active_baby",
]
