---
description: "Task list for feature 003-chat-session-store"
---

# Tasks: Backend-Side Chat Session Store

**Input**: Design documents in `specs/003-chat-session-store/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [quickstart.md](./quickstart.md)

**Tests**: INCLUDED — Constitution Principle II (NON-NEGOTIABLE) mandates test-first for new behavior, ≥ 80% line / ≥ 70% branch coverage, and contract tests for every interface surface. Tests for each story MUST be authored and demonstrated failing before the implementing code is merged.

**Organization**: Tasks are grouped by user story (US1, US2, US3). Phase 1 (Setup) and Phase 2 (Foundational) MUST complete before any story phase begins.

## Format: `[ID] [P?] [Story?] Description`

- **[P]** — parallelizable with sibling [P] tasks (different files, no incomplete-task dependencies)
- **[US1] / [US2] / [US3]** — story label (story-phase tasks only)

## Path Conventions

Web-app layout per [plan.md](./plan.md#source-code-repository-root): all backend paths are under `backend/`. No frontend changes in this feature.

---

## Phase 1 — Setup (Shared Infrastructure)

**Purpose**: Wire the new in-memory session store as a process-lifetime singleton and add the five new env settings.

- [X] T001 [P] Add five new fields to [backend/src/momdiary/config.py](../../backend/src/momdiary/config.py): `momdiary_session_ttl_seconds: int = 86400`, `momdiary_session_max_turns: int = 50`, `momdiary_session_max_sessions: int = 100`, `momdiary_session_message_max_bytes: int = 4096`, `momdiary_session_prompt_token_budget: int = 12000`. Include docstrings citing FR-009, FR-010, FR-011, FR-012, FR-013.
- [X] T002 [P] Add the five settings (with default values commented) to [backend/.env.example](../../backend/.env.example). Create the file from any existing `.env.example`; if none exists, add only the new keys with comments.
- [X] T003 ~~Update backend/README.md~~ SKIPPED — backend/README.md does not exist; quickstart.md is the canonical reference. Update (./quickstart.md) reference link in [backend/README.md](../../backend/README.md) under a new "Chat Session Store" heading pointing at [quickstart.md](./quickstart.md) and [openapi.yaml](./contracts/openapi.yaml).

**Checkpoint**: Settings load successfully via `get_settings()`; no behavior change yet.

---

## Phase 2 — Foundational (Blocking Prerequisites)

**Purpose**: Land the `SessionStore` protocol + `InMemorySessionStore` + `ChatTurn` + `ChatSession` dataclasses with full unit coverage. Every user story imports from this module.

**⚠️ CRITICAL**: No user-story phase can start until T013 passes green.

### Tests (RED) — write first, must fail before T011 lands

- [X] T004 [P] Create [backend/tests/unit/test_session_store_basics.py](../../backend/tests/unit/test_session_store_basics.py): assert `get_or_create(None)` returns a fresh UUID-v4 `ChatSession`; `get_or_create(id)` for a known id returns the same object; `get_or_create(unknown_id)` returns a freshly issued id (FR-007).
- [X] T005 [P] Create [backend/tests/unit/test_session_store_fifo.py](../../backend/tests/unit/test_session_store_fifo.py): append 2 × `max_turns + 5` turns and assert `deque` length == `max_turns * 2` and oldest items dropped (FR-009).
- [X] T006 [P] Create [backend/tests/unit/test_session_store_ttl.py](../../backend/tests/unit/test_session_store_ttl.py): use `freezegun` to advance past `TTL`; assert `get_or_create(expired_id)` returns a new id and emits `session.expired` log event (FR-010).
- [X] T007 [P] Create [backend/tests/unit/test_session_store_lru.py](../../backend/tests/unit/test_session_store_lru.py): fill to `max_sessions`; create one more; assert least-recently-active session removed and `session.evicted` log fires (FR-011).
- [X] T008 [P] Create [backend/tests/unit/test_session_store_size_cap.py](../../backend/tests/unit/test_session_store_size_cap.py): append a `ChatTurn` whose `text` is `max_bytes + 1` bytes; assert `SessionMessageTooLargeError` raised (FR-012).
- [X] T009 [P] Create [backend/tests/unit/test_session_store_locking.py](../../backend/tests/unit/test_session_store_locking.py): two concurrent `asyncio.create_task` appenders against the same session must serialize — verify by recording per-append start/end timestamps with no overlap (FR-014).
- [X] T010 [P] Create [backend/tests/unit/test_session_store_recent_view.py](../../backend/tests/unit/test_session_store_recent_view.py): build a session with 10 turns whose token-estimates exceed the budget; assert `recent_view` returns the longest *suffix* whose estimate sum ≤ budget; assert empty session → `[]` (FR-013).

### Implementation (GREEN)

- [X] T011 Create [backend/src/momdiary/agents/session_store.py](../../backend/src/momdiary/agents/session_store.py) implementing:
  - `class SessionMessageTooLargeError(ValueError)`
  - `@dataclass(slots=True) class ChatTurn` per [data-model.md §1](./data-model.md#entity-chatturn)
  - `class ChatSession` carrying `id`, `created_at`, `last_activity_at`, `turns: deque[ChatTurn]` (maxlen = `max_turns * 2`), and `lock: asyncio.Lock`
  - `class SessionStore(Protocol)` with `get_or_create`, `append`, `recent_view`, `evict_expired`
  - `class InMemorySessionStore` implementing the protocol with a single `asyncio.Lock` for the dict, lazy TTL eviction inside `get_or_create`, LRU eviction when the dict is full, structured `structlog` logs (`session.created`, `session.appended`, `session.evicted`, `session.expired`) tagged with `correlation_id` and `session_id[:8]`
  - Token estimator: module-level `_estimate_tokens(text: str) -> int` returning `len(text) // 4 + 4`
