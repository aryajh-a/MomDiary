"""Networkless Clerk JWT verification (feature 008).

Per `specs/008-clerk-auth/research.md` decisions:

* Verification path: networkless. We fetch Clerk's JWKS once and cache it
  in-process for `CLERK_JWKS_CACHE_TTL_SECONDS` (default 1 h). On `kid`
  miss we force a single refresh (deduplicated via `asyncio.Lock`).
* Claims contract: `sub` (Clerk user id), `email`, `email_verified` (from
  the `momdiary-default` JWT template), `sid`, `iss`, `aud` (when
  `CLERK_JWT_AUDIENCE` is configured), `exp`, `iat`.
* Failure modes raise `ClerkAuthError` with an error code that the FastAPI
  dependency translates into a uniform `401 not_signed_in` body.

This module is intentionally framework-agnostic so the verifier can be
exercised from unit tests without a FastAPI app.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Final

import httpx
import jwt
from jwt import PyJWKSet

from momdiary.config import get_settings

_JWKS_PATH: Final[str] = "/.well-known/jwks.json"


class ClerkAuthError(Exception):
    """Raised when JWT verification fails for any reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ClerkClaims:
    """Typed projection of the verified JWT claims."""

    sub: str
    email: str
    email_verified: bool
    sid: str | None
    iss: str
    exp: int
    iat: int


class _JwksCache:
    """In-process JWKS cache with TTL + kid-miss force refresh.

    Thread/coroutine safety: the asyncio.Lock guards JWKS refresh so a
    burst of requests with a freshly-rotated key only triggers one HTTP
    fetch. Reads outside refresh are lock-free.
    """

    def __init__(self) -> None:
        self._jwks: PyJWKSet | None = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()
        self._client_factory = httpx.AsyncClient

    def install_transport(self, transport: httpx.BaseTransport) -> None:
        """Test hook: replace the httpx transport (e.g. MockTransport)."""

        def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            kwargs["transport"] = transport
            return httpx.AsyncClient(*args, **kwargs)

        self._client_factory = _factory  # type: ignore[assignment]

    def reset(self) -> None:
        self._jwks = None
        self._fetched_at = 0.0

    async def get_key(self, kid: str, *, issuer: str, ttl: int) -> Any:
        now = time.monotonic()
        if self._jwks is not None and (now - self._fetched_at) < ttl:
            try:
                return self._jwks[kid].key
            except KeyError:
                pass  # fall through to force-refresh
        async with self._lock:
            # Re-check after acquiring the lock (another coroutine may have refreshed).
            now = time.monotonic()
            if (
                self._jwks is not None
                and (now - self._fetched_at) < ttl
                and kid in {k.key_id for k in self._jwks.keys}
            ):
                return self._jwks[kid].key
            await self._refresh(issuer)
        try:
            assert self._jwks is not None
            return self._jwks[kid].key
        except KeyError as err:
            raise ClerkAuthError("unknown_kid", f"Unknown JWT kid: {kid}") from err

    async def _refresh(self, issuer: str) -> None:
        url = issuer.rstrip("/") + _JWKS_PATH
        async with self._client_factory(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as err:
                raise ClerkAuthError(
                    "jwks_unavailable",
                    f"Failed to fetch JWKS from {url}: {err}",
                ) from err
        self._jwks = PyJWKSet.from_dict(resp.json())
        self._fetched_at = time.monotonic()


_jwks_cache = _JwksCache()


def get_jwks_cache() -> _JwksCache:
    """Accessor for tests that need to install a MockTransport or reset state."""
    return _jwks_cache


async def verify_clerk_jwt(token: str) -> ClerkClaims:
    """Verify a Clerk-issued JWT against the cached JWKS.

    Raises `ClerkAuthError` on any failure (expired, wrong issuer, wrong
    audience, unknown kid, tampered signature, missing required claim).
    Returns a typed `ClerkClaims` projection on success.
    """
    settings = get_settings()
    issuer = settings.clerk_jwt_issuer
    if not issuer:
        raise ClerkAuthError(
            "auth_not_configured",
            "CLERK_JWT_ISSUER is not configured.",
        )

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as err:
        raise ClerkAuthError("malformed_token", str(err)) from err
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise ClerkAuthError("missing_kid", "JWT header missing 'kid'.")

    key = await _jwks_cache.get_key(
        kid, issuer=issuer, ttl=settings.clerk_jwks_cache_ttl_seconds
    )

    audience = settings.clerk_jwt_audience or None
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as err:
        raise ClerkAuthError("token_expired", "JWT is expired.") from err
    except jwt.InvalidIssuerError as err:
        raise ClerkAuthError("invalid_issuer", "JWT issuer mismatch.") from err
    except jwt.InvalidAudienceError as err:
        raise ClerkAuthError("invalid_audience", "JWT audience mismatch.") from err
    except jwt.InvalidSignatureError as err:
        raise ClerkAuthError("invalid_signature", "JWT signature invalid.") from err
    except jwt.MissingRequiredClaimError as err:
        raise ClerkAuthError("missing_claim", str(err)) from err
    except jwt.PyJWTError as err:
        raise ClerkAuthError("invalid_token", str(err)) from err

    sub = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_verified")
    if not isinstance(sub, str) or not sub:
        raise ClerkAuthError("missing_sub", "JWT 'sub' missing or not a string.")
    if not isinstance(email, str) or not email:
        raise ClerkAuthError("missing_email", "JWT 'email' claim missing.")
    if not isinstance(email_verified, bool):
        raise ClerkAuthError(
            "missing_email_verified",
            "JWT 'email_verified' claim missing or not a boolean.",
        )

    return ClerkClaims(
        sub=sub,
        email=email,
        email_verified=email_verified,
        sid=payload.get("sid") if isinstance(payload.get("sid"), str) else None,
        iss=str(payload["iss"]),
        exp=int(payload["exp"]),
        iat=int(payload["iat"]),
    )


__all__ = [
    "ClerkAuthError",
    "ClerkClaims",
    "get_jwks_cache",
    "verify_clerk_jwt",
]
