# Phase 1 Data Model: User & Baby Profiles with Authentication

**Feature**: 006-user-and-baby-profiles
**Date**: 2026-05-21
**Storage**: SQLite (`backend/momdiary.db`) via SQLAlchemy 2.x async + aiosqlite, schema-managed by Alembic.

All new and existing tables use:
- TEXT primary keys (`id`) populated as UUIDv7-or-equivalent application-generated strings (consistent with the existing schema).
- `created_at`, `updated_at` ISO-8601 UTC TEXT columns set by the application layer (consistent with existing rows).
- `deleted_at` ISO-8601 UTC TEXT column for soft delete, nullable. Reads MUST filter `deleted_at IS NULL` unless explicitly viewing archives.

---

## New entities

### `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | Application-generated. |
| `email` | TEXT | NOT NULL, UNIQUE (case-insensitive via collation NOCASE), indexed | The caregiver identifier (FR-001). Stored lower-cased on write. |
| `password_hash` | TEXT | NOT NULL | Full Argon2id PHC string. Never returned by any API. |
| `display_name` | TEXT | NOT NULL | The Caregiver Profile display name (FR-020). |
| `active_baby_id` | TEXT | NULL, FK → `babies.id` ON DELETE SET NULL | Restored on next sign-in (FR-011). |
| `created_at` | TEXT | NOT NULL | |
| `updated_at` | TEXT | NOT NULL | |
| `deleted_at` | TEXT | NULL | Soft-delete on account closure (out of scope for v1 but column present). |

**Indexes**: `UNIQUE INDEX ix_users_email_lower ON users (email COLLATE NOCASE)`.

**Validation rules**:
- `email` MUST match a permissive RFC-5321-ish regex (`^[^@\s]+@[^@\s]+\.[^@\s]+$`) and ≤ 254 chars.
- `display_name` ≥ 1 and ≤ 80 chars after trim; trim on write.
- `password` input (pre-hash) ≥ 8 chars and ≤ 256 chars; no other strength rule in v1.

---

### `user_sessions`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | Application-generated; this is what the cookie carries. Treat as a bearer secret. |
| `user_id` | TEXT | NOT NULL, FK → `users.id` ON DELETE CASCADE, indexed | |
| `created_at` | TEXT | NOT NULL | Issuance time. |
| `expires_at` | TEXT | NOT NULL | Rolling: set to `now() + 30d` on every authenticated request (FR-003). |
| `last_seen_at` | TEXT | NOT NULL | Observability + diagnostics. |
| `revoked_at` | TEXT | NULL | Set on explicit sign-out; revoked sessions MUST NOT authenticate. |
| `user_agent` | TEXT | NULL | Captured at issuance only. |

**Indexes**: `INDEX ix_user_sessions_user_id ON user_sessions (user_id)`, `INDEX ix_user_sessions_expires_at ON user_sessions (expires_at)`.

**Lifecycle**:
- `POST /v1/auth/login` → INSERT row, set cookie.
- Any authenticated request → UPDATE `expires_at = now() + 30d`, `last_seen_at = now()`.
- `POST /v1/auth/logout` → UPDATE `revoked_at = now()`, delete cookie.
- A background sweep MAY DELETE rows where `revoked_at IS NOT NULL OR expires_at < now() - 7d`; not required for correctness.

---

### `babies`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | |
| `owner_user_id` | TEXT | NOT NULL, FK → `users.id` ON DELETE RESTRICT, indexed | Single-owner per FR-019. |
| `display_name` | TEXT | NOT NULL | |
| `date_of_birth` | TEXT | NOT NULL | ISO-8601 date (`YYYY-MM-DD`). |
| `color_tag` | TEXT | NULL | Optional decoration (e.g., `"indigo"`); free-form short string ≤ 16 chars. |
| `created_at` | TEXT | NOT NULL | |
| `updated_at` | TEXT | NOT NULL | |
| `deleted_at` | TEXT | NULL | Soft-delete per FR-013. |

**Indexes**: `INDEX ix_babies_owner ON babies (owner_user_id, deleted_at)`.

**Validation rules**:
- `display_name` ≥ 1 and ≤ 80 chars after trim.
- `date_of_birth` MUST parse as a calendar date and MUST NOT be in the future.

---

## Modified entities (existing diary tables)

For each of `feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`, `agent_interactions`:

**Add column**:

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `baby_id` | TEXT | NOT NULL, FK → `babies.id` ON DELETE RESTRICT | Set on every write to the active baby of the authenticated caregiver. |

**Add indexes** (one per table, tuned to the table's primary time column):
- `feeds`: `INDEX ix_feeds_baby_occurred ON feeds (baby_id, occurred_at, deleted_at)`
- `sleeps`: `INDEX ix_sleeps_baby_start ON sleeps (baby_id, start_at, deleted_at)`
- `poops`: `INDEX ix_poops_baby_occurred ON poops (baby_id, occurred_at, deleted_at)`
- `appointments`: `INDEX ix_appointments_baby_scheduled ON appointments (baby_id, scheduled_at, deleted_at)`
- `appointment_notes`: inherits scoping from parent appointment; still gets `INDEX ix_appointment_notes_baby ON appointment_notes (baby_id)` for direct queries.
- `agent_interactions`: `INDEX ix_agent_interactions_baby ON agent_interactions (baby_id, created_at)`.

**Migration step** (per FR-018): hard-delete all existing rows from these tables **before** adding the new `NOT NULL` column.

**Settings table** (`settings`): not modified — remains process-global (e.g., time-zone). If per-baby settings are needed later, that is a follow-up feature.

---

## Relationships diagram (textual)

```
users (1) ─┬─< user_sessions
           ├─< babies                  (1 user → 0..N babies)
           └─→ active_baby_id ──→ babies (nullable preference)

babies (1) ─┬─< feeds
            ├─< sleeps
            ├─< poops
            ├─< appointments ─< appointment_notes
            └─< agent_interactions
```

---

## State transitions

### User session

```
[issued] ──(authenticated request)──> [issued, expires_at slid]
   │
   ├──(explicit sign-out)──> [revoked]            ──> rejected on any future use
   └──(expires_at < now)───> [expired]             ──> rejected; client redirected to /login
```

### Baby

```
[active] ──(PATCH /v1/babies/{id})──> [active, edited]
   │
   └──(DELETE /v1/babies/{id})──> [soft-deleted: deleted_at set]
                                    │
                                    └─ if this was users.active_baby_id, user.active_baby_id ← (most-recent surviving baby) OR NULL (FR-011)
```

---

## Authorization invariants (enforced everywhere)

1. **Caregiver ownership**: every read or write on `babies` MUST require `babies.owner_user_id = current_user.id AND babies.deleted_at IS NULL`. Violations return 404 (never 403) to avoid leaking existence.
2. **Diary scoping**: every read or write on `feeds`/`sleeps`/`poops`/`appointments`/`appointment_notes`/`agent_interactions` MUST require:
   - The row's `baby_id` is owned by the current user (`JOIN babies ON ... WHERE babies.owner_user_id = current_user.id`).
   - The row's `baby_id` matches the request's resolved active baby (header `X-Active-Baby-Id` or `users.active_baby_id`).
3. **Chat session partitioning**: in-memory `SessionStore` keys are `(user_id, baby_id, session_id)`; a session may not be looked up without all three components.
