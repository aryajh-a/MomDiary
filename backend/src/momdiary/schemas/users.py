"""User-profile schemas (feature 006)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserUpdate(_StrictModel):
    """PATCH /v1/users/me — display_name and/or timezone (feature 009).

    Both fields are optional so a timezone-only update (the post-sign-in
    capture) doesn't require resending the display name, and vice versa.
    """

    display_name: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    # IANA zone string, e.g. "Asia/Kolkata". Validated server-side; an
    # unparseable value is ignored rather than rejected (feature 009 FR-002).
    timezone: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class SetActiveBabyRequest(_StrictModel):
    """POST /v1/users/me/active-baby."""

    baby_id: int
