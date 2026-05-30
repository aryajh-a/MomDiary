"""Pydantic models for inbound Clerk webhook payloads (feature 008).

Clerk delivers events through Svix; the envelope has `type` (e.g.
`user.created`, `user.updated`, `user.deleted`) plus a `data` object whose
shape depends on the event. We model only the fields we consume; Pydantic
silently ignores the rest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class UserDeletedData(_Loose):
    id: str = Field(..., description="Clerk user id (`user_2abc...`).")
    deleted: bool | None = None
    object: str | None = None


class _EmailAddress(_Loose):
    id: str | None = None
    email_address: str | None = None
    verification: dict[str, object] | None = None


class UserUpdatedData(_Loose):
    id: str = Field(..., description="Clerk user id.")
    primary_email_address_id: str | None = None
    email_addresses: list[_EmailAddress] = Field(default_factory=list)


class ClerkWebhookEnvelope(_Loose):
    type: Literal[
        "user.created",
        "user.updated",
        "user.deleted",
        # Unknown event types are accepted; the dispatcher decides what to do.
    ] | str
    data: dict[str, object]


__all__ = [
    "ClerkWebhookEnvelope",
    "UserDeletedData",
    "UserUpdatedData",
    "_EmailAddress",
]
