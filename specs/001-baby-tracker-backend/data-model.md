# Phase 1 Data Model: Baby Tracker Agentic Backend

**Feature**: 001-baby-tracker-backend
**Date**: 2026-05-16
**Storage**: SQLite (via SQLAlchemy 2.x async + Alembic migrations)

All timestamp columns store ISO-8601 strings with explicit offset
(SQLite `TEXT`), matching FR-012. All "soft-delete-capable" tables
include a nullable `deleted_at` column (FR-018). All entry tables
include a nullable `caregiver_id` column reserved for future
multi-user use (FR-016); v1 always stores `NULL`.

---

## Entities

### 1. `feeds`

Represents a single feeding event (FR-003).

| Column        | Type                     | Constraints                                    | Notes |
| ------------- | ------------------------ | ---------------------------------------------- | ----- |
| `id`          | `INTEGER`                | PRIMARY KEY AUTOINCREMENT                      | Surrogate id |
| `caregiver_id`| `TEXT`                   | NULL                                            | v1: always NULL (FR-016) |
| `feed_type`   | `TEXT`                   | NOT NULL, CHECK in (`breast_milk`, `formula`, `solids`, `water`) | Enum (FR-003) |
| `quantity`    | `REAL`                   | NOT NULL, > 0                                  | Normalized value |
| `unit`        | `TEXT`                   | NOT NULL, CHECK in (`ml`, `g`)                  | `oz` accepted on write, normalized to `ml` (FR-003) |
| `occurred_at` | `TEXT` (ISO-8601 + offset)| NOT NULL                                       | Timestamp of feeding |
| `deleted_at`  | `TEXT`                   | NULL                                            | Soft-delete (FR-018) |
| `created_at`  | `TEXT`                   | NOT NULL, default `CURRENT_TIMESTAMP`          | Audit |
| `updated_at`  | `TEXT`                   | NOT NULL, default `CURRENT_TIMESTAMP`          | Audit |

Indexes: `(deleted_at, occurred_at)` for date-scoped GET (FR-008).

Validation rules (FR-014):
- `quantity > 0`
- `occurred_at` ≤ now + 5 minutes (no future feeds beyond clock skew)

### 2. `sleeps`

A single sleep session (FR-004).

| Column        | Type     | Constraints                              | Notes |
| ------------- | -------- | ---------------------------------------- | ----- |
| `id`          | `INTEGER`| PK AUTOINCREMENT                         | |
| `caregiver_id`| `TEXT`   | NULL                                      | FR-016 |
| `start_at`    | `TEXT`   | NOT NULL                                  | ISO-8601 + offset |
| `end_at`      | `TEXT`   | NOT NULL, CHECK `end_at <> start_at`     | FR-004 |
| `deleted_at`  | `TEXT`   | NULL                                      | FR-018 |
| `created_at`  | `TEXT`   | NOT NULL                                  | |
| `updated_at`  | `TEXT`   | NOT NULL                                  | |

Derived (not stored): `duration_minutes = (end_at - start_at)`.

Indexes: `(deleted_at, start_at)`.

Sleep that spans midnight is filed under its `start_at` date (FR-009).

### 3. `poops`

A single diaper event (FR-005).

| Column        | Type     | Constraints                                                | Notes |
| ------------- | -------- | ---------------------------------------------------------- | ----- |
| `id`          | `INTEGER`| PK AUTOINCREMENT                                           | |
| `caregiver_id`| `TEXT`   | NULL                                                        | FR-016 |
| `occurred_at` | `TEXT`   | NOT NULL                                                    | |
| `consistency` | `TEXT`   | NOT NULL, CHECK in (`watery`, `soft`, `formed`, `hard`)    | Enum (FR-005) |
| `deleted_at`  | `TEXT`   | NULL                                                        | FR-018 |
| `created_at`  | `TEXT`   | NOT NULL                                                    | |
| `updated_at`  | `TEXT`   | NOT NULL                                                    | |

Indexes: `(deleted_at, occurred_at)`.

### 4. `appointments`

A doctor appointment, scheduled or past (FR-006).

| Column        | Type     | Constraints       | Notes |
| ------------- | -------- | ----------------- | ----- |
| `id`          | `INTEGER`| PK AUTOINCREMENT  | |
| `caregiver_id`| `TEXT`   | NULL              | FR-016 |
| `scheduled_at`| `TEXT`   | NOT NULL          | ISO-8601 + offset; future timestamps allowed (FR-014) |
| `deleted_at`  | `TEXT`   | NULL              | FR-018 |
| `created_at`  | `TEXT`   | NOT NULL          | |
| `updated_at`  | `TEXT`   | NOT NULL          | |

Indexes: `(deleted_at, scheduled_at)`.

### 5. `appointment_notes`

Zero-or-more notes per appointment (FR-006). Notes are append-only from the
user's perspective; updating an existing note's text is an admin-level
operation outside v1 scope.

