# Implementation Plan: Context-Aware Web Research

**Branch**: `011-research-web-context` | **Date**: 2026-06-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from [specs/011-research-web-context/spec.md](spec.md)

## Summary

Replace the `/v1/research` placeholder with a real Microsoft Agent Framework (MAF) agent that grounds answers in live web results via the **Azure Foundry Agent Service Web Search tool**. Each request: (1) reads conversation history from the existing chat session store, (2) computes the active baby's friendly age from `babies.date_of_birth`, (3) runs a lightweight LLM guardrail (parenting-scope + baby-safety), (4) PII-rewrites the query, (5) issues a context-aware web search bounded by a 15s timeout, (6) filters and clamps sources to 3–5 entries from a maintained allow-list, (7) appends a fixed not-medical-advice reminder, and (8) persists the (question, answer, sources) turn back into `chat_sessions`. The response schema (`outcome`, `agent_message`, `sources[]`, `correlation_id`, `session_id`) is preserved so the existing frontend works unchanged.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged); TypeScript 5.4 (frontend, unchanged for this feature)
**Primary Dependencies**: FastAPI; `agent-framework-core==1.0.0rc6`; `agent-framework-azure-ai==1.0.0rc6` (Principle V — MAF-first, prerelease channel); `azure-identity`; `azure-ai-projects` (new — for `WebSearchTool` model + Foundry chat client surface); SQLAlchemy 2.x async; Pydantic v2; `structlog`
**Storage**: Azure Database for PostgreSQL Flexible Server (single datastore per feature 009). No new tables, no Alembic migration. Research turns reuse the existing `chat_sessions` JSONB row with an extended `ChatTurn` carrying an optional `sources: list[{title,url}]` field.
**Testing**: `pytest`, `pytest-asyncio`, contract/unit/integration tiers + opt-in `tests/evals/` for live-model checks (Constitution II)
**Target Platform**: Linux server (Azure App Service / containerized FastAPI worker)
**Project Type**: Web application (existing `backend/` + `frontend/`); only backend changes for this feature
**Performance Goals**: p50 end-to-end < 10 s per research turn (SC-006); web-search call capped at 15 s (FR-014); first-byte from the FastAPI handler ≤ 200 ms on the synchronous code paths before delegating to the model (Constitution III)
**Constraints**: No PII forwarded to the external search backend (FR-010); 100% of responses include the medical-advice reminder (SC-008); refused turns persisted as session history (FR-022); reuse existing session store, no new tables (FR-006); preserve response schema (FR-018) so frontend ships unchanged
**Scale/Scope**: Per active user, ≤ 1 in-flight research request at a time (single chat surface); peak concurrency bounded by gunicorn worker count (4) × instances (2) ≈ 8 parallel research calls; conversation history capped by `momdiary_session_max_turns` (50 pairs).

## Constitution Check

Mapped to Principles I–V from `.specify/memory/constitution.md`.

| Gate | Principle | How this plan satisfies it |
|---|---|---|
| Code quality / lint / docstrings | I | New modules (`research_agent.py`, `research_runner.py`, `research_guardrail.py`, `research_policy.py`, `services/baby_age.py`) carry docstrings on public callables; ruff/black enforced by existing CI; no new function exceeds cyclomatic 10 (helpers are pure and small). |
| Test-first, tiered coverage | II (NON-NEGOTIABLE) | Phase 1 generates contract tests in `backend/tests/contract/test_research_api.py` (response schema, refused-turn shape), unit tests for `baby_age.py`, `research_policy.py`, `research_guardrail.py` (mocked LLM), and an integration test in `backend/tests/integration/test_research_e2e.py` with the WebSearchTool mocked. An opt-in live-model evaluation suite under `backend/tests/evals/test_research_eval.py` exercises SC-002/003/004/009 against the real Foundry web search (gated by env flag — not run in CI). |
| Performance budgets | III | The synthesis call is the only > 1 s operation; we instrument latency for the guardrail step, the search call, the synthesis call, and the post-filter step separately, asserting `web_search_call_ms ≤ 15_000` (FR-014). A micro-benchmark for `baby_age.compute(...)` and `research_policy.filter_and_clamp(...)` lands in `backend/tests/benchmarks/`. |
| Modular architecture, swappable seams | IV | Search backend is hidden behind a single `WebSearchPort` interface (Phase 1) so swapping `WebSearchTool` → `BingGroundingTool` → MCP web-search server is a one-file change. Guardrail and policy are independently injectable into the runner. |
| Microsoft Agent Framework first, prerelease channel | V (NON-NEGOTIABLE) | The research agent is constructed with MAF primitives (`agent_framework.Agent` + a Foundry-aware chat client) on the same `1.0.0rc6` pin as the diary agent. No alternative agent framework introduced. New dependency `azure-ai-projects` is the official Azure SDK that hosts the `WebSearchTool` model type and is the canonical companion to MAF's Foundry client. Warning suppressions remain governed by `backend/docs/AGENT_FRAMEWORK_WARNINGS.md`. |

