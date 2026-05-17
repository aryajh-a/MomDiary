# Implementation Plan: Baby Tracker Agentic Backend

**Branch**: `001-baby-tracker-backend` | **Date**: 2026-05-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-baby-tracker-backend/spec.md`

## Summary

MomDiary v1 backend is a single-user FastAPI service that exposes one
conversational write endpoint (`POST/PUT /v1/entries`) driven by a
Microsoft Agent Framework (MAF) "Diary Agent" plus four date-scoped GET
endpoints (`/v1/feeds`, `/v1/sleeps`, `/v1/poops`, `/v1/appointments`).
The Diary Agent uses Azure AI Foundry's `gpt-4.1` deployment to route
natural-language messages to typed tools (`log_*`, `update_*`,
`delete_*`, `add_appointment_note`, `ask_for_clarification`) that
persist to a local SQLite database via SQLAlchemy 2.x (async) +
Alembic migrations. All clarification answers from Session 2026-05-16
are honored: single-user with nullable `caregiver_id`, hybrid
`entry_id`-optional PUT contract, soft delete via the agent,
server-side `default_timezone`, indefinite retention.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Microsoft Agent Framework (`agent-framework`, `agent-framework-azure-ai`, prerelease per constitution), `azure-identity`, SQLAlchemy 2.x (async) + `aiosqlite`, Alembic, Pydantic v2, `structlog` (or `python-json-logger`)
**Storage**: SQLite (local file via `sqlite+aiosqlite`), Alembic-managed schema
**Testing**: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-benchmark`, `httpx.AsyncClient` for FastAPI; MAF stub model client (no live model in CI)
**Target Platform**: Linux/macOS/Windows local dev host; Linux container-ready
**Project Type**: Web-service (single backend; no frontend in this feature)
**Performance Goals**: SC-002 write p95 < 5 s end-to-end excluding model time; SC-003 GET-by-date p95 < 500 ms for ≤ 50 entries/day; agent streams first token within 1 s when model supports it (Principle III)
**Constraints**: Single SQLite file; one configured `default_timezone`; no live model calls in CI; warnings suppressed only for MAF packages (Principle V); structured JSON log per request (FR-013); idempotent PUTs (FR-015, SC-006)
**Scale/Scope**: 1 caregiver, 1 baby, ≤ 50 entries/day (v1); indefinite retention (FR-019); 4 entity types + 1 child table + 1 audit table + 1 settings singleton

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates are derived from the [MomDiary Constitution](../../.specify/memory/constitution.md) v1.0.0.

| # | Gate (Principle) | Status | How this plan satisfies it |
|---|------------------|--------|----------------------------|
| 1 | I. Code Quality & Maintainability | PASS | `ruff` (lint + format) and `mypy --strict` configured; CI fails on diagnostics; public APIs (agent tools, repositories, FastAPI routes) get docstrings; complexity kept low by repository + tools split. |
| 2 | II. Testing Standards (NON-NEGOTIABLE) | PASS | `pytest` tiers (unit, integration, contract); MAF stub model client for deterministic agent tests; coverage gates ≥ 80% line / ≥ 70% branch on changed packages; contract tests for OpenAPI surface and every agent tool. |
| 3 | III. Performance Requirements | PASS | `pytest-benchmark` baseline for GET-by-date (SC-003); per-invocation `latency_ms` and `model_latency_ms` logged + persisted (`agent_interactions`); CI fails on > 10% regression on tracked benchmarks; SQLite indexes on `(deleted_at, occurred_at\|start_at\|scheduled_at)`. |
| 4 | IV. Modular Architecture | PASS | Layered modules: `api/` (FastAPI routes), `agents/` (MAF agent + tools), `services/` (time, target resolver), `db/` (engine, repositories), `models/` (Pydantic/ORM), `observability/`. No cyclic deps; tools and model client are pluggable; persistence sits behind repository interfaces so SQLite can be swapped later. |
| 5 | V. Microsoft Agent Framework First (NON-NEGOTIABLE) | PASS | Only MAF used for agent functionality; prerelease pin via `uv` lockfile; `pip install --prerelease=allow`; warning suppression scoped to `agent_framework.*` module only and documented in `docs/AGENT_FRAMEWORK_WARNINGS.md`; Azure AI `gpt-4.1` reached via Microsoft-supported `agent-framework-azure-ai` client; resolved versions recorded for reproducibility. |

