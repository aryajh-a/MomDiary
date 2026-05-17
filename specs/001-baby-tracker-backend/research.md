# Phase 0 Research: Baby Tracker Agentic Backend

**Feature**: 001-baby-tracker-backend
**Date**: 2026-05-16
**Status**: Complete

This document resolves the open technical questions that were either marked
`NEEDS CLARIFICATION` in `plan.md` Technical Context (initial draft) or
implied by combining the spec, the user-supplied stack (Python, FastAPI,
Microsoft Agent Framework, Azure AI GPT-4.1, SQLite), and the project
constitution.

---

## 1. Microsoft Agent Framework for Python — package choice & version channel

- **Decision**: Use the Microsoft Agent Framework (MAF) Python package family
  (`agent-framework` and its `agent-framework-azure-ai` extension) from the
  PyPI prerelease channel (`pip install --pre agent-framework
  agent-framework-azure-ai`). Pin to the latest published prerelease at
  implementation start and record the resolved versions in `requirements.lock`
  / `uv.lock` (or `pip-tools`-generated lockfile).
- **Rationale**: Principle V mandates Microsoft Agent Framework on the
  prerelease channel. MAF's Python distribution is the supported way to build
  agents and tools from Python (FastAPI), and the `azure-ai` extension is the
  Microsoft-supported connector to Azure AI Foundry models (gpt-4.1).
- **Alternatives considered**:
  - Semantic Kernel Python — predecessor framework, allowed prereleases but
    superseded by MAF for new agent work; rejected to stay aligned with
    Principle V's "Microsoft Agent Framework First".
  - LangChain / LlamaIndex — non-Microsoft frameworks; prohibited by
    Principle V without a constitutional amendment.
  - MAF stable-only — would lag the capabilities (tool routing, streaming,
    structured-output helpers) the agent needs; explicitly contrary to
    Principle V's prerelease baseline.

## 2. Azure AI GPT-4.1 client

- **Decision**: Reach Azure-hosted `gpt-4.1` via `agent-framework-azure-ai`'s
  `AzureOpenAIChatClient` (or equivalent MAF Azure chat client), authenticated
  using `azure-identity`'s `DefaultAzureCredential`. The deployment name and
  endpoint come from environment variables
  (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT=gpt-4.1`,
  `AZURE_OPENAI_API_VERSION`). API keys are NOT committed; if used in dev,
  they go through `AZURE_OPENAI_API_KEY` env var per the constitution's
  secrets rule.
- **Rationale**: Microsoft-supported client per Principle V; managed identity
  / `DefaultAzureCredential` keeps secrets out of code; env-var configuration
  matches the constitution's secret-handling and reproducibility rules.
- **Alternatives considered**:
  - Direct REST calls to Azure OpenAI — bypasses MAF tool plumbing; rejected.
  - Pure `openai` SDK pointed at Azure — works but loses MAF integration
    benefits and forces hand-rolled tool routing; rejected.

## 3. Suppressing preview-API warnings from MAF

- **Decision**: Suppress only Python warnings whose `__module__` originates
  in `agent_framework*` (or that carry MAF-specific category classes such as
  `ExperimentalWarning`). Configure suppression in two places:
  1. `pyproject.toml` under `[tool.pytest.ini_options]` `filterwarnings`,
     with explicit `ignore::agent_framework...` entries.
  2. A one-time `warnings.filterwarnings("ignore", module=r"agent_framework.*")`
     call inside the application's startup module (`momdiary/observability/
     logging.py` or `main.py`), narrowly scoped by `module=` regex.
  Maintain a `docs/AGENT_FRAMEWORK_WARNINGS.md` listing each suppressed
  category and why, per Principle V.
- **Rationale**: Principle V requires the narrowest possible scope and
  documentation for every suppression, AND prohibits suppressing warnings
  from non-MAF libraries. Module-scoped filters meet both bars.
- **Alternatives considered**:
  - Global `warnings.simplefilter("ignore")` — prohibited by Principle V.
  - Per-call `with warnings.catch_warnings()` — workable but noisier in
    code; reserved for cases where module-scope is too broad.

## 4. Web framework wiring (FastAPI)

- **Decision**: FastAPI app exposes one conversational write endpoint
  (`POST /v1/entries` for create, `PUT /v1/entries` for update, both
  delegating to the same MAF agent) and four GET-by-date endpoints
  (`/v1/feeds`, `/v1/sleeps`, `/v1/poops`, `/v1/appointments`). The agent
  is instantiated once per process and reused across requests via a
  FastAPI dependency that injects an agent runner.
- **Rationale**: Matches FR-001 (single conversational write endpoint) and
  FR-008 (per-type date-scoped GETs). Reusing one agent instance keeps
  latency low and is consistent with MAF's recommended pattern.
- **Alternatives considered**:
  - One write endpoint per event type — rejected, violates FR-001's "single
    POST/PUT API" requirement and the user's stated intent.
  - WebSocket / SSE write surface — out of scope for v1; HTTP keeps the
    contract testable.

## 5. SQLite + SQLAlchemy

- **Decision**: Use SQLAlchemy 2.x (async via `aiosqlite`) as the ORM with
  Alembic for migrations. Database file lives at the path in `MOMDIARY_DB_URL`
  (default `sqlite+aiosqlite:///./momdiary.db`). Each request gets a scoped
  `AsyncSession` via FastAPI dependency. Repository pattern isolates SQL
  from the agent tool layer (Principle IV: modular, pluggable persistence).
- **Rationale**: SQLAlchemy is the industry-standard pluggable persistence
  layer in Python and lets us swap SQLite for Postgres later without
  touching the agent or API code (Principle IV). Alembic versions the
  schema, which the constitution's reproducibility rule requires.
- **Alternatives considered**:
  - Raw `sqlite3` / `aiosqlite` — fastest to write, but couples SQL into the
    repository layer and frustrates future engine swaps. Rejected.
  - SQLModel — thin wrapper over SQLAlchemy + Pydantic; viable but adds a
    prerelease-ish dependency; deferred to a follow-up if duplication
    between ORM and Pydantic schemas becomes painful.
  - Tortoise ORM — non-Microsoft, smaller ecosystem; rejected.

## 6. Time zone handling (FR-012 clarified)

- **Decision**: Hold `default_timezone` (IANA string, e.g.
  `America/Los_Angeles`) in a singleton `settings` row in SQLite, seeded on
  first run from the `MOMDIARY_DEFAULT_TIMEZONE` env var (fallback: `UTC`).
  All timestamps stored as `TIMESTAMP WITH TIME ZONE`-equivalent ISO-8601
  strings carrying the offset that applied at the original local time.
  GETs use the configured zone to compute "the requested date's window".
- **Rationale**: Matches the clarification's Option A (server-side single
  setting) and FR-012's requirement that responses carry explicit offsets.
