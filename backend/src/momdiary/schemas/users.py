"""User-profile schemas (feature 006)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserUpdate(_StrictModel):
    """PATCH /v1/users/me — only display_name is editable in v1."""

    display_name: Annotated[str, Field(min_length=1, max_length=80)]


class SetActiveBabyRequest(_StrictModel):
    """POST /v1/users/me/active-baby."""

    baby_id: int