Additional constraints (Technology & Dependency Constraints / Development Workflow & Quality Gates):

- Approved agent stack only → MAF + `agent-framework-azure-ai` (no LangChain etc.).
- Dependencies pinned via `uv.lock`; transitive upgrades reviewed in PRs.
- Secrets (`AZURE_OPENAI_API_KEY`, etc.) only via env / managed identity; never logged or in prompts.
- Per-invocation structured JSON log with correlation id, agent name, model id, latency, token usage, outcome (FR-013 + Observability clause).
- Branching `001-baby-tracker-backend`; CI gates 1–4 enforced before merge.

**Result**: All gates PASS. No entries required in Complexity Tracking.

**Post-Design re-evaluation (after Phase 1 artifacts)**: Re-checked against the
generated `data-model.md`, `contracts/openapi.yaml`, and `contracts/agent-tools.md`.
No new violations introduced. Modular layout from `data-model.md` (repositories
per entity, dispatcher between API and tools) still satisfies Principle IV; the
OpenAPI contract preserves the single conversational write endpoint
(Principle V intent); tool contracts each support a deterministic argument
path enabling Principle II contract tests. Result remains PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-baby-tracker-backend/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── openapi.yaml     # Phase 1 output: HTTP contract
│   └── agent-tools.md   # Phase 1 output: MAF tool contracts
├── checklists/
│   └── requirements.md  # /speckit.specify quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks, NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── momdiary/
│       ├── __init__.py
│       ├── main.py                  # FastAPI app factory + lifespan
│       ├── config.py                # Pydantic Settings, env-var bindings
│       ├── api/
│       │   ├── __init__.py
│       │   ├── entries.py           # POST/PUT /v1/entries (agent-driven)
│       │   ├── feeds.py             # GET /v1/feeds
│       │   ├── sleeps.py            # GET /v1/sleeps
│       │   ├── poops.py             # GET /v1/poops
│       │   └── appointments.py      # GET /v1/appointments
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── diary_agent.py       # MAF agent wiring + Azure AI client
│       │   ├── dispatcher.py        # Per-request invocation, logs to agent_interactions
│       │   └── tools/
│       │       ├── feeds.py         # log/update/delete_feed
│       │       ├── sleeps.py
│       │       ├── poops.py
│       │       └── appointments.py  # incl. add_appointment_note
│       ├── services/
│       │   ├── time_service.py      # default_timezone + relative-time parsing helpers
│       │   ├── target_resolver.py   # FR-017 / FR-018 disambiguation
│       │   └── normalization.py     # oz→ml, unit casing, etc.
│       ├── models/
│       │   ├── orm.py               # SQLAlchemy models
│       │   └── schemas.py           # Pydantic request/response models
│       ├── db/
│       │   ├── engine.py            # Async engine + session factory
│       │   └── repositories/
│       │       ├── feeds.py
│       │       ├── sleeps.py
│       │       ├── poops.py
│       │       ├── appointments.py
│       │       └── agent_interactions.py
│       └── observability/
│           ├── logging.py           # structlog config + MAF warning filter
│           └── middleware.py        # correlation-id middleware
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── contract/
│   │   ├── test_openapi.py
│   │   └── test_agent_tools.py
│   ├── integration/
│   │   ├── test_agent_routing.py    # SC-001
│   │   ├── test_ambiguous_inputs.py # SC-004
│   │   ├── test_full_day.py         # SC-005
│   │   ├── test_put_idempotency.py  # SC-006
│   │   └── test_soft_delete.py      # FR-018
│   ├── unit/
│   │   ├── test_time_service.py
│   │   ├── test_target_resolver.py
│   │   └── test_normalization.py
│   └── benchmarks/
│       └── test_get_by_date.py      # SC-003 / Principle III gate
├── docs/
│   └── AGENT_FRAMEWORK_WARNINGS.md  # Principle V documentation
├── pyproject.toml
├── uv.lock
└── requirements.txt
```

**Structure Decision**: Single-project web service. Backend-only feature;
no frontend in this slice. Source under `backend/src/momdiary/` (importable
package), tests under `backend/tests/` mirroring module boundaries
(Principle IV). Alembic migrations colocated with the backend.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                              |
