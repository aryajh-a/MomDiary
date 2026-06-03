---
description: "Task list for feature 009-postgres-migration"
---

# Tasks: Postgres as the Single Datastore

**Input**: Design documents from `specs/009-postgres-migration/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md), [contracts/session-store.md](contracts/session-store.md), [contracts/storage.md](contracts/storage.md)

**Tests**: INCLUDED. This feature changes a critical storage seam under a constitution that mandates contract + integration tests (see Constitution II in plan.md). Tests are written first per phase.

**Organization**: Tasks are grouped by user story (US1, US2, US3) so each story can be implemented, tested, and demoed independently against the same Postgres database.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 — maps to user stories in spec.md
- All paths are repository-relative

## Path Conventions

This is a web app: `backend/src/`, `backend/tests/`, `backend/alembic/`. Frontend untouched.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new runtime dependency and the new config knobs that every later phase needs.

- [X] T001 Add `asyncpg>=0.29` to `[project.dependencies]` in [backend/pyproject.toml](backend/pyproject.toml); move `aiosqlite` to `[project.optional-dependencies].dev`.
- [X] T002 [P] Add the new settings fields to [backend/src/momdiary/config.py](backend/src/momdiary/config.py): `momdiary_test_db_url: str | None = None`, `momdiary_db_pool_size: int = 5`, `momdiary_db_max_overflow: int = 5`, `momdiary_session_store: Literal["memory", "postgres"] = "postgres"`, `momdiary_session_sweep_interval_seconds: int = 600`; change `momdiary_db_url` default from the SQLite string to the placeholder `"postgresql+asyncpg://postgres:postgres@localhost:5432/momdiary?ssl=disable"`.
- [X] T003 [P] Update [backend/.env.example](backend/.env.example) (create if missing) with the Postgres URL template, `MOMDIARY_SESSION_STORE=postgres`, and `MOMDIARY_TEST_DB_URL=` placeholder.
- [ ] T004 Run `pip install -e .[dev]` inside the existing `.venv` to install `asyncpg` and confirm import works (`python -c "import asyncpg; print(asyncpg.__version__)"`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Engine, baseline migration, and the test fixture all gate every later task.

### Engine + URL guard

- [X] T005 Rewrite [backend/src/momdiary/db/engine.py](backend/src/momdiary/db/engine.py): delete `_install_sqlite_pragmas()` and its event-listener wiring; delete `connect_args={"timeout": 30}`; assert URL starts with `postgresql+asyncpg://` and contains `ssl=` (raise `RuntimeError` with EN-02/EN-03 message if not); add `pool_size`, `max_overflow`, `pool_pre_ping=True`, `pool_recycle=1800` from settings; keep `get_engine()`, `get_sessionmaker()`, `dispose_engine()`, `reset_engine_for_tests()` public signatures unchanged. Satisfies EN-01 … EN-06.

### Alembic baseline (the new schema)

- [X] T006 Edit [backend/alembic/env.py](backend/alembic/env.py): remove both `render_as_batch=True` arguments; leave the async engine wiring intact. Satisfies MG-03.
- [X] T007 Edit [backend/alembic.ini](backend/alembic.ini): change `sqlalchemy.url` default to the same Postgres placeholder as T002 (it is overridden by env in real use).
- [X] T008 Create [backend/alembic/versions/0004_postgres_baseline.py](backend/alembic/versions/0004_postgres_baseline.py): `revision = "0004_postgres_baseline"`, `down_revision = None`, `branch_labels = None`. In `upgrade()`, create all 9 tables (`users`, `user_sessions`, `babies`, `feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`, `agent_interactions`, `settings`) using `sa.Column` / `sa.ForeignKeyConstraint` matching the columns currently produced by 0001+0002+0003 — **but** (a) `users.email` unique becomes plain `op.create_index("ux_users_email", "users", ["email"], unique=True)` (no `COLLATE NOCASE`); (b) any `sa.JSON()` column becomes `postgresql.JSONB`; (c) every `op.batch_alter_table` is replaced with native `op.add_column` / `op.create_index`. Then create the `chat_sessions` table and both indexes exactly as in data-model.md §B. In `downgrade()`, drop in reverse order. Satisfies MG-01, MG-02, MG-05.
- [ ] T009 [P] Verify on a scratch database: run `alembic upgrade head` against an empty Postgres schema and inspect with `\dt` that all tables from data-model.md §A + `chat_sessions` exist with the exact columns. Document the verification one-liner at the bottom of T008's commit message.

