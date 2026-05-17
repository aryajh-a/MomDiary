---
description: "Task list for feature 001-baby-tracker-backend"
---

# Tasks: Baby Tracker Agentic Backend

**Input**: Design documents from `specs/001-baby-tracker-backend/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml), [contracts/agent-tools.md](contracts/agent-tools.md)

**Tests**: Tests are REQUIRED for this feature. Principle II of the MomDiary Constitution is NON-NEGOTIABLE (test-first, ≥ 80% line / ≥ 70% branch coverage, deterministic agent tests, contract tests on every tool and on the OpenAPI surface). Test tasks below are mandatory and MUST be authored failing before their paired implementation tasks.

**Organization**: Tasks are grouped by user story (US1, US2, US3 from `spec.md`). Each phase is an independently testable increment.

## Format: `[ID] [P?] [Story?] Description`

- **[P]** — May run in parallel (different files, no dependency on incomplete tasks).
- **[Story]** — User story label (US1, US2, US3); omitted for Setup, Foundational, Polish.
- File paths shown are workspace-relative.

## Path Conventions

Single web-service backend layout (from `plan.md` Structure Decision):

- Source: `backend/src/momdiary/...`
- Migrations: `backend/alembic/...`
- Tests: `backend/tests/{contract,integration,unit,benchmarks}/...`
- Docs: `backend/docs/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, tooling, and constitution-mandated baselines.

