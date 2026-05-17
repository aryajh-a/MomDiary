# Quickstart: MomDiary Baby Tracker Backend

**Feature**: 001-baby-tracker-backend
**Date**: 2026-05-16

This quickstart shows how to run the backend locally and walk through the
primary user journeys validated in `spec.md` (User Stories 1–3).

This document references the [MomDiary Constitution](../../.specify/memory/constitution.md);
all commands and conventions below comply with Principles I–V.

---

## Prerequisites

- Python 3.12 (64-bit)
- `uv` (recommended) or `pip` + `pip-tools`
- An Azure AI Foundry project with a `gpt-4.1` deployment
- Either Azure CLI logged in (`az login`) for `DefaultAzureCredential`,
  or an Azure OpenAI API key for dev

## 1. Install dependencies

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install --prerelease=allow -r requirements.txt
```

Microsoft Agent Framework packages are resolved from the prerelease
channel per the constitution (Principle V). The exact resolved versions
are pinned in `uv.lock` and listed in `docs/AGENT_FRAMEWORK_WARNINGS.md`.

## 2. Configure environment

Create `.env` (never commit) with:

```ini
AZURE_OPENAI_ENDPOINT=https://<your-foundry>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2024-10-21
# Optional dev fallback (constitution-compliant when via env var):
# AZURE_OPENAI_API_KEY=...

MOMDIARY_DB_URL=sqlite+aiosqlite:///./momdiary.db
MOMDIARY_DEFAULT_TIMEZONE=America/Los_Angeles
```

## 3. Initialize the database

```powershell
alembic upgrade head
```

This creates the SQLite file and the singleton `settings` row, seeded
from `MOMDIARY_DEFAULT_TIMEZONE`.

## 4. Run the server

```powershell
uvicorn momdiary.main:app --reload --port 8000
```

The OpenAPI doc is available at `http://localhost:8000/docs`. Its schema
MUST match [contracts/openapi.yaml](contracts/openapi.yaml) (validated by
`tests/contract/test_openapi.py`).

---

## Walkthrough — User Story 1 (P1): log events via the agent

Log a feed:

```powershell
curl.exe -X POST http://localhost:8000/v1/entries `
  -H "content-type: application/json" `
  -d '{"message":"Fed 90 ml of breast milk at 8:05 am"}'
```

Expected (truncated):

```json
{
  "outcome": "created",
  "entry_type": "feed",
  "entry": {
    "id": 1, "entry_type": "feed", "feed_type": "breast_milk",
    "quantity": 90, "unit": "ml",
    "occurred_at": "2026-05-16T08:05:00-07:00", ...
  },
  "agent_message": "Logged a 90 ml breast milk feed at 8:05 AM.",
  "correlation_id": "..."
}
```

Repeat for the other event types ("Slept from 1pm to 2:45pm",
"Poop at 9am, runny", "Pediatrician appointment on May 20 at 4pm, ask
about vaccine schedule") to verify all four tools.

## Walkthrough — User Story 2 (P1): read by date

```powershell
curl.exe "http://localhost:8000/v1/feeds?date=2026-05-16"
curl.exe "http://localhost:8000/v1/sleeps?date=2026-05-16"
curl.exe "http://localhost:8000/v1/poops?date=2026-05-16"
curl.exe "http://localhost:8000/v1/appointments?date=2026-05-20"
```

Each returns `{ "date": "...", "items": [...] }`. Empty `items` for a date
with no entries is a successful 200, not a 404 (FR-008, edge case).

## Walkthrough — User Story 3 (P2): correct an entry

Given the feed from Story 1 (id 1):

```powershell
curl.exe -X PUT http://localhost:8000/v1/entries `
  -H "content-type: application/json" `
  -d '{"message":"Actually the 8 am feed was 120 ml"}'
```

The agent resolves the target from the message (FR-017 hybrid: `entry_id`
absent → agent infers). Expected `outcome: "updated"` with the new
quantity. Re-issuing the same PUT is idempotent (FR-015, SC-006).

A deterministic variant (always works regardless of agent inference):

```powershell
curl.exe -X PUT http://localhost:8000/v1/entries `
  -H "content-type: application/json" `
  -d '{"message":"Set quantity to 120 ml","entry_id":1,"entry_type":"feed"}'
```

Soft-delete an entry:

```powershell
curl.exe -X PUT http://localhost:8000/v1/entries `
  -H "content-type: application/json" `
  -d '{"message":"Remove the 8 am feed"}'
```

After this, the feed disappears from `GET /v1/feeds?date=...` (FR-018).

---

## Running the test suite

```powershell
pytest --cov=src/momdiary --cov-branch --cov-report=term-missing
```

CI gates (Principle II):
- ≥ 80% line coverage on changed packages
- ≥ 70% branch coverage on changed packages
- No live model calls (the agent uses a stub model client in CI)
- No flaky tests outside the explicit `quarantine` marker (which does not
  count toward coverage)

Lint + format + types (Principle I):

```powershell
ruff check src tests
ruff format --check src tests
mypy src
```

Benchmarks (Principle III):

```powershell
pytest tests/benchmarks --benchmark-only
```

A > 10% regression on a tracked benchmark fails CI.

---

## Validating success criteria

| Criterion | How to validate from this quickstart |
| --------- | ------------------------------------ |
| SC-001    | Run the curated agent-routing test set under `tests/integration/test_agent_routing.py`; ≥ 95% correct first-attempt routing. |
| SC-002    | The `agent_interactions.latency_ms` column for each Story 1 call; p95 across the suite < 5000 ms excluding model time. |
| SC-003    | `pytest tests/benchmarks/test_get_by_date.py`; reports p95 < 500 ms for 50-entry days. |
| SC-004    | `tests/integration/test_ambiguous_inputs.py` confirms 100% of ambiguous inputs return `clarification_requested`. |
| SC-005    | `tests/integration/test_full_day.py` seeds ≥ 20 mixed events and asserts all four GETs together return them exactly once, ordered. |
| SC-006    | `tests/integration/test_put_idempotency.py` issues identical PUTs twice and asserts byte-identical responses. |

---

## Where things live

- API layer: `backend/src/momdiary/api/`
- Agent + tools: `backend/src/momdiary/agents/`
- Repositories: `backend/src/momdiary/db/repositories/`
- Models / schemas: `backend/src/momdiary/models/`
- Config + observability: `backend/src/momdiary/config.py`, `backend/src/momdiary/observability/`
- Migrations: `backend/alembic/`
- Tests: `backend/tests/{contract,integration,unit,benchmarks}/`
