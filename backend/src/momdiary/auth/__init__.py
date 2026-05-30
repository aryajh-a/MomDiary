"""Authentication primitives — feature 008 (Clerk-issued JWT)."""

from momdiary.auth.clerk import (
    ClerkAuthError,
    ClerkClaims,
    get_jwks_cache,
    verify_clerk_jwt,
)
from momdiary.auth.dependencies import (
    ActiveBabyDep,
    AuthContext,
    CurrentUser,
    CurrentUserDep,
    VerifiedUserDep,
    get_current_user,
    require_active_baby,
    require_verified_email,
)

__all__ = [
    "ActiveBabyDep",
    "AuthContext",
    "ClerkAuthError",
    "ClerkClaims",
    "CurrentUser",
    "CurrentUserDep",
    "VerifiedUserDep",
    "get_current_user",
    "get_jwks_cache",
    "require_active_baby",
    "require_verified_email",
    "verify_clerk_jwt",
]
