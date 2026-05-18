# Implementation Plan: Backend-Side Chat Session Store

**Branch**: `003-chat-session-store` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-chat-session-store/spec.md`

## Summary

Add an in-memory, server-side chat-session store to the existing FastAPI backend so the
Microsoft Agent Framework (MAF) agent receives prior caregiver/assistant turns on every
chat invocation. The store lives in the `uvicorn` process (a thread-safe dict guarded by
`asyncio.Lock`s) and enforces bounded retention (per-session FIFO turn cap, per-session
idle TTL, global LRU eviction), token-aware trimming on read, per-session serialization
of concurrent writes, and an unguessable UUID-v4 session identifier issued by the server
and echoed by the client via the `X-Session-ID` header / `session_id` response field.
No schema migration, no new external service, no auth changes.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged)
**Primary Dependencies**: FastAPI, `agent-framework==1.0.0rc6`, `agent-framework-azure-ai==1.0.0rc6`, `azure-identity`, SQLAlchemy 2.x async, `pydantic` v2, `structlog`
**Storage**: In-memory (Python dict in the FastAPI process). No SQLite/Alembic changes. The existing `momdiary.db` file is untouched.
**Testing**: `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `freezegun` for TTL/LRU tests
**Target Platform**: Single-process `uvicorn` worker on Linux/Windows dev hosts
**Project Type**: Web service (backend) — the `frontend/` directory exists but its session-id wiring is out of scope for this feature
**Performance Goals**: p95 added latency ≤ 50 ms over the no-store baseline for a 100-turn session (SC-006); session lookup ≤ 1 ms; FIFO eviction ≤ 1 ms
**Constraints**: Bounded memory per Constitution III — every cap (max-sessions, max-turns, max-bytes, token budget, TTL) is documented and configurable via env. Session IDs must be unguessable (UUID v4).
**Scale/Scope**: Single-tenant dev/demo workload — ≤ 100 resident sessions, ≤ 50 turn-pairs per session, ≤ 4 KB per caregiver message, ≤ 12 K prompt tokens delivered to the model.

## Constitution Check

*GATE: Re-evaluated after Phase 1 design — see "Post-Design Re-check" below.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Code Quality | Lint/format pass; new module ≤ 10 cyclomatic per fn; docstrings on `SessionStore` public methods | **PASS** by design — module is small and pure-logic. |
| II — Testing (NON-NEGOTIABLE) | Tests authored before code (red→green); ≥ 80% line / ≥ 70% branch on new code; unit + integration + contract tests | **PASS** by design — tasks.md will enumerate failing tests first. |
| III — Performance | Bounded memory documented; benchmark for hot path (session lookup + append); regression budget | **PASS** by design — caps explicit; benchmark task included. |
| IV — Modular Architecture | New session store module isolated; pluggable behind a `SessionStore` protocol so a future SQLite/Redis backend can drop in; no cyclic imports | **PASS** by design — `agents/session_store.py` is a leaf module; only `agents/maf_runner.py` and `api/entries.py` import it. |
| V — Microsoft Agent Framework First (NON-NEGOTIABLE) | All agent functionality stays on MAF; only adapter is changed (history is concatenated into the prompt) | **PASS** — MAF Agent contract is unchanged; history is supplied via the existing `_format_context` channel as additional prompt content. No new agent framework introduced. |