**Result: PASS (no gate violations).** Complexity Tracking table below is therefore empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-research-web-context/
├── plan.md              # This file
├── research.md          # Phase 0 — backend & guardrail decisions
├── data-model.md        # Phase 1 — ChatTurn extension + in-memory dataclasses
├── quickstart.md        # Phase 1 — local + Azure setup + smoke flow
├── contracts/
│   ├── research-api.md  # POST /v1/research request/response/error contract
│   └── session-store.md # Backward-compatible ChatTurn JSONB shape
├── checklists/
│   └── requirements.md  # Already authored at /speckit.specify time
└── tasks.md             # Phase 2 — written by /speckit.tasks (NOT now)
```

### Source Code (repository root)

```text
backend/
├── src/momdiary/
│   ├── api/
│   │   └── research.py                    # CHANGED — now a thin dispatcher (FR-001)
│   ├── agents/
│   │   ├── research_agent.py              # NEW — MAF agent factory with WebSearchTool
│   │   ├── research_runner.py             # NEW — per-request orchestration
│   │   ├── research_guardrail.py          # NEW — scope + safety LLM judge (FR-021..023)
│   │   ├── research_policy.py             # NEW — source allow/block filter + 3-5 clamp
│   │   ├── session_store.py               # CHANGED — add ChatTurn.sources (optional)
│   │   └── pg_session_store.py            # CHANGED — tolerant deserialize of new field
│   ├── services/
│   │   └── baby_age.py                    # NEW — pure age-string helper (FR-007, FR-008)
│   └── config.py                          # CHANGED — research-specific settings
└── tests/
    ├── contract/test_research_api.py      # NEW — response shape + refused-turn shape
    ├── unit/test_baby_age.py              # NEW — boundary table for age units
    ├── unit/test_research_policy.py       # NEW — allow/block list, source clamp
    ├── unit/test_research_guardrail.py    # NEW — mocked judge, 3 verdicts
    ├── integration/test_research_e2e.py   # NEW — mocked WebSearchTool, full flow
    ├── benchmarks/test_research_hotpath.py# NEW — micro-benchmark for hot helpers
    └── evals/test_research_eval.py        # NEW — opt-in live eval (SC-002..009)

frontend/
└── (no changes required — FR-018 preserves response schema; existing ChatPanel
   already renders agent_message + sources list)
```

**Structure Decision**: Web application (existing `backend/` + `frontend/`); changes are entirely backend-local. The new modules live alongside the existing diary agent stack so MAF wiring, observability middleware, auth dependencies, and the session store are reused without abstraction churn (Principle IV).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified.**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(none)_ | _(none)_ |

All gates pass with the chosen approach. Notably:

- The single new third-party dependency (`azure-ai-projects`) is a Microsoft package and the canonical companion to the MAF Foundry client; it does not introduce a non-Microsoft agent framework (Principle V).
- No additional persistent storage is introduced (Principle IV); the new `ChatTurn.sources` field is additive and backward-compatible with the existing JSONB layout (see `contracts/session-store.md`).
- The new helper modules each have a single responsibility and explicit input/output types (Principle IV).