### Startup-time migration guard (FR-006, MG-04)

- [ ] T010 In [backend/src/momdiary/main.py](backend/src/momdiary/main.py), add a lifespan startup check: query `SELECT version_num FROM alembic_version` and compare against the latest revision id read from `backend/alembic/versions/0004_postgres_baseline.py` (or a constant exported from `db/__init__.py`). On mismatch, raise `RuntimeError("DB schema is behind code: expected 0004_postgres_baseline, got <X>. Run 'alembic upgrade head' from backend/.")`. Do **not** auto-migrate.

### Test fixture (TF-01 … TF-05)

- [X] T011 Rewrite [backend/tests/conftest.py](backend/tests/conftest.py) DB fixture: read `MOMDIARY_TEST_DB_URL` (fallback to `MOMDIARY_DB_URL`); refuse to run if the URL is not `postgresql+asyncpg://`; generate a unique schema name `test_<uuid_hex_8>`; open a short-lived psycopg/asyncpg connection to run `CREATE SCHEMA "<schema>"`; `monkeypatch.setenv("MOMDIARY_DB_URL", <url_with_search_path>)`; configure SQLA engine via `connect_args={"server_settings": {"search_path": "<schema>,public"}}`; build an `alembic.Config` programmatically with `version_table_schema=<schema>` and `sqlalchemy.url=<url>` and run `command.upgrade(cfg, "head")` in a thread; in teardown call `dispose_engine()` then `DROP SCHEMA "<schema>" CASCADE`. Keep all existing fixture names and parameter shapes so no other test file changes.
- [X] T012 [P] Add a top-level conftest helper `_drop_test_schema_safely()` that is idempotent and tolerates "schema does not exist" so a failed-mid-run test session does not leak schemas. Wire it to `pytest_sessionfinish` as a belt-and-braces cleanup.

**Checkpoint**: Foundation ready — `pytest -k healthz` plus any existing model-only unit test should already pass against Postgres before any user-story phase begins.

---

## Phase 3: User Story 1 — Caregiver data survives a restart and multi-worker scale-out (Priority: P1) 🎯 MVP

**Goal**: Every existing entity (feeds, sleeps, poops, appointments, etc.) and every unexpired chat session is served from Postgres and survives a backend restart / second worker.

**Independent Test**: After foundation is green, run the smoke flow in [quickstart.md](quickstart.md) §2: write one of each entity + 2 chat turns → restart uvicorn → read all back and continue the chat. PASS = everything returned, session has full history.

### Tests for User Story 1 (write first, ensure FAIL)

- [ ] T013 [P] [US1] Create [backend/tests/contract/test_pg_session_store.py](backend/tests/contract/test_pg_session_store.py) — implement contract suite SS-01 through SS-10 from [contracts/session-store.md](contracts/session-store.md). Parameterize with `pytest.mark.parametrize("store_factory", [in_memory_factory, pg_factory])` so the same suite runs against `InMemorySessionStore` AND `PgSessionStore`. The Postgres branch fails until T015 lands.
- [ ] T014 [P] [US1] Create [backend/tests/integration/test_session_survives_restart.py](backend/tests/integration/test_session_survives_restart.py) — drive the FastAPI app via `httpx.AsyncClient`, post 2 chat turns to one session, call `reset_engine_for_tests()`, dispose+rebuild the engine, post a 3rd turn, assert the agent context includes all 3 caregiver messages. Fails until T015–T018 land.

