# Quickstart: Bring MomDiary Up Against Postgres

**Feature**: 009-postgres-migration  
**Audience**: developers and the release operator  
**Pre-req**: you have a Postgres database you can write to (the shared Azure
dev server `legion.postgres.database.azure.com`, a local Postgres container,
or any Postgres ≥ 14).

---

## 1. Backend dev loop

### 1.1 Configure environment

In `backend/.env`:

```ini
# Replaces the SQLite default
MOMDIARY_DB_URL=postgresql+asyncpg://<user>:<password>@legion.postgres.database.azure.com:5432/<db>?ssl=require

# Use the Postgres-backed chat-session store at runtime
MOMDIARY_SESSION_STORE=postgres

# (unchanged) AOAI, Clerk, etc. — keep your existing values
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
CLERK_JWT_ISSUER=https://...
```

> For a per-developer database on the shared server, ask the operator to
> create one (`CREATE DATABASE momdiary_<you>`). Do **not** point your
> local dev at the shared `momdiary` database.

### 1.2 Install / refresh dependencies

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]   # picks up asyncpg
```

### 1.3 Apply migrations (out-of-process, FR-006)

```powershell
cd backend
alembic upgrade head     # runs ONLY 0004_postgres_baseline on a fresh DB
```

Expected: every table from [data-model.md](data-model.md) §A plus
`chat_sessions` from §B exists.

### 1.4 Run the API

```powershell
cd backend
uvicorn momdiary.main:app --reload --port 8000
```

`GET http://localhost:8000/healthz` must return 200 and **must not**
auto-migrate (FR-006). If `alembic_version` is behind the code, startup
fails with a clear error — re-run §1.3.

---

## 2. Smoke test: data + sessions survive a restart

This is the executable version of acceptance scenarios 1 and 2 in
[spec.md](spec.md).

```powershell
# 1. Sign in via the frontend OR mint a Clerk JWT in the dashboard,
#    then export it:
$tok = "Bearer <clerk_jwt>"
$h   = @{ Authorization = $tok }

# 2. Pick a baby (create via frontend or the existing POST /v1/babies)
$bid = 1

# 3. Log one of each entity type
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/feeds `
  -Headers $h -ContentType application/json `
  -Body (@{ baby_id=$bid; ts="2026-06-02T08:00:00-07:00"; quantity_ml=120 } | ConvertTo-Json)
# (repeat for sleeps / poops / appointments)

# 4. Exchange two chat turns
$sess = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat `
  -Headers $h -ContentType application/json `
  -Body (@{ baby_id=$bid; message="Logged 120 ml at 8am" } | ConvertTo-Json)).session_id

Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat `
  -Headers $h -ContentType application/json `
  -Body (@{ baby_id=$bid; session_id=$sess; message="And another 100 ml at 11am" } | ConvertTo-Json)

# 5. RESTART the backend (Ctrl-C and re-run uvicorn).

# 6. Read it all back — must return everything from step 3 and continue
#    the session from step 4 with full history.
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/v1/feeds/by-date?baby_id=$bid&date=2026-06-02" -Headers $h
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat `
  -Headers $h -ContentType application/json `
  -Body (@{ baby_id=$bid; session_id=$sess; message="What's the total today?" } | ConvertTo-Json)
```

PASS criteria: every feed/sleep/poop/appointment from step 3 returned in
step 6; the chat reply in step 6 references both prior turns (i.e. the
session was loaded from Postgres, not lost).

---

## 3. Tests

```powershell
cd backend
# point the test fixture at a Postgres you can write to — defaults to
# MOMDIARY_DB_URL if MOMDIARY_TEST_DB_URL is unset:
$env:MOMDIARY_TEST_DB_URL = "postgresql+asyncpg://<u>:<p>@<host>:5432/momdiary_dev?ssl=require"

pytest           # creates a unique schema per session, runs alembic, drops it
ruff check .
```

Pass criteria (SC-005): the same tests that were green before this
feature are green after, with no skips or deletes beyond ones that
explicitly probed SQLite internals.

---

## 4. Benchmark gate (Constitution III)

```powershell
pytest tests/benchmarks/test_get_by_date.py tests/benchmarks/test_session_store_bench.py --benchmark-only
```

Compare the medians against the pre-migration baseline checked into
[backend/tests/benchmarks/](backend/tests/benchmarks/). A regression > 10%
on any tracked benchmark blocks merge (SC-004 = 100 ms p95 ceiling for
entity reads is stricter than the 10% rule and also applies).

---

## 5. Deploy

Production deploy follows [Deployment.md](Deployment.md) end-to-end
(already updated to drop Cosmos and use Postgres for sessions). The
release pipeline must:

1. Build and ship the new code.
2. Run `alembic upgrade head` exactly once (§7.1 of Deployment.md).
3. Restart App Service so the lifespan starts the TTL sweeper.
4. Hit `/healthz` and verify 200.

The session TTL sweeper logs `"session_ttl_swept rows=<n>"` every 10
minutes from exactly one worker (the advisory-lock holder).

---

## 6. Rollback

Because this is a clean break:

1. Re-deploy the previous container image / SHA.
2. Re-point `MOMDIARY_DB_URL` back to the SQLite default
   (`sqlite+aiosqlite:///./momdiary.db`).
3. App Service comes back on the embedded file. The `chat_sessions` rows
   in Postgres are orphaned but harmless; the next forward deploy reuses
   the same Postgres database without conflict.

No data is migrated in either direction, consistent with FR-013.
