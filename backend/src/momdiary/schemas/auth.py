"""Auth-related response schemas — feature 008 (Clerk JWT identity)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


DisplayNameStr = Annotated[str, Field(min_length=1, max_length=80)]


class UserPublic(_StrictModel):
    id: int
    email: EmailStr
    display_name: str
    email_verified: bool = False
    active_baby_id: int | None = None
    timezone: str | None = None


class AuthSessionInfo(_StrictModel):
    """Returned by GET /v1/users/me."""

    user: UserPublic


class CurrentUserOut(_StrictModel):
    """OpenAPI `CurrentUser` projection (feature 008 contract)."""

    id: int
    clerk_user_id: str
    email: EmailStr
    email_verified: bool
    display_name: str
    active_baby_id: int | None = None
    timezone: str | None = None


class ErrorResponse(_StrictModel):
    error: str
    message: str
    details: dict[str, object] | None = None
    correlation_id: str