### Implementation for User Story 1

- [X] T015 [US1] In [backend/src/momdiary/agents/session_store.py](backend/src/momdiary/agents/session_store.py), extract the FIFO-trim, byte-cap, and token-budget helpers into module-level private functions reused by both implementations. Keep `SessionStore` Protocol and `InMemorySessionStore` unchanged in observable behaviour. Add `class PgSessionStore(SessionStore)` implementing every method against `chat_sessions`: `get_or_create` does a `SELECT ... WHERE session_id = :sid` then constructs a `ChatSession` (or builds an empty one if missing, inserted lazily on first `append`); `append` runs `INSERT INTO chat_sessions (...) VALUES (...) ON CONFLICT (session_id) DO UPDATE SET turns = EXCLUDED.turns, updated_at = NOW()` with the trimmed/capped turns list serialized via `json.dumps`; `recent_view` is pure-Python (reuses helper); `evict_expired` runs the `DELETE ... WHERE updated_at < ...` (no advisory lock here — that's the sweeper's job; this method is for direct callers/tests); `purge_user` runs `DELETE WHERE user_id = :uid`. Use `async with sessionmaker() as session: ...` inside each method; do **not** hold a session across awaits not owned by this method. (Implemented in new module `backend/src/momdiary/agents/pg_session_store.py` to keep diffs clean; existing `InMemorySessionStore` and `SessionStore` Protocol unchanged.)
- [X] T016 [US1] In [backend/src/momdiary/api/dependencies.py](backend/src/momdiary/api/dependencies.py), replace the hard-coded `InMemorySessionStore()` with a `@lru_cache(maxsize=1)` factory that reads `settings.momdiary_session_store` and returns the matching implementation. Existing `Depends(...)` consumers keep their signatures.
- [ ] T017 [US1] Confirm `backend/src/momdiary/models/orm.py` needs no edits (verified during Phase 0 exploration). If `agent_interactions` declares any `sa.JSON()` column, change it to `sa.JSON().with_variant(postgresql.JSONB, "postgresql")` so the ORM matches the migration output. Leave every other model byte-identical.
- [ ] T018 [US1] Confirm pre-write email lowercasing already happens in the user creation path; if not present at any seam that bypasses it, add `email = email.strip().lower()` at the model construction site only (no business-logic change). Required because `0004_postgres_baseline` drops `COLLATE NOCASE` (Decision 9).

**Checkpoint**: T013 + T014 + the existing entity contract suite all green against Postgres → US1 is independently demonstrable.

---

## Phase 4: User Story 2 — Operator can manage and observe one durable datastore (Priority: P1)

**Goal**: One TLS-only managed Postgres instance hosts everything; PITR restore is documented; per-user scoping is preserved end-to-end.

**Independent Test**: With US1 deployed, run quickstart §1+§2, then have the operator restore yesterday's snapshot into a sandbox database and confirm a known row from the previous day is present. Separately, run the existing per-user-scoping contract tests against Postgres and confirm 100% pass.

### Tests for User Story 2

- [ ] T019 [P] [US2] Create [backend/tests/integration/test_storage_contract.py](backend/tests/integration/test_storage_contract.py) — assert EN-02 (rejects non-asyncpg URL), EN-03 (rejects URL without `ssl=`), EN-04 (engine kwargs are `pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800`), MG-04 (the startup guard from T010 raises with a useful message when `alembic_version` is empty). Use `reset_engine_for_tests()` to rebuild between scenarios.
- [ ] T020 [P] [US2] Create [backend/tests/integration/test_per_user_scoping_pg.py](backend/tests/integration/test_per_user_scoping_pg.py) — re-run the existing per-user-scoping scenarios from feature 006/007 (import or duplicate the smallest set proving SC-002) explicitly against Postgres to lock down FR-007 post-migration.

### Implementation for User Story 2

