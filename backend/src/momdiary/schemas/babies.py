"""Baby-profile schemas (feature 006; extended for feature 010)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


DisplayNameStr = Annotated[str, Field(min_length=1, max_length=80)]
ColorTagStr = Annotated[str, Field(max_length=16)]

# Feature 010 — baby profile attributes. Validation lives here (Pydantic),
# not as DB CHECK constraints (see specs/010-baby-profile/data-model.md).
Gender = Literal["girl", "boy", "other"]
# Sane upper bounds keep typos out; lower bound is strictly positive.
WeightKg = Annotated[float, Field(gt=0, le=50)]
HeightCm = Annotated[float, Field(gt=0, le=200)]


class BabyCreate(_StrictModel):
    display_name: DisplayNameStr
    date_of_birth: date
    color_tag: ColorTagStr | None = None


class BabyUpdate(_StrictModel):
    """All fields optional — caller PATCHes whichever subset they edit.

    For the feature-010 fields, an explicit ``null`` clears the value back to
    unset (FR-014). The service distinguishes "omitted" from "explicit null"
    via ``model_fields_set``.
    """

    display_name: DisplayNameStr | None = None
    date_of_birth: date | None = None
    color_tag: ColorTagStr | None = None
    gender: Gender | None = None
    weight_kg: WeightKg | None = None
    height_cm: HeightCm | None = None


class BabyPublic(_StrictModel):
    id: int
    owner_user_id: int
    display_name: str
    date_of_birth: date
    color_tag: str | None = None
    gender: Gender | None = None
    # Cached "current" snapshot = the latest growth measurement.
    weight_kg: float | None = None
    height_cm: float | None = None
    # Growth history projection (feature 010): the latest measurement date and
    # the change vs the previous measurement, per metric. Null when there is no
    # prior measurement to diff against.
    last_measured_at: str | None = None
    weight_kg_delta: float | None = None
    height_cm_delta: float | None = None
    created_at: str
    updated_at: str


class BabyListResponse(_StrictModel):
    items: list[BabyPublic]
