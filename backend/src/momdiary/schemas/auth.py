"""Auth-related request/response schemas (feature 006)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Argon2id practical floor: 12 chars; max 128 to bound hashing cost.
PasswordStr = Annotated[str, Field(min_length=12, max_length=128)]
DisplayNameStr = Annotated[str, Field(min_length=1, max_length=80)]
# IANA zone names are at most 64 chars in the tz database. We do not validate
# the value against `zoneinfo` here — invalid strings are silently ignored on
# the server side (FR-008) so a buggy client cannot block sign-in.
TimezoneStr = Annotated[str, Field(min_length=1, max_length=64)]


class RegisterRequest(_StrictModel):
    email: EmailStr
    password: PasswordStr
    display_name: DisplayNameStr
    timezone: TimezoneStr | None = None


class LoginRequest(_StrictModel):
    email: EmailStr
    password: PasswordStr
    timezone: TimezoneStr | None = None


class UserPublic(_StrictModel):
    id: int
    email: EmailStr
    display_name: str
    active_baby_id: int | None = None
    timezone: str | None = None


class AuthSessionInfo(_StrictModel):
    """Returned by POST /v1/auth/login, /register, and GET /v1/auth/me."""

    user: UserPublic


class ErrorResponse(_StrictModel):
    error: str
    message: str
    details: dict[str, object] | None = None
    correlation_id: str
