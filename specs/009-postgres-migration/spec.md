# Feature Specification: Postgres as the Single Datastore

**Feature Branch**: `009-postgres-migration`  
**Created**: 2026-06-02  
**Status**: Draft  
**Input**: User description: "I want to start using postgresql which is deployed in azure legion.postgres.database.azure.com for storing everything : entities as well as session."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Caregiver data survives an app restart and multi-worker scale-out (Priority: P1)

A caregiver logs feeds, sleeps, poops, and appointments throughout the day,
chats with the diary assistant, then closes the browser. Hours later — after
the backend has been restarted and/or scaled to more than one worker /
instance — she opens MomDiary again, picks her baby, and expects to see
every entry she logged and to resume any chat session that has not yet
expired.

**Why this priority**: Today the relational data lives in a local SQLite
file on the API host and chat sessions live in a Python dict inside one
worker process. Either restarting the host or running more than one worker
silently loses data or splits sessions across processes. This is the
blocking issue for running MomDiary on App Service (which uses multiple
workers by default and may move the host at any time).

**Independent Test**: Stand up the API against the shared Postgres
instance, write one entry of each kind and exchange a few chat turns,
restart every backend process, hit the same endpoints from a second
worker/replica, and confirm all entries and the unexpired chat session are
still returned exactly as written.

**Acceptance Scenarios**:

1. **Given** a caregiver has logged a feed, a sleep, a poop, and an
   appointment against her baby today, **When** the backend host is
   restarted and a follow-up `GET /v1/<entity>/by-date` request lands on a
   different worker, **Then** all four entries are returned with the same
   values, ids, and ordering as before the restart.
2. **Given** a caregiver has exchanged 6 turns in a chat session, **When**
   the next request for that session lands on a different worker, **Then**
   the assistant sees the full prior turn history and continues the
   conversation without restarting it.
3. **Given** the shared database is reachable, **When** two backend
   instances accept writes for the same baby at the same time, **Then**
   both writes succeed and both appear in subsequent reads (no per-process
   state drift).

---

### User Story 2 - Operator can manage and observe one durable datastore (Priority: P1)

The operator running MomDiary needs to back up, restore, monitor, and
secure caregiver data in one place. Today there are two stores with
different operational shapes (an on-host file and an in-memory dict);
neither is backed up, neither can be inspected with standard SQL tooling,
and there is no story for point-in-time recovery.

**Why this priority**: Without a single managed store, the app cannot be
operated to a basic durability and compliance bar (PITR, audit, access
control via a managed identity / least-privilege login, encrypted at
rest + in transit). This is the second blocker for any non-toy
deployment.

**Independent Test**: Connect to the Azure-hosted database with a standard
SQL client using the operator credentials, confirm every entity table and
the session table are present with the expected schema, take an on-demand
backup, restore it into a sandbox database, and confirm the data matches.

**Acceptance Scenarios**:

1. **Given** the operator opens the Azure-hosted database, **When** they
   list tables, **Then** every existing diary entity table (users,
   user_sessions, babies, feeds, sleeps, poops, appointments, …) and the
   chat-session table are present and queryable with standard SQL.
2. **Given** point-in-time backups are enabled on the database, **When**
   the operator restores yesterday's snapshot into a sandbox, **Then**
   the restored database contains the same rows the production database
   had at that point in time.
3. **Given** caregiver A is signed in, **When** caregiver A queries any
   endpoint that returns entity data, **Then** the response only contains
   rows owned by caregiver A's babies — i.e., per-user scoping behaviour
   is preserved end-to-end after the migration.

---

### User Story 3 - Existing local-dev workflow continues to work (Priority: P2)

A developer clones the repo, runs the documented backend setup, and is
able to bring up a working API against a developer Postgres (either the
shared Azure server using a dev credential, or a local Postgres) without
provisioning extra Azure infrastructure for unit tests and without losing
the existing `pytest`/lint workflow.

**Why this priority**: Without a workable dev story the migration blocks
day-to-day feature work. Important, but not blocking production launch.

**Independent Test**: From a clean checkout, follow the updated backend
README to bring up the API against Postgres, run the existing
`pytest` + `ruff` gates, and confirm they pass.

**Acceptance Scenarios**:

1. **Given** a developer with the documented dev credentials, **When**
   they run the backend startup command, **Then** the API starts, applies
   schema migrations idempotently, and serves `/healthz` successfully.
2. **Given** the developer runs the project test suite, **When** the
   tests execute, **Then** every test that previously passed against the
   embedded store still passes against Postgres (using either the shared
   dev database or an ephemeral Postgres) with no test rewrites required
   beyond connection configuration.

---

### Edge Cases

- The Azure Postgres server is briefly unreachable (network blip, planned
  maintenance, failover). The API must surface a clear, retryable error to
  the client rather than corrupt state or silently lose writes.
- Connection pool exhaustion under burst load. The API must back off and
  return a retryable error instead of crashing the worker.
- A chat session expires (TTL elapsed) between two caregiver messages.
  The next message must start a fresh session rather than silently
  resurrect expired turns.
- Schema-migration races on multi-instance startup. Migrations must be
  applied exactly once per release; multiple workers starting at the same
  time must not corrupt schema.
