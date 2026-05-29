# Phase 1 Data Model: Clerk-Powered Caregiver Authentication

**Feature**: 008-clerk-auth
**Date**: 2026-05-27
**Migration**: `2026XXXX_008_clerk_users.py` (single revision)

This feature changes only the identity layer. Diary entry shapes
(`feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`,
`agent_interactions`) are **unchanged** in column shape — they retain the
`baby_id NOT NULL` FK introduced in feature 006. What changes is the contents
of `users` and the disappearance of `user_sessions`.

---

## 1. Tables affected

### 1.1 `users` (MODIFIED)

| Column | Before (feature 006) | After (this feature) | Notes |
|---|---|---|---|
| `id` | `UUID PRIMARY KEY` | **unchanged** | Internal stable caregiver ID. Still the FK target from `babies.user_id`. |
| `email` | `TEXT NOT NULL UNIQUE` | **unchanged** | Mirrored from Clerk on each sign-in / on `user.updated` webhook. |
| `password_hash` | `TEXT NOT NULL` | **DROPPED** | Clerk owns credential material. |
| `password_updated_at` | `TIMESTAMP NOT NULL` | **DROPPED** | Same. |
| `email_verified_at` | (not present) | `TIMESTAMP NULL` (**NEW**) | Mirrored from Clerk. `NULL` means unverified. Drives FR-017 fallback only; the request-time gate reads the JWT claim. |
| `clerk_user_id` | (not present) | `TEXT NOT NULL UNIQUE` (**NEW**) | Stable Clerk identifier (`sub` claim). Source of truth per FR-006. |
| `created_at` | `TIMESTAMP NOT NULL` | **unchanged** | Set on lazy-provision. |
| `updated_at` | `TIMESTAMP NOT NULL` | **unchanged** | Touched on email or verification mirror updates. |

**Indexes after migration**:

- `PRIMARY KEY (id)` — unchanged
- `UNIQUE (email)` — kept (one MomDiary row per email; FR-007)
- `UNIQUE (clerk_user_id)` — new (one MomDiary row per Clerk identity; FR-005, FR-006)

### 1.2 `user_sessions` (DROPPED)

The entire table is removed by the migration. Clerk owns sessions. The
backend stores no session state, so there is nothing to manage on sign-out
(FR-004 is a frontend concern: `signOut()` from `@clerk/clerk-react`).

### 1.3 `babies` (UNCHANGED in shape)

| Column | Status | Notes |
|---|---|---|
| `id`, `user_id`, `name`, `birth_date`, `created_at`, `updated_at` | unchanged | `user_id` still FKs to `users.id`. |

The `user_id → users.id` FK relationship is preserved, which means the
account-deletion cascade chain (entries → babies → user) continues to work
unchanged once the webhook initiates the delete.

### 1.4 Every diary table (UNCHANGED in shape)

`feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`,
`agent_interactions`: column-for-column unchanged. The `baby_id NOT NULL`
FK and the per-table `(baby_id, occurred_at)` composite indexes from feature
006 are all preserved.

---

## 2. Data reset at migration (FR-012)

The migration's upgrade step, in order:

1. `DELETE FROM appointment_notes;`
2. `DELETE FROM appointments;`
3. `DELETE FROM poops;`
4. `DELETE FROM sleeps;`
5. `DELETE FROM feeds;`
6. `DELETE FROM agent_interactions;` (if present)
7. `DELETE FROM babies;`
8. `DELETE FROM users;`
9. `DROP TABLE user_sessions;`
10. `ALTER TABLE users DROP COLUMN password_hash;`
11. `ALTER TABLE users DROP COLUMN password_updated_at;`
12. `ALTER TABLE users ADD COLUMN clerk_user_id TEXT NOT NULL;`
    *(safe because the table is empty after step 8)*
13. `ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP NULL;`
14. `CREATE UNIQUE INDEX uq_users_clerk_user_id ON users (clerk_user_id);`

SQLite does not natively support `DROP COLUMN` on older versions; Alembic's
batch-mode (`with op.batch_alter_table('users') as batch_op:`) is used to
emit the necessary table-rebuild. The migration is irreversible (no
downgrade beyond raising `NotImplementedError`), consistent with the
"discard pre-existing data" decision.

---

