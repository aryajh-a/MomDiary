"""Baby-profile schemas (feature 006)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


DisplayNameStr = Annotated[str, Field(min_length=1, max_length=80)]
ColorTagStr = Annotated[str, Field(max_length=16)]


class BabyCreate(_StrictModel):
    display_name: DisplayNameStr
    date_of_birth: date
    color_tag: ColorTagStr | None = None


class BabyUpdate(_StrictModel):
    """All fields optional — caller PATCHes whichever subset they edit."""

    display_name: DisplayNameStr | None = None
    date_of_birth: date | None = None
    color_tag: ColorTagStr | None = None


class BabyPublic(_StrictModel):
    id: int
    owner_user_id: int
    display_name: str
    date_of_birth: date
    color_tag: str | None = None
    created_at: str
    updated_at: str


class BabyListResponse(_StrictModel):
    items: list[BabyPublic]
