# Contract: Storage Engine Configuration

**Feature**: 009-postgres-migration  
**Source files**:
- [backend/src/momdiary/db/engine.py](backend/src/momdiary/db/engine.py)
- [backend/src/momdiary/config.py](backend/src/momdiary/config.py)
- [backend/alembic.ini](backend/alembic.ini)
- [backend/alembic/env.py](backend/alembic/env.py)

This contract describes the **invariants** the storage layer must
guarantee post-migration. Tests in [tests/integration/](backend/tests/integration/)
enforce them.

## Engine

| ID    | Invariant                                                                                                                                                       |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EN-01 | `create_async_engine` is called exactly once per process; subsequent `get_engine()` calls return the same instance.                                              |
| EN-02 | URL scheme is `postgresql+asyncpg://`. Any other scheme is rejected at engine construction with a clear error.                                                   |
| EN-03 | URL query string contains `ssl=require`. If missing, engine construction fails before any connection is attempted (FR-004 / SC-007).                            |
| EN-04 | Pool configuration: `pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800`. Overridable via env vars but defaults are these values.                |
| EN-05 | No SQLite PRAGMA event listener is installed; `connect_args["timeout"]` is removed.                                                                              |
| EN-06 | `dispose_engine()` and `reset_engine_for_tests()` continue to work (existing test helpers — signatures preserved).                                               |

## Config (new / changed settings)

| Setting                          | Default value                                                                                                  | Notes                                                          |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `momdiary_db_url`                | `postgresql+asyncpg://postgres:postgres@localhost:5432/momdiary?ssl=disable` *(dev placeholder; prod sets via env)* | The SQLite default is removed. Real values come from `.env` / Key Vault. |
| `momdiary_test_db_url`           | `None` (falls back to `momdiary_db_url`)                                                                       | Lets CI / dev override just the test DB.                       |
| `momdiary_db_pool_size`          | `5`                                                                                                            | Override per environment.                                      |
| `momdiary_db_max_overflow`       | `5`                                                                                                            | Override per environment.                                      |
| `momdiary_session_store`         | `"postgres"` in app; `"memory"` in tests by default                                                            | Selects `SessionStore` implementation.                         |
| `momdiary_session_ttl_seconds`   | `86_400` (unchanged)                                                                                           | Drives TTL `DELETE`.                                           |
| `momdiary_session_sweep_interval_seconds` | `600`                                                                                                  | Cadence of the background TTL task.                            |

All existing settings keep their names and defaults; the four `MOMDIARY_SESSION_*`
limit knobs from feature 003 are unchanged.

## Migrations

| ID    | Invariant                                                                                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ |
| MG-01 | `alembic upgrade head` on a fresh empty Postgres database runs **only** `0004_postgres_baseline.py`.                                 |
| MG-02 | After `upgrade head`, every table listed in [data-model.md](../data-model.md) §A plus `chat_sessions` exists with the documented columns and indexes. |
| MG-03 | `alembic/env.py` no longer passes `render_as_batch=True`.                                                                            |
| MG-04 | App startup does **not** run migrations. If `alembic_version.version_num` is behind the latest code revision, the app fails fast with a clear error message naming the missing revision (FR-006). |
| MG-05 | Old revisions `0001_initial.py`, `0002_users_babies.py`, `0003_clerk_users.py` remain on disk but are unreachable from the new baseline (`down_revision = None` on 0004). |

## Background TTL sweeper

| ID    | Invariant                                                                                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ |
| TS-01 | Started from the FastAPI lifespan; cancelled cleanly on shutdown.                                                                    |
| TS-02 | Each tick attempts `pg_try_advisory_lock(<const>)`. Only the lock holder runs the `DELETE`; non-holders log `"session_ttl_skipped"` and sleep. |
| TS-03 | Tick cadence is `momdiary_session_sweep_interval_seconds` (default 600 s).                                                           |
| TS-04 | The `DELETE` predicate is `updated_at < NOW() - make_interval(secs => :ttl)` with `:ttl = momdiary_session_ttl_seconds`.             |
| TS-05 | Each successful run emits a structured log `"session_ttl_swept" rows=<n>` (Constitution: observability).                             |

## Test fixture

| ID    | Invariant                                                                                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ |
| TF-01 | At session start, conftest generates a schema name `test_<uuid_hex_8>` and `CREATE SCHEMA` on the configured Postgres.               |
| TF-02 | The engine for the test session uses `connect_args["server_settings"]["search_path"] = "<schema>,public"`.                           |
| TF-03 | `alembic upgrade head` runs against that schema with `alembic.version_table_schema = <schema>`.                                      |
| TF-04 | On session end, `DROP SCHEMA <schema> CASCADE` runs unconditionally (even on test failure).                                          |
| TF-05 | Per-test isolation strategy (truncate vs transaction-per-test) preserves the behaviour of existing tests; no test is rewritten beyond reading the new URL. |
