# Phase 1 — Data Model: Context-Aware Web Research

This feature **does not add any database tables, columns, or indexes**. It extends one in-memory dataclass that the existing session store already serializes opaquely into the `chat_sessions.turns` JSONB column.

## Entities

### `ChatTurn` (extended — in-memory dataclass)

Module: `backend/src/momdiary/agents/session_store.py`

| Field | Type | Source | Validation |
|---|---|---|---|
| `role` | `Literal["user", "assistant"]` | existing | required |
| `text` | `str` | existing | required; ≤ `momdiary_session_message_max_bytes` (4096) bytes UTF-8 |
| `correlation_id` | `str` | existing | required (UUID) |
| `created_at` | `datetime` (UTC, aware) | existing | required |
| `outcome` | `str \| None` | existing | one of {`research_answer`, `research_unavailable`, `scope_refused`, `safety_refused`, `no_sources_found`, …existing diary outcomes…} |
| `entry_type` | `str \| None` | existing | unchanged |
| `entry_id` | `int \| None` | existing | unchanged |
| **`sources`** | **`list[ResearchSource] \| None`** | **NEW** | `None` for any non-research assistant turn or any caregiver turn; for research assistant turns: 0–5 items, each item validated by `ResearchSource` below |

**Default**: `None` (so all pre-existing rows and all diary turns continue to validate).

**Serialization**: `dataclasses.asdict(turn)` (current behavior in `pg_session_store._turn_to_json`) automatically includes the new field. **Deserialization** in `_turn_from_json` adds one tolerant line: `sources=d.get("sources")`.

### `ResearchSource` (existing — Pydantic model)

Module: `backend/src/momdiary/api/research.py` (currently lives in the request/response models)

| Field | Type | Validation |
|---|---|---|
| `title` | `str` | 1 ≤ len ≤ 200 chars; non-empty after strip |
| `url` | `HttpUrl` | must be HTTPS; host must be present |

When persisted in `ChatTurn.sources`, stored as the plain `dict[str, str]` shape `{"title": "...", "url": "https://..."}` (Pydantic `model_dump(mode="json")`). The on-read direction (e.g. a future history endpoint) re-validates through `ResearchSource(**d)`.

### `AgeLabel` (NEW — in-memory dataclass)

Module: `backend/src/momdiary/services/baby_age.py`

| Field | Type | Validation |
|---|---|---|
| `value` | `int` | `≥ 0` |
| `unit` | `Literal["days", "weeks", "months", "years", "none"]` | required |
| `display` | `str` | empty string iff `unit == "none"`; otherwise human-readable (e.g. `"4 months"`, `"3 weeks"`, `"10 days"`, `"2 years"`) |

**Construction rules** (per Decision 7 in `research.md`):

```text
dob is None / future / invalid    → AgeLabel(0, "none", "")
delta < 14 days                   → AgeLabel(delta.days, "days", f"{n} days")
delta < 12 weeks (84 days)        → AgeLabel(delta.days // 7, "weeks", "...")
delta < 2 years (730 days)        → AgeLabel(months, "months", "...")
otherwise                         → AgeLabel(years, "years", "...")
```

Singular forms (`"1 day"`, `"1 week"`, etc.) when `value == 1`.

### `GuardrailVerdict` (NEW — in-memory dataclass)

Module: `backend/src/momdiary/agents/research_guardrail.py`

| Field | Type | Validation |
|---|---|---|
| `verdict` | `Literal["allow", "scope_refuse", "safety_refuse"]` | required |
| `reason` | `str` | required; ≤ 200 chars; logged but never surfaced to caregivers |

Refusal mapping (consumed by the runner):

| `verdict` | `outcome` field on the assistant `ChatTurn` | `agent_message` template | `sources` |
|---|---|---|---|
| `allow` | `research_answer` *(or one of the failure outcomes below if downstream errors)* | model-synthesized + appended `RESEARCH_DISCLAIMER` | filtered + clamped citations |
| `scope_refuse` | `scope_refused` | `"I can only help with baby-care research questions. Please rephrase as a question about your baby's care."` | `[]` |
| `safety_refuse` | `safety_refused` | `"I can't help with that request. If you have concerns about your baby's safety, please contact your pediatrician or an emergency line."` | `[]` |

## Relationships

```
ChatSession (existing)
  └── turns: deque[ChatTurn]   (in-memory; serialized to chat_sessions.turns JSONB)
                ├── (existing diary turn)            sources = None
                └── (NEW research turn)              sources = list[{title,url}] | []
```

No foreign keys, no joins. The session is keyed by `(session_id, user_id, baby_id)` via the existing `chat_sessions` table.

## State transitions

The research turn has no independent lifecycle — it is created, persisted in the same writer-side transaction as the diary turns, and read back via `recent_view(token_budget=...)`. The only invariant new to this feature:

- A research assistant turn with `outcome == "research_answer"` MUST have `len(sources) >= 1` (clamp upper bound is 5).
- A research assistant turn with `outcome in {"scope_refused", "safety_refused", "research_unavailable", "no_sources_found"}` MUST have `sources == []`.

These invariants are enforced by `research_runner.py` before `session.append(...)` is called, and verified by `tests/contract/test_research_api.py`.

## Migration & backward compatibility

- **No Alembic revision.** The Postgres schema is unchanged.
- **Old rows.** `chat_sessions.turns` JSONB rows written before this change have no `sources` key. `_turn_from_json` reads via `d.get("sources")` and substitutes `None`, which is the legal default for the extended `ChatTurn`.
- **Old code paths.** Diary turns continue to construct `ChatTurn(...)` without passing `sources`; the kwarg defaults to `None`.
- **Forward compatibility.** A future history-replay endpoint can serialize `sources` straight from the JSONB column with no additional schema work.

## Validation rules consolidated

Drawn from FRs in `spec.md` and reflected in code/tests:

| Rule | Source | Enforced where |
|---|---|---|
| Caregiver `message` ≤ 4000 chars | FR-001 | Pydantic `ResearchRequest` in `api/research.py` |
| Caregiver `message` ≤ 4096 bytes UTF-8 | FR-006 reuse of session-store cap | `pg_session_store.append` (existing) |
| Sanitized search query ≤ 200 chars | Decision 5 | `research_guardrail.redact_query` |
| Web search call ≤ 15 s | FR-014 | `asyncio.wait_for` in `research_runner` |
| Sources clamped to 3–5 (after filter) | FR-011a | `research_policy.filter_and_clamp` |
| Source URL must match allow-list and not match block-list | FR-012 | `research_policy.is_trusted_url` |
| Response includes disclaimer for every `research_answer` | FR-015, SC-008 | `research_runner.compose_final_message` |
| Refused/failed turns persisted | FR-022 | `research_runner.run` always calls `session.append` |
| Response schema preserved | FR-018 | `tests/contract/test_research_api.py` |
