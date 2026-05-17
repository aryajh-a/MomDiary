"""Pydantic request/response schemas mirroring contracts/openapi.yaml."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

EntryType = Literal["feed", "sleep", "poop", "appointment"]
FeedType = Literal["breast_milk", "formula", "solids", "water"]
FeedUnit = Literal["ml", "g"]
PoopConsistency = Literal["watery", "soft", "formed", "hard"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Request / response envelopes
# ---------------------------------------------------------------------------


class AgentWriteRequest(_StrictModel):
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    entry_id: int | None = None
    entry_type: EntryType | None = None
    correlation_id: str | None = None


class SuggestedCandidate(_StrictModel):
    entry_type: EntryType
    entry_id: int
    summary: str


class AgentClarificationResponse(_StrictModel):
    outcome: Literal["clarification_requested"]
    agent_message: str
    suggested_candidates: list[SuggestedCandidate] | None = None
    correlation_id: str


class ErrorResponse(_StrictModel):
    error: str
    message: str
    details: dict[str, object] | None = None
    correlation_id: str


# ---------------------------------------------------------------------------
# Entry payloads (GET responses + AgentWriteResponse.entry)
# ---------------------------------------------------------------------------


class FeedEntry(_StrictModel):
    id: int
    entry_type: Literal["feed"] = "feed"
    feed_type: FeedType
    quantity: Annotated[float, Field(gt=0)]
    unit: FeedUnit
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class SleepEntry(_StrictModel):
    id: int
    entry_type: Literal["sleep"] = "sleep"
    start_at: datetime
    end_at: datetime
    duration_minutes: Annotated[int, Field(ge=1)]
    created_at: datetime
    updated_at: datetime


class PoopEntry(_StrictModel):
    id: int
    entry_type: Literal["poop"] = "poop"
    occurred_at: datetime
    consistency: PoopConsistency
    created_at: datetime
    updated_at: datetime


class AppointmentNote(_StrictModel):
    id: int
    body: Annotated[str, Field(min_length=1, max_length=2000)]
    added_at: datetime


class AppointmentEntry(_StrictModel):
    id: int
    entry_type: Literal["appointment"] = "appointment"
    scheduled_at: datetime
    notes: list[AppointmentNote] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


EntryPayload = FeedEntry | SleepEntry | PoopEntry | AppointmentEntry


class AgentWriteResponse(_StrictModel):
    outcome: Literal["created", "updated", "deleted"]
    entry_type: EntryType
    entry: EntryPayload
    agent_message: str | None = None
    correlation_id: str


# ---------------------------------------------------------------------------
# GET-by-date list envelopes
# ---------------------------------------------------------------------------


class FeedListResponse(_StrictModel):
    date: str
    items: list[FeedEntry]


class SleepListResponse(_StrictModel):
    date: str
    items: list[SleepEntry]


class PoopListResponse(_StrictModel):
    date: str
    items: list[PoopEntry]


class AppointmentListResponse(_StrictModel):
    date: str
    items: list[AppointmentEntry]