- A row written by one backend instance must be visible to a read from
  another instance immediately after the write commits (strong read-after-
  write within a single user's session).
- Pre-migration SQLite data is intentionally dropped at cutover (see
  FR-013). Caregivers attempting to use legacy accounts after cutover
  must re-register; this is an accepted, communicated behaviour for a
  pre-launch app, not a defect.
- TLS is required end-to-end. Plaintext connections to the database must
  be refused.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist all relational entities currently
  stored in the embedded database (users, user sessions, babies, feeds,
  sleeps, poops, appointments, and any other diary entity present at
  cutover) in the Azure-hosted Postgres server at
  `legion.postgres.database.azure.com`.
- **FR-002**: The system MUST persist chat sessions (turn history, the
  owning user, the active baby, last-updated timestamp) in the same
  Postgres server so that any backend worker or instance can read and
  resume any unexpired session.
- **FR-003**: The system MUST enforce a chat-session inactivity timeout
  consistent with the value already used today, after which an unused
  session is no longer returned to callers.
- **FR-004**: The system MUST require TLS for every database connection
  and MUST reject plaintext connections.
- **FR-005**: The system MUST authenticate to the database using a
  credential stored outside source control (environment variable backed
  by a secrets store in deployed environments, `.env` for local dev).
- **FR-006**: The system MUST apply schema migrations to Postgres in a
  single, repeatable, automated step that is safe to run from a release
  pipeline and is NOT executed implicitly on every worker startup.
- **FR-007**: The system MUST preserve all existing per-user scoping
  behaviour: a caregiver may only read or modify entities and sessions
  that belong to babies they own.
- **FR-008**: The system MUST keep every existing public API surface
  (request/response shapes, status codes, and authentication contract)
  unchanged after the migration; only the underlying store changes.
- **FR-009**: The system MUST report a clear, retryable error to the
  caller when the database is temporarily unavailable, and MUST NOT
  silently drop writes.
- **FR-010**: The system MUST remove the in-memory chat-session store and
  the embedded SQLite file from the deployed runtime so there is exactly
  one source of truth per environment.
- **FR-011**: The system MUST allow the operator to perform point-in-time
  recovery of the database and to inspect data with standard SQL tooling.
- **FR-012**: The system MUST expire idle chat-session rows from Postgres
  (so the session table does not grow without bound) on a schedule
  consistent with the inactivity timeout in FR-003.
- **FR-013**: The cutover to Postgres MUST be a clean break: pre-existing
  rows in the legacy SQLite file are NOT migrated, and the SQLite file is
  removed from the deployed runtime. Caregivers are expected to re-create
  their accounts and data in Postgres. (Consistent with the 006 cutover,
  which also hard-deleted pre-existing rows.)
- **FR-014**: Local-developer setup MUST continue to support running the
  full test suite and the API without requiring write access to a shared
  production database; either ephemeral/local Postgres for tests or a
  per-developer schema/database on the shared server is acceptable.

### Key Entities *(include if feature involves data)*

- **All existing diary entities** (users, user sessions, babies, feeds,
  sleeps, poops, appointments, and any other entity present at cutover):
  identity, ownership, timestamps, and per-baby scoping unchanged; only
  the storage location moves to Postgres.
- **Chat session**: an ongoing conversation between one caregiver and the
  diary assistant for one baby. Holds session id, owning user, active
  baby, ordered turn history (caregiver + assistant pairs), and a
  last-activity timestamp used to compute expiry. Lives in Postgres so any
  worker can resume it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the cutover, 100% of caregiver-visible reads and
  writes are served from Postgres; the embedded SQLite file is no longer
  present on the deployed host and the in-memory chat-session store is no
  longer instantiated.
- **SC-002**: Restarting the backend host or scaling to ≥2 backend workers
  or instances causes zero loss of caregiver entries and zero loss of
  unexpired chat sessions in a smoke test that exercises one of each
  entity type and at least one multi-turn chat.
- **SC-003**: A point-in-time restore of the production database into a
  sandbox completes within the operator's documented runbook time budget
  (a documented, tested procedure exists; success is "the runbook works
  end-to-end", not a specific minute value).
- **SC-004**: 95th-percentile latency of every existing entity read
  endpoint does not regress by more than 100 ms versus the pre-migration
  baseline measured on the same workload.
- **SC-005**: The full existing automated test suite (unit + integration
  + contract + lint) passes against Postgres in CI with no skipped or
  deleted tests beyond those that explicitly targeted SQLite internals.
- **SC-006**: Idle chat sessions older than the configured inactivity
  timeout are removed from the database within one TTL cycle (so the
  session table size in steady state reflects only active conversations).
- **SC-007**: Every database connection observed in monitoring uses TLS;
  any plaintext connection attempt is rejected.

## Assumptions

- The Azure Postgres server at `legion.postgres.database.azure.com` is
  reachable from both developer machines (via firewall allow-list or a
  dev credential) and from the deployed backend, and has enough capacity
  (storage, connections, IOPS) to host all entities plus chat sessions
  for the current scale described in [Deployment.md](Deployment.md)
  (≤100 concurrent caregivers, low write rate).
- The Azure-hosted Postgres provides managed point-in-time backups, TLS
  on the wire, and at-rest encryption out of the box; the operator does
  not need to build those primitives in application code.
- A database, a credential the backend can use, and a credential a
  developer can use are provisioned outside the scope of this feature
  (this spec consumes them; it does not create the Azure resource).
- All public API contracts (REST shapes, status codes, auth) stay the
  same; this feature is a storage swap, not an API redesign.
- Chat-session retention semantics already defined in earlier features
  (single in-process dict, ~24h idle timeout) remain the target
  behaviour; only the storage location changes.
- The frontend requires no behavioural changes for this feature; it
  continues to call the same endpoints with the same payloads.
- Developer test setup is allowed to use either the shared Azure server
  with a per-developer/test schema OR an ephemeral local Postgres
  (e.g. a container), whichever the implementing plan prefers.
- Anything not listed as an entity above (e.g. blob attachments, audit
  logs) is out of scope for this feature.
