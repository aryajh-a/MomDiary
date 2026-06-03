# Phase 0 Research: Postgres Migration

**Feature**: 009-postgres-migration  
**Date**: 2026-06-02

This document records the technical decisions that resolve every open
"NEEDS CLARIFICATION" implied by the Technical Context. The spec itself
has no open clarifications (FR-013 resolved as clean-break). All
remaining decisions below are *technical* choices made during planning.

---

## Decision 1 — Driver: `asyncpg` (via SQLAlchemy `postgresql+asyncpg://`)

**Decision**: Use `asyncpg>=0.29` as the async Postgres driver, wired
through SQLAlchemy 2.x with the `postgresql+asyncpg://` URL scheme.

**Rationale**:
- The codebase is already 100% SQLAlchemy async (`AsyncSession`,
  `async_sessionmaker`); `asyncpg` is the canonical SQLAlchemy async
  driver for Postgres and slot-in compatible. No ORM changes required.
- `asyncpg` outperforms `psycopg[binary]` on async workloads (the
  numbers are not the point here — the point is "drop-in for SQLA
  async").
- Azure Postgres Flexible Server officially supports the libpq protocol
  used by `asyncpg`.

**Alternatives considered**:
- `psycopg[async]` (v3): also async-capable. Rejected: marginally
  slower for this workload and not the default async driver in SQLA
  docs; no advantage.
- `psycopg2-binary` (sync): would require sync engine + ThreadPool
  bridging. Rejected: defeats the existing async architecture.

---

## Decision 2 — TLS: `sslmode=require` baked into the URL

**Decision**: Always include `?ssl=require` in the Postgres URL (the
`asyncpg` flavour of `sslmode`). Reject any URL that doesn't.

**Rationale**:
- FR-004 requires TLS; SC-007 audits it.
- Azure Postgres Flex enforces TLS server-side, but failing early in
  the app is better UX than a confusing handshake error.
- `asyncpg` reads `ssl=require` from the SQLA URL params and translates
  to its own `ssl` parameter.

**Alternatives considered**:
- Set `ssl=` via `connect_args` in `create_async_engine`. Rejected: URL
  string is more visible in logs and harder to misconfigure than a code
  parameter.

---

## Decision 3 — Connection pool: `pool_size=5, max_overflow=5, pool_recycle=1800`

**Decision**: Configure the engine with `pool_size=5, max_overflow=5,
pool_pre_ping=True, pool_recycle=1800`.

**Rationale**:
- Azure Postgres B1ms cap is ~50 connections. With gunicorn `workers=4`
  per App Service instance and 2 instances target in prod, 4 × 2 × 10
  = 80 worst-case connections. 5+5 keeps us at 40 worst case with
  headroom for `pg_cron` / admin sessions and stays under the cap.
- `pool_pre_ping=True` defends against Azure idle-connection resets.
- `pool_recycle=1800` matches Azure's 30-minute idle timeout default.

**Alternatives considered**:
- Default unlimited pool. Rejected: trivially exhausts B1ms under burst
  load.
- PgBouncer in transaction mode. Rejected: not justified at MomDiary's
  scale; adds a service to operate. Revisit if we sustain > 100
  concurrent connections.

---

## Decision 4 — Migration strategy: one new "baseline" revision (0004), keep 0001-0003 in history

**Decision**: Author a new Alembic revision `0004_postgres_baseline.py`
whose `upgrade()` builds the **entire current schema** (every table from
0001 + 0002 + 0003 collapsed) **using vanilla SQLAlchemy / Postgres
operations** (no `op.batch_alter_table`, no `COLLATE NOCASE`,
`JSON` → `JSONB`), **plus** the new `chat_sessions` table. Existing
revisions 0001–0003 stay on disk as historical artefacts but are
**unreachable** from a fresh Postgres database because we set
`down_revision = None` on 0004 and remove the heads of the legacy chain
via `alembic_version` reset (clean break per FR-013).

**Why this is acceptable**:
- FR-013: clean break. No production data to preserve.
- The 0001–0003 revisions are SQLite-specific (`render_as_batch=True`,
  `COLLATE NOCASE`, `op.batch_alter_table(... recreate="always")`) and
  would error or behave incorrectly on Postgres. Replaying them is
  pointless.
- Keeping the files preserves git history and lets the team read what
  the previous shape was.

**Rationale (vs alternatives)**:
- *Patch each old revision to be cross-dialect*: brittle, more code, no
  benefit because there's no existing Postgres DB to upgrade.
- *Delete the old revision files entirely*: loses history, makes
  `git blame` worse, no upside.
- *Use `alembic stamp`*: still requires the schema to exist; collapsing
  into a single baseline gives us one authoritative starting point.

**Operational note**: The first `alembic upgrade head` against the new
empty Postgres database runs only `0004_postgres_baseline.py`. Old
revisions never execute.

---

## Decision 5 — Chat session storage shape: one row per session, `JSONB` turns

**Decision**:

```sql
CREATE TABLE chat_sessions (
    session_id     VARCHAR(64)   PRIMARY KEY,
    user_id        VARCHAR(64)   NOT NULL,
    baby_id        INTEGER       NOT NULL,
    turns          JSONB         NOT NULL DEFAULT '[]'::jsonb,
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_chat_sessions_user_baby_updated
    ON chat_sessions (user_id, baby_id, updated_at DESC);
CREATE INDEX ix_chat_sessions_updated_at
    ON chat_sessions (updated_at);
```

Writes are upserts: `INSERT … ON CONFLICT (session_id) DO UPDATE SET
turns = $2, updated_at = NOW()`. FIFO trim + per-message byte cap
happen in Python *before* the upsert (same logic that
`InMemorySessionStore` already enforces — reused via shared helpers).

**Rationale**:
- Mirrors the existing in-memory shape (`ChatSession` dataclass with a
  list of `ChatTurn`s). Serialising the turn list to JSONB lets us
  reuse the existing dataclass without designing a row-per-turn schema.
- Read pattern is "fetch one session by id" → primary-key lookup, O(1).
- One row per session ⇒ no per-turn write amplification.
- TTL eviction is one `DELETE WHERE updated_at < …` per cycle.
- Two indexes cover (a) "expire idle sessions" and (b) any future
  "recent sessions for this user/baby" query, both already used by the
  in-memory store's debug-list path.

**Alternatives considered**:
- *Row per turn* (normalized). Rejected: doubles round-trips, no query
  pattern needs it.
- *Cosmos DB / Redis*. Explicitly rejected in Deployment.md §1 for this
  scale.

---

## Decision 6 — TTL eviction: background asyncio task with `pg_try_advisory_lock`

**Decision**: A background task started from the FastAPI lifespan calls
`DELETE FROM chat_sessions WHERE updated_at < NOW() - make_interval(secs => :ttl)`
every 600 seconds. Before each run it takes a Postgres advisory lock
(`pg_try_advisory_lock(0x4D4D44545452L)` — a constant chosen for
"MMDTTR" mnemonic) so only one worker across all instances actually
deletes; other workers skip the run.

**Rationale**:
- Single-Postgres deployment ⇒ no extra moving parts.
- Advisory locks are cheap, automatic-release on disconnect, and
  cluster-wide — exactly the leader-election primitive we need without
  introducing ZK/etcd/Redis.
- 10-minute cadence + 24-hour TTL ⇒ steady-state rows ≈ peak
  concurrent sessions; alert from Deployment.md §10 ("`chat_sessions`
  row count > 10K") catches a stuck sweeper.

**Alternatives considered**:
- `pg_cron`. Rejected as default: not enabled by default on Azure
  Postgres Flex (requires server-parameter change + extension toggle);
  documented as fallback in Deployment.md §5.3.
- GitHub Actions nightly. Rejected as default: introduces an
  out-of-cluster dependency for a steady-state cleanup; documented as
  fallback in Deployment.md §5.3.
- *No TTL in app, rely on serverless or storage cap*. Rejected: FR-012
  requires bounded growth.

---

## Decision 7 — `SessionStore` Protocol stays; `PgSessionStore` is a sibling implementation

**Decision**: Keep the existing `SessionStore` Protocol and the
`InMemorySessionStore` class in
[backend/src/momdiary/agents/session_store.py](backend/src/momdiary/agents/session_store.py).
Add `PgSessionStore` in the same module implementing the same Protocol
(same method signatures). The DI factory in `api/dependencies.py`
selects between them based on a new config flag
`momdiary_session_store` (values `"memory"` (default in tests) /
`"postgres"` (default in app)). FIFO trim, token-budget view, per-user
purge, and expiry are reused from a shared module-level helper so the
two implementations don't drift.

**Rationale**:
- Satisfies Constitution IV ("agent capabilities MUST be pluggable").
- Lets tests run against the fast in-memory store *or* the real
  Postgres-backed store, with the contract test enforcing parity.
- Keeps the blast radius of this feature inside one module + one new
  config knob.

**Alternatives considered**:
- *Delete `InMemorySessionStore` entirely*. Rejected: it's still useful
  for unit tests that don't need a database, and the Protocol
  abstraction costs nothing.

---

## Decision 8 — Test database: ephemeral schema on Postgres, one per session

**Decision**: `conftest.py` reads `MOMDIARY_TEST_DB_URL` (a Postgres
URL the developer/CI provides — defaults to the shared Azure dev
server). At session start, it generates a unique schema name
(`test_<uuid_hex_8>`), creates the schema, sets
`SQLAlchemy` engine `connect_args={"server_settings": {"search_path":
"<schema>,public"}}`, runs `alembic upgrade head` with the same URL,
then drops the schema in teardown. Alembic's `version_table_schema` is
pinned to the same per-test schema so concurrent test runs don't
collide on `alembic_version`.

**Rationale**:
- Reuses existing Alembic migration machinery (no separate schema
  fixture).
- One schema per test session ⇒ zero cross-test interference.
- Works against any Postgres (local container, Azure dev DB) — no
  hard-coded host.
- Schema drop is one statement; no file cleanup like the old SQLite
  fixture needed.

**Alternatives considered**:
- *In-memory SQLite for tests*. Rejected: defeats the whole point of
  the migration; would mask Postgres-only bugs (JSONB defaults, advisory
  locks, COLLATE).
- *Docker Postgres ephemeral container per test*. Rejected as default:
  slow startup, complicates CI. Documented as supported via overriding
  `MOMDIARY_TEST_DB_URL`.
- *Transaction-rollback fixture*. Rejected: doesn't compose well with
  Alembic schema creation; advisory-lock and TTL tests need real
  committed state.

---

## Decision 9 — Email uniqueness without `COLLATE NOCASE`: lowercase email at write time

**Decision**: Drop the SQLite-only `COLLATE NOCASE` from the unique
email index. The existing user-creation path **already** normalises
email to lowercase before insert (this is current code — confirmed
during exploration); the unique index in Postgres becomes a plain
`UNIQUE (email)`. No `citext` extension required (one less moving
part).

**Rationale**:
- Lowercasing at write time is the canonical Postgres-friendly pattern.
- Avoids requiring the `citext` extension (Azure supports it but it
  takes a server-parameter change).
- Pre-existing data is dropped (FR-013), so there is no legacy
  mixed-case email to worry about.

**Alternatives considered**:
- *Enable `citext` extension and use `citext` column*. Rejected:
  unnecessary at this scale and adds an extension dependency that has
  to be re-enabled in every Postgres instance.
- *Functional index `LOWER(email)`*. Rejected: existing code already
  lowercases, so the function-index would be redundant; if we ever
  stop lowercasing, this is the fallback.

---

## Decision 10 — Migration execution: out-of-process release step, not on app startup

**Decision**: Migrations run via a single explicit command
(`alembic upgrade head`) executed by the release pipeline (or
`az webapp ssh` for ad-hoc), **not** from FastAPI startup. App startup
fails fast with a clear error if `alembic_version.version_num`
doesn't match the latest revision pinned in code.

**Rationale**:
- FR-006 forbids implicit startup migrations.
- Multi-worker startup races corrupt schema; out-of-process
  serialisation eliminates the risk.
- Startup-time version check gives a fast, clear failure mode if a
  deploy ships code newer than the migrated schema.

**Alternatives considered**:
- *Auto-migrate on startup with a lock*. Rejected: FR-006 forbids it
  and Deployment.md §7.1 explicitly disallows it.

---

## Decision 11 — Frontend: no change

**Decision**: No frontend code changes for this feature. Public API
contracts and payload shapes are unchanged (FR-008).

**Rationale**: Pure storage swap; status codes, fields, and auth
contract preserved.

---

## Summary of resolved unknowns

| Unknown                                       | Decision                              |
| --------------------------------------------- | ------------------------------------- |
| Async Postgres driver                         | `asyncpg` via `postgresql+asyncpg://` |
| TLS handling                                  | `?ssl=require` in URL, fail-fast      |
| Connection pool sizing                        | `pool_size=5, max_overflow=5`         |
| Alembic strategy on clean break               | New `0004_postgres_baseline.py`       |
| Chat-session row shape                        | One row + `JSONB` turns               |
| TTL eviction mechanism                        | App background task + advisory lock   |
| Reuse strategy for in-memory store            | Keep Protocol, add `PgSessionStore`   |
| Test database strategy                        | Ephemeral schema on Postgres          |
| Case-insensitive email uniqueness             | Lowercase at write, plain `UNIQUE`    |
| When migrations run                           | Out-of-process release step           |
| Frontend impact                               | None                                  |