**Initial check**: PASS — no violations, Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-chat-session-store/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entities + invariants)
├── quickstart.md        # Phase 1 output (curl walkthrough)
├── contracts/
│   └── openapi.yaml     # Phase 1 output (delta from feature 002's openapi)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/momdiary/
│   ├── agents/
│   │   ├── session_store.py        # NEW — ChatTurn, ChatSession, SessionStore
│   │   ├── maf_runner.py           # MODIFIED — accept session_id, prepend history
│   │   ├── dispatcher.py           # MODIFIED — thread session_id through DispatchResult
│   │   └── diary_agent.py          # UNCHANGED (Principle V)
│   ├── api/
│   │   ├── entries.py              # MODIFIED — read/write X-Session-ID, return session_id
│   │   └── dependencies.py         # MODIFIED — add get_session_store() dependency
│   ├── models/
│   │   └── schemas.py              # MODIFIED — add session_id to write/clarify/error envelopes
│   ├── config.py                   # MODIFIED — 5 new settings (TTL, caps, token budget)
│   └── main.py                     # MODIFIED — instantiate SessionStore in lifespan
└── tests/
    ├── unit/
    │   └── test_session_store.py        # NEW — append, FIFO, TTL, LRU, locking
    ├── integration/
    │   ├── test_session_continuity.py   # NEW — US1 multi-turn correction
    │   ├── test_session_isolation.py    # NEW — US2 two sessions don't bleed
    │   └── test_session_retention.py    # NEW — US3 caps + TTL + LRU
    ├── contract/
    │   └── test_entries_session.py      # NEW — X-Session-ID / session_id contract
    └── benchmarks/
        └── test_session_store_bench.py  # NEW — append+recent_view p95

frontend/                            # UNTOUCHED in this feature
```

**Structure Decision**: Reuse the existing single-backend layout. The session store is a new
leaf module under `agents/` (it serves the agent), and all wiring touches only the
agent runner, dispatcher, request/response schemas, dependencies, and config. No new
top-level packages.

## Phase 0 — Research

See [research.md](./research.md). All NEEDS CLARIFICATION resolved in the spec via documented Assumptions; this phase records the technical decisions.

## Phase 1 — Design & Contracts

See:
- [data-model.md](./data-model.md) — `ChatTurn`, `ChatSession`, `SessionStore`, invariants
- [contracts/openapi.yaml](./contracts/openapi.yaml) — additive changes to `/v1/entries` (header + body field)
- [quickstart.md](./quickstart.md) — three-turn curl walkthrough end-to-end

### Agent Invocation Flow (history inclusion — FR-004)

Every chat invocation on `/v1/entries` MUST execute exactly the following sequence so the
MAF agent receives prior conversation turns. This is the canonical sequence that tasks
and tests are expected to enforce:

```text
POST /v1/entries
   │  X-Session-ID: <maybe>            body: {"message": "...", ...}
   ▼
api/entries.py
   │  cid = correlation_id_from_header_or_body()
   │  store = Depends(get_session_store())
   │  session = await store.get_or_create(request.headers.get("X-Session-ID"))
   ▼
async with session.lock:                          # FR-014 — per-session serialization
   │
   │  history = await store.recent_view(          # FR-013 — token-aware trim
   │      session,
   │      token_budget=settings.momdiary_session_prompt_token_budget,
   │  )
   │
   │  ──► dispatcher.dispatch(message, correlation_id=cid, history=history, ...)
   │         │
   │         └─► MAFAgentRunner.run(message, ..., history=history)
   │                │
   │                │  context = await _format_context(session_db, entry_id, entry_type)
   │                │  history_block = _render_history(history)           # NEW
   │                │  full_message = (
   │                │      f"{context}\n\n"
   │                │      f"Conversation so far:\n{history_block}\n\n"   # FR-004
   │                │      f"Caregiver said: {message}"
   │                │  )
   │                │  response = await bundle.agent.run(full_message)
   │                ▼
   │            AgentRunResult
   │
   │  caregiver_turn  = ChatTurn(role="caregiver", text=message, correlation_id=cid, ...)
   │  assistant_turn  = ChatTurn(
   │      role="assistant",
   │      text=result.agent_message or "",
   │      outcome=result.outcome,
   │      entry_type=result.entry_type,
   │      entry_id=result.entry_id,
   │      correlation_id=cid,
   │  )
   │  try:
   │      await store.append(session, caregiver_turn)                     # FR-005
   │      await store.append(session, assistant_turn)                     # FR-005
   │  except Exception:
   │      log.warning("session.append_failed", correlation_id=cid)        # FR-016
   │
   ▼