- [X] T012 Wire `get_session_store()` dependency in [backend/src/momdiary/api/dependencies.py](../../backend/src/momdiary/api/dependencies.py) returning a module-level singleton `InMemorySessionStore` instantiated lazily from `get_settings()`. Also instantiate it in [backend/src/momdiary/main.py](../../backend/src/momdiary/main.py)'s `_lifespan` so a single store survives across requests.
- [X] T013 Run `pytest backend/tests/unit/test_session_store_*.py -x -q` and confirm all RED tests now pass.

**Checkpoint**: SessionStore is testable, bounded, and locked. Ready for user-story phases.

---

## Phase 3 — User Story 1: Agent Resolves References to Prior Turns (Priority: P1) 🎯 MVP

**Goal**: A correction like "actually make it 90" after "120 ml breast milk just now" produces an `updated` outcome on the same entry id — verifying FR-004 (history reaches the agent) end-to-end.

**Independent Test**: Drive the two turns against a clean dev backend through the same `X-Session-ID`; assert turn 2's response has `outcome=updated` and the same `entry_id` from turn 1. Repeating turn 2 *without* the session id produces `clarification_requested`.

### Tests (RED) — write first

- [X] T014 [P] [US1] Create [backend/tests/unit/test_render_history.py](../../backend/tests/unit/test_render_history.py) covering `_render_history`:
  - empty list → `""`
  - caregiver-only turn → `"Caregiver: <text>\n"`
  - assistant turn with `outcome="created"` and `entry_id=42`, `entry_type="feed"` → trailing `(created feed#42)` parenthetical
  - assistant turn with `outcome="clarification_requested"` → no parenthetical
  - ordering is oldest→newest
- [X] T015 [P] [US1] Create [backend/tests/unit/test_maf_runner_prompt.py](../../backend/tests/unit/test_maf_runner_prompt.py): stub `bundle.agent.run` to record the `full_message` arg; assert that when `history=[turn1, turn2]` is passed, the captured `full_message` contains `"Conversation so far:\n"` followed by the exact `_render_history` output, then `"Caregiver said: <message>"`. Also assert that `history=[]` elides the `"Conversation so far:"` block entirely (FR-015 first-turn byte-compat).
- [X] T016 [US1] Create [backend/tests/integration/test_session_continuity.py](../../backend/tests/integration/test_session_continuity.py) using the existing scripted-agent harness: turn 1 = "120 ml breast milk just now" → expect `created` with entry id `E1`; turn 2 = "actually make it 90" sent with the same `X-Session-ID` → expect `outcome="updated"` and `entry.id == E1`. Use the existing scripted agent runner, but extend it to consult the supplied `history` when deciding `updated` vs `created` (the scripted runner needs only a tiny "if history mentions a feed and current message says 'make it N', emit update_feed(N)" rule for this test).
- [X] T017 [US1] Add a negative-path test in the same file: turn 2 sent with NO `X-Session-ID` → response sets a NEW `session_id` AND `outcome="clarification_requested"`.

