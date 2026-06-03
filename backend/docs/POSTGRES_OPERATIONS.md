# Postgres Operations Runbook (feature 009)

> Covers the operational concerns of running MomDiary on Azure Database
> for Postgres Flexible Server: point-in-time restore, restore drills,
> session-store TTL behaviour, and the `chat_sessions` JSONB lifecycle.

## 1. Backups & point-in-time restore (PITR)

Azure Postgres Flexible Server provides automated full + incremental backups
with **7-day default retention** (configurable up to 35 days). PITR is the
documented recovery path — there is no application-side dump-and-restore.

**Operational expectations:**
- RPO target: ≤5 minutes (Azure-managed WAL archiving cadence).
- RTO target: ≤1 hour (provisioning a restore-target server is the dominant
  cost; the data copy itself is incremental from the backup vault).
- Backups cover the **entire database**, including both the relational
  diary tables and the `chat_sessions` JSONB table. There is no separate
  store to coordinate.

**To trigger a restore:**

```bash
az postgres flexible-server restore \
  --resource-group <rg> \
  --name <new-server-name> \
  --source-server legion \
  --restore-time "2026-06-02T14:00:00Z"
```

After the restore-target server is online:
1. Update `MOMDIARY_DB_URL` in App Service config (or rotate the Key Vault
   secret backing it).
2. Restart the App Service plan so all workers re-open pooled connections.
3. Confirm the Alembic head is `0004` (or whatever the current production
   head is) by querying `SELECT version_num FROM alembic_version;`. PITR
   restores the schema-version row alongside the data, so this should
   already match.

## 2. Restore drill cadence

A quarterly restore drill is required (FR-016, SC-005). Drill checklist:

- [ ] Stand up a non-prod server from the latest backup (PITR to "now").
- [ ] Run `pytest -k smoke` against the restored server (point
      `MOMDIARY_TEST_DB_URL` at it).
- [ ] Confirm the smoke set passes within RTO.
- [ ] Tear down the restore-target server.
- [ ] File a runbook update if any step diverged from this document.

## 3. `chat_sessions` lifecycle

- The table is the only data structure feature 009 added on top of the
  feature 008 schema (see `alembic/versions/0004_postgres_baseline.py`).
- Per-row TTL is enforced by the **background sweeper** in
  `momdiary.agents.session_sweeper`. It runs every
  `MOMDIARY_SESSION_SWEEP_INTERVAL_SECONDS` (default 600s) and DELETEs rows
  with `updated_at < NOW() - MOMDIARY_SESSION_TTL_SECONDS`.
- Multiple FastAPI workers cooperate via `pg_try_advisory_lock(0x4D4D44545452)`
  so only one worker per cycle issues the DELETE. Workers that lose the
  lock log `session.sweeper.lock_held_elsewhere` at DEBUG and sleep.
- Per-caregiver hard purge happens in `PgSessionStore.purge_user`, called
  from the Clerk `user.deleted` webhook.
- Table size is bounded: TTL × peak active caregivers × per-caregiver
  session count. With 24h TTL and 100 active caregivers × 1 session each,
  expect ≤100 rows steady-state.

## 4. Schema migrations

- Production Alembic head: `0004_postgres_baseline.py`. This is the
  *baseline* revision — `down_revision=None`. SQLite-era revisions
  (`0001_initial.py`, `0002_users_babies.py`, `0003_clerk_users.py`)
  are retained under `alembic/versions_legacy_sqlite/` for historical
  reference only and are NOT loaded by Alembic.
- To deploy schema changes:
  1. Create a new `00NN_*.py` revision in `alembic/versions/` with
     `down_revision="0004"` (or the latest head).
  2. CI runs `alembic upgrade head` against the test schema before
     promoting the image.
  3. Production runs `alembic upgrade head` as a one-shot job before the
     new image takes traffic (App Service deployment slot swap).

## 5. Connection pooling & sizing

- App-side pool: `pool_size=5, max_overflow=5` per worker (config
  defaults; tune via `MOMDIARY_DB_POOL_SIZE` / `MOMDIARY_DB_MAX_OVERFLOW`).
- Across 4 workers × 2 App Service instances = 80 max steady connections,
  well under the B1ms 50-per-server cap. **Scale up** the Postgres SKU
  before bumping `pool_size` beyond 5.
- `pool_pre_ping=True` and `pool_recycle=1800` handle Azure's idle
  connection reaper without surfacing transient `OperationalError`s to
  request handlers.

## 6. TLS

- Production URLs MUST include `?ssl=require`. The engine guard in
  `momdiary.db.engine._validate_postgres_url` raises `RuntimeError` at
  startup if the URL is missing the `ssl=` parameter, so misconfigured
  deployments fail fast rather than silently connecting over cleartext.