- [X] T001 Create backend project layout per `plan.md` (folders `backend/src/momdiary/{api,agents/tools,services,models,db/repositories,observability}`, `backend/alembic/`, `backend/tests/{contract,integration,unit,benchmarks}`, `backend/docs/`).
- [X] T002 Initialize Python 3.12 project with `uv` in `backend/pyproject.toml` declaring dependencies: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `sqlalchemy[asyncio]>=2`, `aiosqlite`, `alembic`, `azure-identity`, `agent-framework`, `agent-framework-azure-ai`, `structlog`, plus dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-benchmark`, `httpx`, `ruff`, `mypy`, `types-PyYAML`. Allow prereleases for `agent-framework*` only.
- [X] T003 [P] Configure `ruff` (lint + format) and `mypy --strict` for `backend/src/momdiary/` in `backend/pyproject.toml`; add `pre-commit` config in `backend/.pre-commit-config.yaml`.
- [X] T004 [P] Configure `pytest` in `backend/pyproject.toml` `[tool.pytest.ini_options]` with `pytest-asyncio` mode, `pytest-cov` thresholds (≥ 80% line, ≥ 70% branch, fail-under), and `filterwarnings = ["ignore::DeprecationWarning:agent_framework.*", "ignore::PendingDeprecationWarning:agent_framework.*"]`.
- [X] T005 [P] Create `backend/docs/AGENT_FRAMEWORK_WARNINGS.md` documenting the (initially empty) list of scoped MAF warning suppressions and the recorded resolved prerelease versions placeholder (Principle V).
- [X] T006 [P] Create `backend/.env.example` listing `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT=gpt-4.1`, `AZURE_OPENAI_API_VERSION`, `MOMDIARY_DB_URL`, `MOMDIARY_DEFAULT_TIMEZONE`; update repo `.gitignore` to exclude `*.db`, `.env`, `.venv/`, `backend/.coverage*`.

**Checkpoint**: Tooling and project skeleton in place; CI gates (ruff, mypy, pytest) wired but no source yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that EVERY user story depends on. No user-story work may begin until this phase is green.

- [X] T007 Implement Pydantic `Settings` (env-var driven) in `backend/src/momdiary/config.py` exposing `azure_openai_*`, `db_url`, `default_timezone`, `app_env`.
- [X] T008 [P] Implement structured JSON logging + MAF-scoped warning filter (`warnings.filterwarnings("ignore", module=r"agent_framework.*")`) in `backend/src/momdiary/observability/logging.py`.
- [X] T009 [P] Implement correlation-id ASGI middleware in `backend/src/momdiary/observability/middleware.py` (generates UUID per request, exposes via `contextvars` for the dispatcher).
- [X] T010 Implement async SQLAlchemy engine + session factory + `get_session` FastAPI dependency in `backend/src/momdiary/db/engine.py`.
- [X] T011 Define all SQLAlchemy ORM models in `backend/src/momdiary/models/orm.py` per `data-model.md`: `Feed`, `Sleep`, `Poop`, `Appointment`, `AppointmentNote`, `AgentInteraction`, `Settings` (singleton). Include CHECK constraints, nullable `caregiver_id`, nullable `deleted_at`, and the prescribed indexes.
- [X] T012 Initialize Alembic in `backend/alembic/` (`env.py` wired to async engine) and author migration `backend/alembic/versions/0001_initial.py` creating all tables + indexes + the seeded singleton `settings` row from `MOMDIARY_DEFAULT_TIMEZONE`.
- [X] T013 [P] Define Pydantic request/response schemas in `backend/src/momdiary/models/schemas.py` matching `contracts/openapi.yaml`: `AgentWriteRequest`, `AgentWriteResponse`, `AgentClarificationResponse`, `ErrorResponse`, `FeedEntry`, `SleepEntry`, `PoopEntry`, `AppointmentEntry`, `AppointmentNote`.
- [X] T014 [P] Implement `backend/src/momdiary/services/time_service.py`: load `default_timezone` from `settings`, expose helpers `now_in_tz()`, `parse_iso_with_offset()`, `date_window_in_tz(date)`.
- [X] T015 [P] Implement `backend/src/momdiary/services/normalization.py`: oz→ml conversion, feed-type lowercasing/alias mapping, consistency vocabulary enforcement (closest-match suggestion with explicit-confirmation flag).
- [X] T016 Implement agent-interactions repository in `backend/src/momdiary/db/repositories/agent_interactions.py` (insert-only, queries by correlation_id) — required by the dispatcher before any user-story write code lands.
- [X] T017 Implement MAF agent factory in `backend/src/momdiary/agents/diary_agent.py`: build `AzureOpenAIChatClient` using `DefaultAzureCredential` (fallback to API key), assemble a `ChatAgent` with the system prompt enforcing FR-002, FR-011, FR-017, FR-018; tools list starts empty and is extended in later phases.
- [X] T018 Implement dispatcher in `backend/src/momdiary/agents/dispatcher.py`: per-request entry point that runs the MAF agent, captures `selected_tool` / `outcome` / `latency_ms` / `model_latency_ms`, writes an `agent_interactions` row, and returns the typed response envelope (FR-013, SC-002).
- [X] T019 Implement FastAPI app factory + lifespan in `backend/src/momdiary/main.py`: register correlation-id middleware, mount empty routers for `entries`/`feeds`/`sleeps`/`poops`/`appointments`, expose `/openapi.json`.
- [X] T020 [P] Scaffold contract test `backend/tests/contract/test_openapi.py` that loads `backend/src/momdiary/main.py:create_app()` and diffs `/openapi.json` paths + schemas against `specs/001-baby-tracker-backend/contracts/openapi.yaml`. Initially the test asserts presence of all five paths.
- [X] T021 [P] Add shared pytest fixtures in `backend/tests/conftest.py`: ephemeral SQLite file per test session, `alembic upgrade head` invocation, async `httpx.AsyncClient`, and a MAF stub model client that returns scripted tool-call sequences (no live model — Principle II).

**Checkpoint**: Foundation ready. All three user stories may now proceed (in parallel if staffed).

---

## Phase 3: User Story 1 — Log a daily care event by chatting with the agent (Priority: P1) 🎯 MVP

**Goal**: A natural-language POST to `/v1/entries` results in exactly one correctly-typed entry persisted in SQLite, with a confirmation response.

**Independent Test**: Send one natural-language message per event type (feed, sleep, poop, appointment) to `POST /v1/entries`; verify each results in the right tool being chosen and the canonical record being written.

### Tests for User Story 1 (write FAILING first)

- [X] T022 [P] [US1] Contract test for each `log_*` tool's argument schema in `backend/tests/contract/test_agent_tools_log.py` (validates the four log tools' Pydantic argument models match `contracts/agent-tools.md`).
- [X] T023 [P] [US1] Integration test `backend/tests/integration/test_agent_routing.py::test_routes_each_event_type` covering the four Acceptance Scenarios of US1, using the stubbed MAF model client to script the correct tool call per message (SC-001).
- [X] T024 [P] [US1] Integration test `backend/tests/integration/test_agent_routing.py::test_missing_required_field_triggers_clarification` covering Edge Case "ambiguous or missing time" and FR-011 (SC-004 partial).

### Implementation for User Story 1

- [X] T025 [P] [US1] Implement `create` and `get_by_id` in `backend/src/momdiary/db/repositories/feeds.py` using ORM + validation (FR-003, FR-014).
- [X] T026 [P] [US1] Implement `create` and `get_by_id` in `backend/src/momdiary/db/repositories/sleeps.py` (FR-004; reject `end_at == start_at`).
- [X] T027 [P] [US1] Implement `create` and `get_by_id` in `backend/src/momdiary/db/repositories/poops.py` (FR-005, consistency enum).
- [X] T028 [P] [US1] Implement `create_appointment` (optionally with initial note in one transaction) and `get_by_id_with_notes` in `backend/src/momdiary/db/repositories/appointments.py` (FR-006).
- [X] T029 [P] [US1] Implement MAF tool `log_feed` in `backend/src/momdiary/agents/tools/feeds.py` (calls normalization service then `feeds` repo).
- [X] T030 [P] [US1] Implement MAF tool `log_sleep` in `backend/src/momdiary/agents/tools/sleeps.py`.
- [X] T031 [P] [US1] Implement MAF tool `log_poop` in `backend/src/momdiary/agents/tools/poops.py`.
- [X] T032 [P] [US1] Implement MAF tool `log_appointment` in `backend/src/momdiary/agents/tools/appointments.py` (accepts optional `note`).
- [X] T033 [US1] Register the four `log_*` tools (plus pseudo-tool `ask_for_clarification`) on the agent in `backend/src/momdiary/agents/diary_agent.py` (depends on T029–T032).
- [X] T034 [US1] Implement `POST /v1/entries` in `backend/src/momdiary/api/entries.py`: validate `AgentWriteRequest`, call dispatcher, return `AgentWriteResponse` (201) or `AgentClarificationResponse` (200) or `ErrorResponse` (400) per `contracts/openapi.yaml`. Register router in `main.py` (depends on T033).
- [X] T035 [US1] Implement clarification response path in the dispatcher: when the agent calls `ask_for_clarification`, do not persist anything; emit outcome `clarification_requested` (FR-011).

**Checkpoint**: User Story 1 is functional end-to-end and testable independently — MVP achieved.

---

## Phase 4: User Story 2 — Review everything that happened on a given day (Priority: P1)

**Goal**: Each of the four event types has a `GET /v1/<type>?date=YYYY-MM-DD` endpoint that returns all non-deleted entries of that type for that date, chronologically.

**Independent Test**: Seed entries (via US1 or fixtures), call each GET-by-date endpoint, and assert exact set + ordering for the date, including the midnight-spanning sleep case.

### Tests for User Story 2 (write FAILING first)

- [X] T036 [P] [US2] Integration test `backend/tests/integration/test_get_by_date.py::test_feeds_by_date` (Scenario US2.1).
- [X] T037 [P] [US2] Integration test `backend/tests/integration/test_get_by_date.py::test_sleeps_spanning_midnight` (FR-009, Scenario US2.2).
- [X] T038 [P] [US2] Integration test `backend/tests/integration/test_get_by_date.py::test_empty_day_returns_200_with_empty_list` (Scenario US2.3, Edge case).
- [X] T039 [P] [US2] Integration test `backend/tests/integration/test_get_by_date.py::test_appointments_with_notes` (Scenario US2.4).
- [X] T040 [P] [US2] Integration test `backend/tests/integration/test_full_day.py::test_full_day_all_entries_returned_exactly_once` covering SC-005 (≥ 20 mixed entries).
- [X] T041 [P] [US2] Benchmark `backend/tests/benchmarks/test_get_by_date.py` asserting p95 < 500 ms for a 50-entry day (SC-003, Principle III gate).

### Implementation for User Story 2

- [X] T042 [P] [US2] Add `list_by_date(date)` to `backend/src/momdiary/db/repositories/feeds.py` (filters `deleted_at IS NULL`, orders by `occurred_at`, uses `time_service.date_window_in_tz`).
- [X] T043 [P] [US2] Add `list_by_start_date(date)` to `backend/src/momdiary/db/repositories/sleeps.py` (FR-009: assignment by `start_at`'s local date).
- [X] T044 [P] [US2] Add `list_by_date(date)` to `backend/src/momdiary/db/repositories/poops.py`.
- [X] T045 [P] [US2] Add `list_by_date(date)` with eager-loaded notes to `backend/src/momdiary/db/repositories/appointments.py`.
- [X] T046 [P] [US2] Implement `GET /v1/feeds` in `backend/src/momdiary/api/feeds.py`.
- [X] T047 [P] [US2] Implement `GET /v1/sleeps` in `backend/src/momdiary/api/sleeps.py`.
- [X] T048 [P] [US2] Implement `GET /v1/poops` in `backend/src/momdiary/api/poops.py`.
- [X] T049 [P] [US2] Implement `GET /v1/appointments` in `backend/src/momdiary/api/appointments.py`.
- [X] T050 [US2] Register the four GET routers in `backend/src/momdiary/main.py` and extend `backend/tests/contract/test_openapi.py` to validate the four GET schemas against `contracts/openapi.yaml`.

**Checkpoint**: User Stories 1 + 2 deliver the read/write MVP: caregivers can log and review a day independently.

---

## Phase 5: User Story 3 — Correct or extend an existing entry via the agent (Priority: P2)

**Goal**: `PUT /v1/entries` supports the hybrid contract (explicit `entry_id` or agent-resolved), idempotent updates, soft delete, and appending notes to appointments; ambiguous targets result in clarification with no mutation.

**Independent Test**: For each event type, create then correct an entry via PUT; verify update; re-issue the same PUT and confirm idempotency; issue an ambiguous correction and confirm clarification + unchanged state; soft-delete and confirm exclusion from GETs.

### Tests for User Story 3 (write FAILING first)

- [X] T051 [P] [US3] Integration test `backend/tests/integration/test_put_update.py::test_explicit_entry_id_update` (FR-017 strict path).
- [X] T052 [P] [US3] Integration test `backend/tests/integration/test_put_update.py::test_agent_resolved_update` (FR-017 inference path, US3 Scenario 1).
- [X] T053 [P] [US3] Integration test `backend/tests/integration/test_ambiguous_inputs.py::test_ambiguous_target_returns_clarification_no_mutation` (SC-004, US3 Scenario 3, FR-017 unambiguity rule).
- [X] T054 [P] [US3] Integration test `backend/tests/integration/test_put_idempotency.py::test_repeated_put_byte_identical` (SC-006, FR-015).
- [X] T055 [P] [US3] Integration test `backend/tests/integration/test_appointment_notes.py::test_add_note_appends_not_overwrites` (US3 Scenario 2, FR-006).
- [X] T056 [P] [US3] Integration test `backend/tests/integration/test_soft_delete.py::test_soft_delete_hides_from_gets_and_resolution` (FR-018).
- [X] T057 [P] [US3] Contract test `backend/tests/contract/test_agent_tools_update_delete.py` validating argument schemas of all `update_*`, `delete_*`, and `add_appointment_note` tools against `contracts/agent-tools.md`.

### Implementation for User Story 3

- [X] T058 [P] [US3] Implement target resolver in `backend/src/momdiary/services/target_resolver.py`: given a natural-language hint + agent suggestion, return either a single `(entry_type, entry_id)` or a candidate list for clarification.
- [X] T059 [P] [US3] Add `update`, `soft_delete`, and `is_unchanged` helper to `backend/src/momdiary/db/repositories/feeds.py` (idempotency check per FR-015 / research §11).
- [X] T060 [P] [US3] Add `update`, `soft_delete`, `is_unchanged` to `backend/src/momdiary/db/repositories/sleeps.py`.
- [X] T061 [P] [US3] Add `update`, `soft_delete`, `is_unchanged` to `backend/src/momdiary/db/repositories/poops.py`.
- [X] T062 [P] [US3] Add `update`, `soft_delete`, `is_unchanged`, and `add_note` to `backend/src/momdiary/db/repositories/appointments.py`.
- [X] T063 [P] [US3] Implement MAF tools `update_feed`, `delete_feed` in `backend/src/momdiary/agents/tools/feeds.py`.
- [X] T064 [P] [US3] Implement MAF tools `update_sleep`, `delete_sleep` in `backend/src/momdiary/agents/tools/sleeps.py`.
- [X] T065 [P] [US3] Implement MAF tools `update_poop`, `delete_poop` in `backend/src/momdiary/agents/tools/poops.py`.
- [X] T066 [P] [US3] Implement MAF tools `update_appointment`, `delete_appointment`, `add_appointment_note` in `backend/src/momdiary/agents/tools/appointments.py`.
- [X] T067 [US3] Register the new update/delete/note tools on the agent in `backend/src/momdiary/agents/diary_agent.py` and extend the system prompt to enforce FR-017 hybrid contract and FR-018 soft-delete rules (depends on T063–T066).
- [X] T068 [US3] Implement `PUT /v1/entries` in `backend/src/momdiary/api/entries.py`: when both `entry_id` and `entry_type` are present, bypass agent target inference and call the matching update tool directly; otherwise hand off to the agent (depends on T067, T058).
- [X] T069 [US3] Wire idempotency short-circuit into the dispatcher: when the repository returns "unchanged", the response body is byte-identical to the previous PUT's body (SC-006).

**Checkpoint**: All three user stories functional and independently testable. Soft delete in place; updates idempotent.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and finalize constitution compliance.

- [X] T070 [P] Unit tests `backend/tests/unit/test_time_service.py` (TZ conversion, DST edges, date-window math).
- [X] T071 [P] Unit tests `backend/tests/unit/test_normalization.py` (oz↔ml rounding, alias mapping, closest-consistency suggestion).
- [X] T072 [P] Unit tests `backend/tests/unit/test_target_resolver.py` (single match, multi-match, no match).
- [X] T073 [P] Update `backend/docs/AGENT_FRAMEWORK_WARNINGS.md` with the exact resolved prerelease versions of `agent-framework` and `agent-framework-azure-ai` from `uv.lock`, and the list of any warning suppressions actually configured (Principle V).
- [X] T074 [P] Add `backend/src/momdiary/agents/README.md` describing tools, the agent's system prompt invariants (FR-002, FR-011, FR-017, FR-018), and the contract-test entry points (Development Workflow clause).
- [X] T075 Add CI configuration (`.github/workflows/backend.yml`) running ruff + mypy + pytest (with coverage thresholds) + benchmark regression gate (> 10% fails) per Principle III; ensure prerelease pip resolution flag is set for MAF packages.
- [X] T076 Run the full `specs/001-baby-tracker-backend/quickstart.md` walkthrough manually against a fresh checkout; record any deviations and fix.
- [X] T077 Security pass: grep the codebase for stray prints/log lines containing secrets or prompts; verify `AZURE_OPENAI_API_KEY` is read only via `Settings`; confirm no secrets are persisted in `agent_interactions.inbound_message` beyond the original user message; document any findings in the PR.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no prerequisites; start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks all user stories**.
- **Phase 3 (US1, P1)**: depends on Phase 2.
- **Phase 4 (US2, P1)**: depends on Phase 2; independent of US1 if staffed in parallel (writes used by US2 tests can be seeded via fixtures or US1).
- **Phase 5 (US3, P2)**: depends on Phase 2; integrates with US1 (uses created entries) and US2 (verifies hidden after soft-delete) but is independently testable.
- **Phase 6 (Polish)**: depends on US1 + US2 + US3 substantially complete.

### User story dependencies

- **US1**: no dependencies on US2/US3.
- **US2**: no dependencies on US1/US3 (date-scoped reads can be tested with fixture-seeded rows).
- **US3**: logically depends on US1's create paths and US2's read paths to verify behavior (an entry must exist to be updated/deleted; GETs verify soft-delete hides entries), but the code paths themselves are independently implementable.

### Within each story

- Tests are written and demonstrated FAILING before the matching implementation tasks (Principle II).
- Repositories before tools.
- Tools before agent wiring.
- Agent wiring before HTTP route registration.

### Parallel opportunities

- Phase 1: T003, T004, T005, T006 in parallel after T001 + T002.
- Phase 2: T008, T009, T013, T014, T015 in parallel after T007; T020, T021 in parallel after T019.
- Phase 3 tests (T022–T024) all parallel; implementation T025–T032 all parallel; T033/T034/T035 sequential.
- Phase 4 tests (T036–T041) all parallel; implementation T042–T049 all parallel; T050 sequential at the end.
- Phase 5 tests (T051–T057) all parallel; implementation T058–T066 all parallel; T067/T068/T069 sequential at the end.
- Phase 6: T070–T074 all parallel; T075 → T076 → T077 sequential.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (must fail before impl):
Task: "T022 [US1] Contract test for log_* tool schemas in backend/tests/contract/test_agent_tools_log.py"
Task: "T023 [US1] Integration test test_routes_each_event_type in backend/tests/integration/test_agent_routing.py"
Task: "T024 [US1] Integration test test_missing_required_field_triggers_clarification in backend/tests/integration/test_agent_routing.py"

# Launch all US1 repository tasks in parallel:
Task: "T025 [US1] feeds repo create/get_by_id in backend/src/momdiary/db/repositories/feeds.py"
Task: "T026 [US1] sleeps repo create/get_by_id in backend/src/momdiary/db/repositories/sleeps.py"
Task: "T027 [US1] poops repo create/get_by_id in backend/src/momdiary/db/repositories/poops.py"
Task: "T028 [US1] appointments repo create_appointment/get_by_id_with_notes in backend/src/momdiary/db/repositories/appointments.py"

# Launch all US1 tool tasks in parallel:
Task: "T029 [US1] log_feed tool in backend/src/momdiary/agents/tools/feeds.py"
Task: "T030 [US1] log_sleep tool in backend/src/momdiary/agents/tools/sleeps.py"
Task: "T031 [US1] log_poop tool in backend/src/momdiary/agents/tools/poops.py"
Task: "T032 [US1] log_appointment tool in backend/src/momdiary/agents/tools/appointments.py"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks every story).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: walk through the User Story 1 portion of `quickstart.md` end-to-end against a real Azure AI Foundry `gpt-4.1` deployment; confirm SC-001 routing accuracy on the curated test set.
5. Optionally ship as the MVP.

### Incremental delivery

1. Phase 1 + Phase 2 → foundation ready.
2. + Phase 3 (US1) → MVP shippable: caregivers can log events conversationally.
3. + Phase 4 (US2) → "review a day" enabled; the product becomes useful day-over-day.
4. + Phase 5 (US3) → corrections and deletes; the dataset becomes trustworthy.
5. + Phase 6 (Polish) → release-grade: CI gates, docs, security pass.

### Parallel team strategy

After Phase 2 completes, three developers can take US1 / US2 / US3 in parallel:

- Dev A: US1 (write path + agent log tools).
- Dev B: US2 (date-scoped reads + perf benchmark).
- Dev C: US3 (update/delete tools + target resolver + idempotency) — coordinates with Dev A on the agent system prompt and tool registration order.

---

## Notes

- Every `[P]` task in this list operates on a distinct file or a clearly disjoint section of a shared file; concurrent execution will not produce merge conflicts.
- Every test task listed before an implementation task is MANDATORY-FIRST per Principle II.
- Tasks T029–T032 share the file convention `backend/src/momdiary/agents/tools/<type>.py` but each writes its own file, so they remain parallel. Tasks T063–T066 extend those same files; mark them sequential with T029–T032 within a single story per file (US3 phase) to avoid clobbering.
- The agent is exercised only via the dispatcher and only with the stub MAF model client in CI; live `gpt-4.1` traffic is reserved for the opt-in evaluation suite outlined in Principle II.
- Avoid: vague tasks ("improve agent"), cross-story dependencies that block US2 on US1 or vice versa, or any task that suppresses warnings outside `agent_framework.*`.