### Implementation (GREEN)

- [X] T018 [US1] Add `_render_history(history: list[ChatTurn]) -> str` to [backend/src/momdiary/agents/maf_runner.py](../../backend/src/momdiary/agents/maf_runner.py) per [plan.md §"Agent Invocation Flow"](./plan.md#agent-invocation-flow-history-inclusion--fr-004).
- [X] T019 [US1] Modify `MAFAgentRunner.run` in the same file: add required keyword-only `history: list[ChatTurn]` parameter (assert `history is not None`); compute `history_block = _render_history(history)`; only when `history_block` is non-empty, splice `f"\n\nConversation so far:\n{history_block}"` between `context` and `Caregiver said: {message}` (matches T015 expectations).
- [X] T020 [US1] Update `AgentRunner` Protocol in [backend/src/momdiary/agents/dispatcher.py](../../backend/src/momdiary/agents/dispatcher.py) to include the new `history` kwarg, and thread it through `AgentDispatcher.dispatch(... , history: list[ChatTurn])`.
- [X] T021 [US1] Update [backend/src/momdiary/api/entries.py](../../backend/src/momdiary/api/entries.py) POST handler to (a) read `X-Session-ID` header via FastAPI `Header(None)`, (b) `session = await store.get_or_create(header_value)`, (c) acquire `session.lock` around the whole flow, (d) `history = await store.recent_view(session, settings.momdiary_session_prompt_token_budget)`, (e) call `dispatcher.dispatch(..., history=history)`, (f) `append` caregiver-turn (pre) and assistant-turn (post) — wrap each append in `try/except` with `WARN` log (FR-016), (g) set `X-Session-ID` response header and inject `session_id` into the response body (see T024).
- [X] T022 [US1] Mirror the same wiring on the PUT handler in `entries.py` so both write entry-points share session semantics.
- [X] T023 [US1] Extend [backend/src/momdiary/api/dependencies.py](../../backend/src/momdiary/api/dependencies.py) `build_response_envelope` to take an extra `session_id: str` arg and include it in every body branch (write, clarification, error). Update both `entries.py` call sites accordingly.
- [X] T024 [US1] Add required `session_id: str` field to `AgentWriteResponse`, `AgentClarificationResponse`, and `ErrorResponse` in [backend/src/momdiary/models/schemas.py](../../backend/src/momdiary/models/schemas.py).
- [X] T025 [US1] Update the existing scripted agent runner used by integration tests (likely in `backend/tests/integration/conftest.py` or `backend/tests/conftest.py`) to accept and consult the new `history` kwarg so T016/T017 turn green.

**Checkpoint**: US1 end-to-end test green. Multi-turn correction works.

---

## Phase 4 — User Story 2: Session Isolation Across Clients (Priority: P1)

**Goal**: Two sessions never see each other's turns; unknown ids are treated as fresh per FR-007.

**Independent Test**: Two `httpx.AsyncClient`s, each logs a feed and then sends "delete that"; neither delete affects the other client's feed; an entirely missing header issues a fresh id per response.

### Tests (RED)

- [X] T026 [P] [US2] Create [backend/tests/integration/test_session_isolation.py](../../backend/tests/integration/test_session_isolation.py):
  - client A: turn 1 = "120 ml breast milk now" → capture `sid_A`, `feed_id_A`
  - client B: turn 1 = "150 ml formula now" → capture `sid_B`, `feed_id_B`
  - assert `sid_A != sid_B`
  - client B: turn 2 = "delete that" with `X-Session-ID: sid_B` → `outcome=deleted`, `entry.id == feed_id_B`
  - independently re-fetch feeds list; assert `feed_id_A` still exists
- [X] T027 [P] [US2] Add a contract test [backend/tests/contract/test_entries_session.py](../../backend/tests/contract/test_entries_session.py) asserting every POST/PUT response on `/v1/entries` (across all five outcomes: created/updated/deleted/clarification/error) sets the `X-Session-ID` response header AND a matching `session_id` field in the body, and that the values are equal UUID-v4 strings. Includes the "unknown id treated as fresh" case.

### Implementation (GREEN)

- [X] T028 [US2] No new implementation files — T021 + T024 + the in-memory dict's natural keying by id already provide isolation. T026 and T027 must pass against the code from Phase 3. If they fail, fix the regression in [entries.py](../../backend/src/momdiary/api/entries.py) or [session_store.py](../../backend/src/momdiary/agents/session_store.py) (not by adding new modules).

**Checkpoint**: US2 tests green alongside US1.

---

## Phase 5 — User Story 3: Bounded Retention (Priority: P2)

**Goal**: Verify end-to-end that all three caps and TTL hold under realistic HTTP-driven workloads, not just direct store calls. (Unit-level caps were already proven in Phase 2.)

**Independent Test**: A scripted loop drives 60 turns through one session and asserts the store's `len(turns)` plateaus at `max_turns * 2`; another loop creates 110 sessions and asserts dict size plateaus at `max_sessions`; a `freezegun`-driven test advances past TTL and asserts the next request issues a fresh id.

### Tests (RED)

- [X] T029 [P] [US3] Create [backend/tests/integration/test_session_retention.py](../../backend/tests/integration/test_session_retention.py) with three test functions:
  - `test_fifo_cap_via_http`: drive `max_turns + 5` turns through `httpx.AsyncClient` against one session; via dependency override, peek at the in-memory store and assert `len(session.turns) == max_turns * 2`.
  - `test_lru_eviction_via_http`: create `max_sessions + 10` distinct sessions; assert resident sessions == `max_sessions` and the earliest-created ones are gone.
  - `test_ttl_via_freezegun`: capture `sid` from one POST; `freezegun` advances `now` past TTL; next POST with the same `X-Session-ID` returns a *different* `session_id` and the response surfaces no leakage from the expired session (a "delete that" follow-up becomes `clarification_requested`).
- [X] T030 [P] [US3] Create [backend/tests/integration/test_session_failure_isolation.py](../../backend/tests/integration/test_session_failure_isolation.py): monkeypatch `InMemorySessionStore.append` to raise; assert the HTTP response still has the normal write outcome AND a `session.append_failed` log event fired (FR-016).

### Implementation (GREEN)

- [X] T031 [US3] No new code expected — the caps are implemented in T011. If T029/T030 fail, fix in [session_store.py](../../backend/src/momdiary/agents/session_store.py) and/or [entries.py](../../backend/src/momdiary/api/entries.py).

**Checkpoint**: All three user stories green.

---

## Phase 6 — Polish & Cross-Cutting Concerns

- [X] T032 [P] Add benchmark [backend/tests/benchmarks/test_session_store_bench.py](../../backend/tests/benchmarks/test_session_store_bench.py) using `pytest-benchmark`: build a 100-turn session and measure `recent_view + append × 2`; assert median runtime < 5 ms locally (informational floor; the SC-006 50 ms p95 budget is for the full HTTP path).
- [X] T033 [P] Update [backend/src/momdiary/agents/README.md](../../backend/src/momdiary/agents/README.md) with a "Session Store" section linking to [plan.md](./plan.md), [data-model.md](./data-model.md), and the four log event names.
- [X] T034 [P] Run `ruff check backend/` and `ruff format --check backend/`; fix any new findings.
- [X] T035 Run the full backend test suite: `cd backend; pytest -q`. Confirm ≥ 80% line / ≥ 70% branch coverage on the new module via `pytest --cov=momdiary.agents.session_store --cov=momdiary.agents.maf_runner --cov-branch --cov-report=term-missing`. Add targeted tests if any new branch is uncovered.
- [ ] T036 Walk through [quickstart.md](./quickstart.md) manually against a live `uvicorn` instance; confirm turn 1, turn 2, turn 3 behave as documented. Update quickstart if any detail drifted. (DEFERRED: requires live Azure model — exercise locally before merge.)
- [X] T037 Update the top-level [.github/copilot-instructions.md](../../.github/copilot-instructions.md) "Recent Changes" entry for 003 to mention "in-memory `SessionStore`, history threaded through `MAFAgentRunner.run(..., history=...)`, `X-Session-ID` header on `/v1/entries`".

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; T001 / T002 / T003 can run in parallel.
- **Phase 2 (Foundational)**: depends on Phase 1; **T013 is the gate**.
- **Phase 3 (US1)**: depends on T013.
- **Phase 4 (US2)**: depends on Phase 3 (uses the entries-handler wiring landed there).
- **Phase 5 (US3)**: depends on Phase 3 (uses HTTP path) + on Phase 2 caps.
- **Phase 6 (Polish)**: depends on Phases 3–5 green.

### Critical Path (single-developer fastest path to MVP)

```
T001 → T011 → T013 → T018 → T019 → T020 → T021 → T024 → T023 → T025 → T016 (US1 green)
```

US1 alone is a viable MVP (it delivers FR-004 — the headline user value).

### Within Each User Story

- All `[P]` test tasks may run in parallel.
- All test tasks (T004–T010, T014, T015, T016, T017, T026, T027, T029, T030) MUST be authored and demonstrated **red** before their corresponding implementation tasks land.
- Models / dataclasses (T011) before services (T012) before endpoint wiring (T021/T022).

### Parallel Opportunities

- **Phase 1**: `[T001, T002, T003]` parallel.
- **Phase 2 tests**: `[T004, T005, T006, T007, T008, T009, T010]` parallel — distinct test files.
- **Phase 3 tests**: `[T014, T015]` parallel; T016 depends on T025-style scripted-runner update, T017 piggybacks on T016's file.
- **Phase 4 tests**: `[T026, T027]` parallel.
- **Phase 5 tests**: `[T029, T030]` parallel.
- **Phase 6**: `[T032, T033, T034]` parallel; T035–T037 sequential.

---

## Parallel Example — Phase 2 RED tests

```powershell
# From repo root, with backend deps installed:
cd backend
pytest -x -q `
  tests/unit/test_session_store_basics.py `
  tests/unit/test_session_store_fifo.py `
  tests/unit/test_session_store_ttl.py `
  tests/unit/test_session_store_lru.py `
  tests/unit/test_session_store_size_cap.py `
  tests/unit/test_session_store_locking.py `
  tests/unit/test_session_store_recent_view.py
# Expect: 7 files, all RED (ModuleNotFoundError until T011 lands).
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (T001–T003).
2. Phase 2 (T004–T013) — landed and green.
3. Phase 3 (T014–T025) — US1 end-to-end.

Ship at this point — caregivers get the headline value (multi-turn corrections work). US2 isolation is *already* true at this point (it's a property of the store, not of additional code), but T026 / T027 *prove* it.

### Incremental Delivery After MVP

- Phase 4 (T026–T028): two contract / integration tests prove isolation; no new prod code.
- Phase 5 (T029–T031): retention validated end-to-end; no new prod code (caps were already implemented).
- Phase 6 (T032–T037): benchmark, docs, lint, full coverage, quickstart walkthrough.

### Independent Test Criteria — Summary

| Story | Independent verification |
|---|---|
| US1 | `test_session_continuity.py` (T016) — turn 2 with shared `X-Session-ID` produces `updated` on turn 1's entry id |
| US2 | `test_session_isolation.py` (T026) + `test_entries_session.py` (T027) — two sessions don't bleed; all responses carry matching header+body session id |
| US3 | `test_session_retention.py` (T029) + `test_session_failure_isolation.py` (T030) — caps + TTL + failure isolation observable via HTTP |

---

## Task Count Summary

- **Phase 1 (Setup)**: 3 tasks
- **Phase 2 (Foundational)**: 10 tasks (7 RED tests + 3 implementation)
- **Phase 3 (US1 / P1 / MVP)**: 12 tasks (4 tests + 8 implementation)
- **Phase 4 (US2 / P1)**: 3 tasks (2 tests + 1 verification)
- **Phase 5 (US3 / P2)**: 3 tasks (2 tests + 1 verification)
- **Phase 6 (Polish)**: 6 tasks
- **Total**: **37 tasks** (15 test-first tasks, 22 implementation/polish tasks)