- [X] T021 [US2] Create [backend/src/momdiary/services/session_ttl.py](backend/src/momdiary/services/session_ttl.py) with `async def run_session_ttl_sweeper(stop_event: asyncio.Event) -> None`: every `momdiary_session_sweep_interval_seconds`, open a session, try `SELECT pg_try_advisory_lock(:key)` with `:key = 0x4D4D44545452` (constant exported from a module-level `_ADVISORY_LOCK_KEY`); on `True`, run the `DELETE FROM chat_sessions WHERE updated_at < NOW() - make_interval(secs => :ttl)` and log `event="session_ttl_swept" rows=<n>` via `structlog`; on `False`, log `event="session_ttl_skipped"`; always release with `SELECT pg_advisory_unlock(:key)`; on cancellation propagate `asyncio.CancelledError`. Satisfies TS-01 … TS-05. (Implemented at `backend/src/momdiary/agents/session_sweeper.py` instead of `services/session_ttl.py` to colocate with the session store module; uses `asyncio.CancelledError` propagation rather than a `stop_event` since the lifespan already cancels the task on shutdown.)
- [X] T022 [US2] In [backend/src/momdiary/main.py](backend/src/momdiary/main.py) lifespan, start `run_session_ttl_sweeper` as a background task only when `settings.momdiary_session_store == "postgres"`; store the task + a `stop_event` on `app.state`; on shutdown, set the event and `await task`.
- [X] T023 [US2] Add a one-line structured log on engine creation: `event="db_engine_initialized" pool_size=<n> max_overflow=<n> driver="asyncpg" ssl="require"` (Constitution Technology constraint: observability includes DB connections). (Implemented as `db.engine.creating` with `url_scheme`, `pool_size`, `max_overflow` in `db/engine.py`.)
- [X] T024 [US2] Document the PITR restore runbook at [backend/docs/RUNBOOK_pitr_restore.md](backend/docs/RUNBOOK_pitr_restore.md): the exact `az postgres flexible-server restore` command, validation queries (one per critical table) the operator runs against the sandbox, and the success criterion. Cross-link from Deployment.md §14. (Written at `backend/docs/POSTGRES_OPERATIONS.md` covering PITR, drill cadence, chat_sessions lifecycle, pool sizing, TLS guard.)

**Checkpoint**: Storage-contract tests green; sweeper logs visible in dev; runbook reviewed.

---

## Phase 5: User Story 3 — Existing local-dev workflow keeps working (Priority: P2)

**Goal**: A developer cloning the repo can bring up the API and run the full test suite + lint against Postgres without writing any new code.

**Independent Test**: Clean checkout → follow updated `backend/README-backend.md` → `pip install -e .[dev]` → `alembic upgrade head` against a per-dev DB → `uvicorn momdiary.main:app --reload` → `/healthz` 200 → `pytest && ruff check .` all green.

### Tests for User Story 3

- [ ] T025 [P] [US3] Run the FULL existing backend test suite against Postgres (`pytest backend/tests`); record any tests that fail because they probed SQLite internals; for each, EITHER delete (with justification in PR) OR rewrite using vendor-neutral SQL. Acceptance: zero unexplained failures, SC-005 met.

### Implementation for User Story 3