response.headers["X-Session-ID"] = session.id
body["session_id"] = session.id                                            # FR-003
```

**`_render_history(history)` shape** (NEW helper inside `agents/maf_runner.py`):

```text
Caregiver: 120 ml breast milk just now
Assistant: Logged 120 ml breast milk at 14:32. (created feed#42)
Caregiver: actually make it 90
Assistant: Updated feed#42 to 90 ml. (updated feed#42)
```

- Plain text, role-prefixed, oldest→newest, one line per turn.
- For assistant turns whose `outcome` was a write, the trailing parenthetical
  `(<outcome> <entry_type>#<entry_id>)` is appended so the model can resolve references
  like "the feed I just logged" without re-reading the database.
- Caregiver turns echo `text` verbatim (already capped at 4 KB by `append`).
- An empty `history` (first turn in a fresh session) elides the `"Conversation so far:"`
  block entirely so the prompt remains identical to today's single-turn shape — preserving
  FR-015 byte-for-byte compatibility on the first turn of every new session.

**Why this shape**:

- The MAF `Agent.run(full_message)` contract is unchanged (Principle V) — history is just
  more prompt text, supplied through the *same* channel as the existing `_format_context`
  preamble.
- Concatenated prose tracks the existing `gpt-4.1` deployment's behavior better than a
  structured JSON history for this model size; if a future deployment supports the MAF
  `ChatHistory` primitive natively, only `_render_history` needs to change (Principle IV).
- The per-session lock around the *whole* `recent_view → agent.run → append × 2` cycle
  guarantees that two concurrent turns on the same session id never see an
  interleaved-partial history (FR-014); the agent never observes a caregiver turn whose
  assistant half is missing.

**Tasks must enforce** (anticipated for /speckit.tasks):

1. A failing integration test (`test_session_continuity.py`) that drives turn 1 = "120 ml
   breast milk just now", turn 2 = "actually make it 90", and asserts turn 2 produces
   `outcome=updated` on the same `entry_id` (US1 acceptance scenario 1).
2. A failing unit test (`test_maf_runner_prompt.py`) that captures the
   `full_message` actually passed to `bundle.agent.run(...)` (via a stub) and asserts the
   `"Conversation so far:"` block contains exactly the rendered prior turns in
   oldest→newest order.
3. A failing unit test for `_render_history` covering: empty list → empty render;
   write-outcome turn → trailing parenthetical; clarification turn → no parenthetical.
4. A failing contract test asserting every `/v1/entries` response sets the
   `X-Session-ID` header and the body `session_id` field to the same UUID.

**Agent context update**: Append the new technologies/decisions to `.github/copilot-instructions.md` via `.specify/scripts/powershell/update-agent-context.ps1 -AgentType copilot` after generating this plan.

### Post-Design Re-check (Constitution)

Re-checked after writing the artifacts:

- **I** PASS — `SessionStore` exposes 4 public methods (`get_or_create`, `append`, `recent_view`, `evict_expired`); each is ≤ 25 lines with a docstring.
- **II** PASS — task list enumerates 14+ tests (5 unit, 3 integration, 1 contract, 1 benchmark + negative-paths) authored before any implementation file.
- **III** PASS — `recent_view` is O(K) where K is the configured turn cap; benchmark target documented (≤ 50 ms p95 added latency on a 100-turn session).
- **IV** PASS — `SessionStore` is a protocol; the in-memory backend (`InMemorySessionStore`) is one implementation; a future SQLite-backed backend drops in without touching the runner.
- **V** PASS — MAF integration remains a single `Agent(...).run(full_message)` call; history is concatenated into `full_message` exactly as today's `_format_context` is.

No new violations.

## Complexity Tracking

> **Empty** — Constitution Check passes with no exceptions.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(n/a)_ | _(n/a)_ |