## 3. Lazy provisioning of `users` rows

On every authenticated request, `get_current_user` does:

1. Verify the JWT (signature, `iss`, `aud`, `exp`, `nbf`).
2. Extract `sub` (Clerk user ID), `email`, `email_verified`.
3. `SELECT * FROM users WHERE clerk_user_id = :sub;`
4. If found and `email`/`email_verified_at` differ, `UPDATE` to mirror.
5. If not found:
   - `INSERT INTO users (id, clerk_user_id, email, email_verified_at, created_at, updated_at) VALUES (uuid4(), :sub, :email, :verified_at, now(), now());`
   - `:verified_at` is `now()` when the JWT claim is `true`, else `NULL`.
   - Conflict on `(email)` → return `409` and log `email_conflict` (should
     not happen in practice because `clerk_user_id` is unique and we have
     just exhausted that path; if it does, this is a Clerk-side identity
     fork we surface explicitly).
6. Return a typed `CurrentUser(id=..., clerk_user_id=..., email=..., email_verified=...)`.

This satisfies FR-005 (lazy provision on first sign-in), FR-006 (Clerk ID
is the stable FK), FR-007 (one MomDiary row per Clerk identity even with
multiple verified emails).

---

## 4. Account-deletion cascade (FR-015, FR-016)

Initiated by `POST /v1/webhooks/clerk` receiving a `user.deleted` event.

After Svix signature verification and parsing the `data.id` (Clerk user ID),
inside a single SQLAlchemy transaction:

1. `SELECT id FROM users WHERE clerk_user_id = :clerk_id;` — call it `:user_id`.
2. If no row, return `200` (idempotent; FR-015 "repeated deletion signals are safe").
3. `SELECT id FROM babies WHERE user_id = :user_id;` — call it `:baby_ids[]`.
4. `DELETE FROM appointment_notes WHERE appointment_id IN (SELECT id FROM appointments WHERE baby_id IN :baby_ids);`
5. `DELETE FROM appointments WHERE baby_id IN :baby_ids;`
6. `DELETE FROM poops WHERE baby_id IN :baby_ids;`
7. `DELETE FROM sleeps WHERE baby_id IN :baby_ids;`
8. `DELETE FROM feeds WHERE baby_id IN :baby_ids;`
9. `DELETE FROM agent_interactions WHERE baby_id IN :baby_ids;`
10. `DELETE FROM babies WHERE user_id = :user_id;`
11. `DELETE FROM users WHERE id = :user_id;`
12. `COMMIT;`
13. Also: evict every entry from the in-memory chat session store whose key
    starts with `(:user_id, ...)`. Implemented as a single `purge_user`
    method on `ChatSessionStore`.

All operations are hard deletes with no soft-delete column anywhere
(FR-015: "irrecoverable — no soft-delete column, no archive table").

---

## 5. In-memory chat session store impact

`ChatSessionStore` (feature 003) keys entries by `(user_id, baby_id, session_id)`.
This feature does NOT change the key shape, but `user_id` now refers to the
internal UUID resolved from Clerk's `sub` claim instead of the
locally-issued caregiver UUID. The store is bounded (TTL / max_turns /
max_sessions / message_max_bytes / prompt_token_budget) and is purged for a
caregiver on cascade delete (§4 step 13).

---

## 6. Invariants

- **I1**: Every `users.clerk_user_id` is non-null and unique. *(Enforced by
  schema; checked in integration test.)*
- **I2**: Every `users.email` is non-null and unique. *(Enforced by schema.)*
- **I3**: Every protected request resolves to exactly one `users.id`
  before reaching any business logic. *(Enforced by `get_current_user`
  dependency.)*
- **I4**: No write endpoint executes when the resolved user's
  `email_verified` JWT claim is `false`. *(Enforced by
  `require_verified_email` dependency.)*
- **I5**: After a `user.deleted` webhook for Clerk user `X`, no row in
  `users`, `babies`, or any diary table references `X` (directly or via the
  baby chain), AND no chat session in the store is keyed by the former
  internal `user_id`. *(Enforced by §4, verified in
  `test_webhook_user_deleted_cascade.py`.)*
- **I6**: No Clerk-issued JWT, password material, or Google access token
  appears in any application log line. *(Enforced by a CI log-scan, SC-005.)*