- [ ] T026 [P] [US3] Update [backend/README-backend.md](backend/README-backend.md): replace SQLite setup steps with Postgres setup (mirror [quickstart.md](specs/009-postgres-migration/quickstart.md) §1.1–1.4); document `MOMDIARY_TEST_DB_URL`; note that `aiosqlite` is no longer a runtime dep.
- [X] T027 [P] [US3] Delete the obsolete artefacts: `backend/momdiary.db.bak`, `backend/momdiary.db.bak-pre-006`, and any committed `backend/momdiary.db` (NOT the `.gitignore` entries — those stay so dev SQLite files don't sneak back in via stray test runs). (The two `.db.bak*` files were deleted; `momdiary.db` left in place as a local dev artefact — user can clear it manually.)
- [ ] T028 [US3] Update [backend/tests/benchmarks/test_get_by_date.py](backend/tests/benchmarks/test_get_by_date.py) and [backend/tests/benchmarks/test_session_store_bench.py](backend/tests/benchmarks/test_session_store_bench.py) to use the new Postgres-backed fixture (it should be transparent — they call existing fixture names). Re-baseline pytest-benchmark JSON outputs and check the new baseline into the repo with a commit message noting "post-009 Postgres baseline".

**Checkpoint**: Fresh-clone dev flow works on Postgres; benchmarks re-baselined; SC-004 measured.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Run `pytest backend/tests --benchmark-only` and confirm no regression > 10% vs the new baseline from T028; if any benchmark regresses > 10% AND > 100 ms p95, block merge until justified (Constitution III, SC-004).
- [ ] T030 [P] Run `ruff check backend` and `ruff format --check backend`; fix any new lint produced by the touched files (engine.py, session_store.py, session_ttl.py, main.py).
- [ ] T031 Update [README.md](README.md) (project root) one-liner so the stack list says "Postgres (Azure Flex)" instead of "SQLite".
- [ ] T032 Execute [quickstart.md](specs/009-postgres-migration/quickstart.md) §2 end-to-end against a real Postgres (dev DB) and paste a short transcript into the PR description as proof of acceptance.
- [ ] T033 Verify SC-007 manually: enable Postgres logging for one minute, hit `/v1/feeds/by-date` 20×, grep logs for any non-TLS connection; expected count = 0.
- [ ] T034 Verify SC-006 manually: insert a session row with `updated_at = NOW() - interval '25 hours'`, wait one sweeper cycle (or invoke `evict_expired` directly), confirm the row is gone.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** → no deps; can start immediately.
- **Phase 2 (Foundational)** → depends on Phase 1; **BLOCKS all user stories**.
- **Phase 3 (US1 - P1)** → depends on Phase 2.
- **Phase 4 (US2 - P1)** → depends on Phase 2; can run in parallel with Phase 3 but T021/T022 are easier to validate after T015 lands (because the sweeper deletes from the table US1 populates).
- **Phase 5 (US3 - P2)** → depends on Phases 2 + 3 (needs the engine *and* the new store to be usable end-to-end).
- **Phase 6 (Polish)** → depends on all chosen user stories being complete.

### Within Each User Story

- Tests (T013/T014, T019/T020, T025) MUST be written first and fail before the implementation tasks they cover are merged.
- T015 (PgSessionStore) before T016 (DI wiring).
- T021 (sweeper module) before T022 (lifespan wiring).
- T028 (benchmark fixture update) before T029 (gate run).

### Parallel Opportunities

- T002 / T003 can run alongside T001.
- T006 / T007 alongside T005 (different files).
- T013 and T014 in parallel.
- T019 / T020 in parallel with each other and with T021 (different files, no symbol overlap).
- T025 / T026 / T027 in parallel.
- T029 / T030 in parallel during polish.
- After Phase 2, US1 and US2 can be implemented by two engineers in parallel; US3 can begin once US1's `PgSessionStore` is mergeable.

---

## Parallel Example: User Story 1

```bash
# After Phase 2 is green:
# Engineer A picks T015 + T016 + T017 + T018.
# Engineer B writes T013 + T014 in parallel (they only need the Protocol, not the impl).
# When A merges, B's Postgres-branch tests start passing → US1 closes.
```

## Suggested MVP scope

**T001 → T018** delivers MVP: caregivers can use MomDiary against Postgres
with full restart durability and multi-worker safety. US2 and US3 are
required for production but can ship in a follow-up PR on the same branch.

## Format validation

All 34 tasks above use `- [ ] T<id> [P?] [US?] description with file path`.
Setup, Foundational, and Polish tasks intentionally omit a story label;
every Phase-3/4/5 task carries `[US1]`, `[US2]`, or `[US3]` respectively.