| Column           | Type     | Constraints                                  | Notes |
| ---------------- | -------- | -------------------------------------------- | ----- |
| `id`             | `INTEGER`| PK AUTOINCREMENT                             | |
| `appointment_id` | `INTEGER`| NOT NULL, FK → `appointments(id)` ON DELETE CASCADE | |
| `body`           | `TEXT`   | NOT NULL, length 1..2000                     | |
| `added_at`       | `TEXT`   | NOT NULL                                     | |

Indexes: `(appointment_id, added_at)`.

Soft-deleting the parent appointment hides its notes from GETs by virtue of
the parent filter; notes themselves have no `deleted_at` in v1.

### 6. `agent_interactions` (operational)

Audit / observability record for each agent invocation (FR-013).

| Column            | Type     | Constraints                                                | Notes |
| ----------------- | -------- | ---------------------------------------------------------- | ----- |
| `id`              | `INTEGER`| PK AUTOINCREMENT                                           | |
| `correlation_id`  | `TEXT`   | NOT NULL                                                    | Mirrors HTTP request correlation id |
| `inbound_message` | `TEXT`   | NOT NULL                                                    | Raw user message |
| `selected_tool`   | `TEXT`   | NULL                                                        | e.g., `log_feed`, `update_sleep`, `delete_poop` |
| `entry_type`      | `TEXT`   | NULL                                                        | `feed` / `sleep` / `poop` / `appointment` |
| `entry_id`        | `INTEGER`| NULL                                                        | FK-free (the entry may live in any table) |
| `outcome`         | `TEXT`   | NOT NULL, CHECK in (`created`, `updated`, `deleted`, `clarification_requested`, `rejected`) | |
| `latency_ms`      | `INTEGER`| NOT NULL                                                    | Excludes model time |
| `model_latency_ms`| `INTEGER`| NULL                                                        | Reported separately (SC-002) |
| `created_at`      | `TEXT`   | NOT NULL                                                    | |

Indexes: `(correlation_id)`, `(created_at)`.

### 7. `settings` (singleton)

One row holding system-wide configuration (FR-012).

| Column              | Type     | Constraints           | Notes |
| ------------------- | -------- | --------------------- | ----- |
| `id`                | `INTEGER`| PK CHECK (`id = 1`)   | Singleton |
| `default_timezone`  | `TEXT`   | NOT NULL              | IANA zone; seeded from env on first run |
| `updated_at`        | `TEXT`   | NOT NULL              | |

---

## State transitions

### Entry lifecycle (feeds, sleeps, poops, appointments)

```text
            +--------+    update      +--------+
   create → | active | ─────────────► | active |
            +--------+                +--------+
                │                          │
                │  soft delete             │  soft delete
                ▼                          ▼
            +-----------+             +-----------+
            | deleted   |             | deleted   |
            +-----------+             +-----------+
```

- `active` → `deleted`: set `deleted_at = now`. Excluded from GETs (FR-008)
  and from agent target resolution for updates (FR-017) and further
  deletes (FR-018).
- `deleted` → `active`: not supported in v1 (no "undo" tool).
- Update on `deleted` row: forbidden; agent must ask for clarification.

### Appointment notes

- `appointment.deleted_at IS NULL` → notes are returned in GETs.
- `appointment.deleted_at IS NOT NULL` → notes are hidden (parent gated).
- Notes are never independently soft-deleted in v1.

### Agent interactions

Insert-only. Never updated, never deleted.

---

## Relationships

```text
appointments ──< appointment_notes      (1..N, cascade on hard delete only)
agent_interactions  →  (feeds | sleeps | poops | appointments)   (logical, no FK)
settings (singleton)
```

No cyclic dependencies (Principle IV).

---

## Mapping to functional requirements

| FR     | Where enforced |
| ------ | -------------- |
| FR-003 | `feeds.feed_type`, `feeds.quantity`, `feeds.unit`, `feeds.occurred_at` |
| FR-004 | `sleeps.start_at`, `sleeps.end_at`, CHECK `end_at <> start_at` |
| FR-005 | `poops.consistency` CHECK in vocabulary |
| FR-006 | `appointments` + `appointment_notes` 1..N |
| FR-007 | All entry tables persist to SQLite via SQLAlchemy/Alembic |
| FR-008 | `(deleted_at, occurred_at|start_at|scheduled_at)` indexes; repo filters `deleted_at IS NULL` |
| FR-009 | GET filter uses `start_at` date for sleeps |
| FR-012 | All timestamp columns store offset; `settings.default_timezone` configures interpretation |
| FR-013 | `agent_interactions` row per invocation |
| FR-014 | CHECK constraints + repository-level validation |
| FR-015 | Repository PUT compares canonical payload; skips no-op writes |
| FR-016 | Nullable `caregiver_id` on every entry table |
| FR-017 | Enforced in service layer, not schema |
| FR-018 | `deleted_at` columns + repository soft-delete |
| FR-019 | No retention job; nothing in schema enforces purge |