- **Alternatives considered**:
  - Store as UTC, render local on read — viable, but reconstructing the
    original local offset for ambiguous historical moments (DST) is fragile.
    Storing with the offset that applied at write time is unambiguous.

## 7. Testing strategy

- **Decision**:
  - `pytest` + `pytest-asyncio` for unit + integration; `httpx.AsyncClient`
    for FastAPI integration tests.
  - Contract tests: a `tests/contract/test_openapi.py` validates the live
    FastAPI app's `/openapi.json` against `specs/.../contracts/openapi.yaml`.
  - Agent contract tests: each MAF tool has tests that exercise the tool
    function directly with realistic structured arguments; tests of the
    full agent loop use a stub model client (MAF supports a fake / test
    client) that returns scripted tool-call sequences — NO live model
    calls in CI (Principle II).
  - Coverage measured by `coverage.py` via `pytest-cov`; CI fails on net
    decrease or absolute thresholds (≥80% line, ≥70% branch on changed
    packages, gated in CI configuration).
- **Rationale**: Satisfies Principle II's three test tiers, deterministic-
  only agent tests, and coverage floors. `pytest-cov`'s diff-based
  reporting handles the "no net decrease" rule.
- **Alternatives considered**:
  - Use VCR-style recorded model responses — viable for evaluation suites,
    but for CI deterministic stubs are simpler and faster.

## 8. Linting / formatting / static analysis

- **Decision**: `ruff` (lint + format), `mypy --strict` on `src/momdiary/`,
  pre-commit hooks. CI fails on any ruff or mypy diagnostic.
- **Rationale**: Principle I requires CI to fail (not warn) on lint and
  format violations, plus type-checking is the cheapest way to keep
  cyclomatic complexity and contract drift in check.

## 9. Performance benchmarking

- **Decision**:
  - Micro-benchmark for date-scoped GETs (target SC-003: < 500 ms p95 with
    50 entries) using `pytest-benchmark` against a populated SQLite file.
  - Latency timer in the agent dispatcher emitting wall-clock time per
    invocation (excluding model time) into the structured log (FR-013).
  - A CI check that fails on > 10% regression of the tracked
    `pytest-benchmark` baseline (Principle III).
- **Rationale**: Encodes Principle III's "performance budgets MUST be
  encoded as automated checks where feasible".

## 10. Observability

- **Decision**: Structured JSON logging via `structlog` (or stdlib `logging`
  with `python-json-logger`) with a request-scoped correlation id middleware.
  Each agent invocation logs: correlation id, agent name, model deployment
  id, latency_ms, prompt_tokens / completion_tokens when MAF surfaces them,
  outcome (`created` / `updated` / `deleted` / `clarification_requested` /
  `rejected`). Persisted to stdout (container-friendly).
- **Rationale**: Implements FR-013 and the constitution's observability
  clause; stdout JSON works in dev and any future container host.

## 11. Idempotency for PUT (FR-015)

- **Decision**: Idempotency is enforced at the repository layer: PUT
  compares the supplied entry id's current canonical payload to the
  incoming payload; if they match exactly (after server-side
  normalization), no UPDATE is issued and the existing `updated_at`
  is preserved. The response is byte-identical to the previous PUT's
  response.
- **Rationale**: SC-006 requires byte-identical responses on repeated
  PUTs. Keeping the comparison server-side avoids client-side keying
  issues and works for both id-supplied and agent-resolved PUTs.

## 12. Dependency lock & reproducibility

- **Decision**: Manage dependencies with `uv` (or `pip-tools` if `uv`
  unavailable). Commit `uv.lock` / `requirements.lock`. Pin MAF prerelease
  versions explicitly. Record resolved versions in
  `docs/AGENT_FRAMEWORK_WARNINGS.md` (or a sibling `RELEASE_NOTES.md`)
  per the constitution's "record the exact prerelease versions consumed".
- **Rationale**: Principle V plus constitution's reproducibility rule.

---

## Open items deferred to implementation

None at the spec level. All `NEEDS CLARIFICATION` markers have been
resolved in the spec or in this research file.
