# Implementation Plan: Per-User Timezone

**Branch**: `007-user-timezone` | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

## Summary

Move timezone resolution from the global `settings.default_timezone` row to a per-user `users.timezone` column, populated automatically from the browser at registration and refreshed on login if it drifts. Every date-window computation (the four `list_by_date` repository calls plus the agent's `Current local time:` injection) is rewired to take a user-scoped timezone, falling back to the system default only when the user's value is NULL. No new endpoints, no new packages, one Alembic migration, no breaking client changes — the frontend just gains a `timezone` field on the register/login payloads.

## Design choice — why per-user, not per-request

Three options were considered:

| Approach | Pros | Cons |
|---|---|---|
| **Per-user** (chosen) | Persistent across devices; predictable; one source of truth; easy to debug ("what TZ is this user in?") | Requires a small schema change + migration |
| Per-request via `X-Client-Timezone` header | No schema change | Every endpoint must accept/validate it; "today" silently shifts when travelling, which most users don't want; the agent prompt also needs it threaded through |
| Per-baby | Supports siblings in different TZs | Vanishingly rare; complicates the data model for a non-need; the user is the right ownership boundary in v1 |

Per-user matches the existing data model (everything else is already scoped to `user_id` / `active_baby_id`) and gives a stable mental model: "the user's timezone is whatever they registered with, optionally re-detected on login."

## Data model change

Single new column on the existing `users` table:

```python
timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- Nullable, so the migration does not require a backfill.
- Stored as the raw IANA string (e.g. `Asia/Kolkata`). No FK, no enum — `zoneinfo` validates on read.
- Soft-validated at write time: the backend tries `ZoneInfo(value)`; on `ZoneInfoNotFoundError`, the field is left as-is on the row (i.e., the write is rejected silently per FR-008).

No index needed — timezone is read with every authenticated request but only via the `users` row that's already loaded by the auth dependency.

### Alembic migration

One revision: `20260530_add_users_timezone.py`.

- `op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))`
- No backfill — the pre-feature test account is being deleted from the dev DB before implementation, so the migration starts against zero user rows.
- Down migration: `op.drop_column("users", "timezone")`.

## API changes

### `POST /v1/auth/register` — request body gains `timezone`

```diff
 class RegisterRequest(_StrictModel):
     email: EmailStr
     password: PasswordStr
     display_name: DisplayNameStr
+    timezone: str | None = None   # IANA zone, e.g. "Asia/Kolkata"
```

If present and parseable by `ZoneInfo`, it's stored on the new user row.

### `POST /v1/auth/login` — request body gains `timezone`

```diff
 class LoginRequest(_StrictModel):
     email: EmailStr
     password: PasswordStr
+    timezone: str | None = None
```

If present, valid, and differs from `users.timezone` (or stored value is NULL), the backend performs a single `UPDATE users SET timezone=? WHERE id=?` *after* the password check succeeds. Pre-auth or invalid TZ is a no-op.

### `GET /v1/auth/me` — response gains `timezone`

```diff
 class UserPublic(_StrictModel):
     id: int
     email: EmailStr
     display_name: str
     active_baby_id: int | None = None
+    timezone: str | None = None
```

This is the existing user-info response used by `useSession()` on the frontend; adding a nullable field is a non-breaking change for any consumer (the frontend's zod schema needs the optional field added).

### No other endpoint contracts change

The `GET /v1/{feeds,sleeps,poops,appointments}?date=...` endpoints continue to take a date string. The change is purely in *how* the backend computes the window for that date — it now uses the authenticated user's timezone instead of the global default.

## Backend code changes

### New helper in `services/time_service.py`

```python
async def get_user_timezone(
    session: AsyncSession, user: User
) -> ZoneInfo:
    """Return the caregiver's IANA timezone; fall back to system default."""
    if user.timezone:
        try:
            return ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            logger.warning("user.timezone.invalid", user_id=user.id, value=user.timezone)
    return await get_default_timezone(session)
```

The existing `get_default_timezone` stays — it's used by the few places that have no authenticated user (e.g. the chat-session-store eviction loop's logs, if any) and as the fallback above.

### Repositories — pass the timezone in, not pull it from settings

`FeedsRepository.list_by_date`, and its three siblings (`SleepsRepository`, `PoopsRepository`, `AppointmentsRepository`), currently call `await get_default_timezone(self._session)` inside the repo. We invert that: the **caller** (the API layer, which already has the authenticated user) resolves the TZ and passes it in.

```diff
-async def list_by_date(self, d: date) -> list[Feed]:
-    tz = await get_default_timezone(self._session)
+async def list_by_date(self, d: date, tz: ZoneInfo) -> list[Feed]:
     start, end = date_window_in_tz(d, tz)
     ...
```

In `api/feeds.py` (and siblings):

```diff
-    rows = await FeedsRepository(session).list_by_date(date)
+    tz = await get_user_timezone(session, auth.user)
+    rows = await FeedsRepository(session).list_by_date(date, tz)
```

Same pattern for `list_sleeps`, `list_poops`, `list_appointments`. ~4 files, ~3 lines each.

### Agent context — use the caller's user

`maf_runner._format_context` currently calls `get_default_timezone`. It needs to accept a `User` (or just the resolved `ZoneInfo`) and use it for the `Current local time:` line. The dispatcher already has the user in scope (the auth dependency runs before the dispatcher), so we thread it through one parameter.

```diff
-async def _format_context(
-    session: AsyncSession, entry_id, entry_type
-) -> str:
-    tz = await get_default_timezone(session)
+async def _format_context(
+    session: AsyncSession, user: User, entry_id, entry_type
+) -> str:
+    tz = await get_user_timezone(session, user)
```

`MAFAgentRunner.run` gains a `user: User` keyword arg and passes it down. The two call sites (`POST /v1/entries`, `PUT /v1/entries`) already have `auth.user` available.

### Agent **read** tools (`list_*`)

`tools/reads.py`'s `list_feeds_for_date` etc. also use the global timezone. These are invoked by the agent during a chat turn, so they need the caller's TZ too. Since tools run with `session: AsyncSession` as their only contextvar-free parameter, the cleanest fix is to stash the active user's TZ on a contextvar (similar to how `active_baby_id` is stashed today in [`auth/context.py`](../../backend/src/momdiary/auth/context.py)) and have the read tools read it. One new contextvar: `active_user_timezone`.

The auth dependency that already sets `active_baby_id` would also set `active_user_timezone` per request.

### Frontend changes

Two minimal edits, both in [`frontend/src/features/auth/`](../../frontend/src/features/auth/):

1. **`useSession.ts`** — extend the zod schema for the `me` and login/register responses to include `timezone: z.string().nullable().optional()`.
2. **`LoginPage.tsx` / `SignupPage.tsx`** — when the form is submitted, attach the browser's detected zone to the POST body:
   ```ts
   timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
   ```

No new pages, no new UI affordances. The Settings UI to manually edit the TZ is out of scope (see spec.md §Out of Scope).

## Testing

- **Backend unit**: new tests in `tests/unit/test_time_service.py`:
  - `get_user_timezone` returns user's TZ when set
  - falls back to system default when NULL
  - falls back to system default and logs a warning when invalid
- **Backend integration**: extend `tests/integration/test_auth_endpoints.py`:
  - register with `timezone="Asia/Kolkata"` → `me` returns it
  - register without timezone → `me` returns null
  - login with a different timezone than stored → stored value updates
  - login with the same timezone → no DB write (assert via a session.commit spy, or by checking `updated_at` unchanged)
- **Backend integration**: extend `tests/integration/test_feeds.py`:
  - user with `timezone="Asia/Kolkata"` logs a feed at 01:00 IST on day D → `GET /v1/feeds?date=D` returns it
  - user with `timezone IS NULL` falls back to system default behaviour identical to the pre-feature behaviour
- **Frontend**: `vitest` mocks `Intl.DateTimeFormat` to assert the register/login payloads include `timezone`.

No new contract test file — the OpenAPI changes are additive optional fields.

## Migration & rollout

1. Wipe the pre-feature test account from the dev DB **before** merging (a clean slate — we'll re-register through the new flow after the code ships).
2. Merge the migration alongside the code.
3. `alembic upgrade head` is the only runtime step.
4. Re-register through the frontend — the browser auto-detects the timezone and ships it in the register payload, so the new user row has `timezone` populated from the first request.

## Constitution Check

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Code Quality & Maintainability | **Pass** | One new helper, one new column, one new contextvar. No new modules. |
| II | Testing Standards | **Pass** | Unit + integration coverage described above; no contract test churn since OpenAPI changes are additive. |
| III | Performance | **Pass** | Adds at most one column read per request (already inside the user row that auth loads) and at most one `UPDATE` per login when the TZ actually changed. No measurable impact on p95. |
| IV | Modular Architecture | **Pass** | Keeps `time_service` as the single source of TZ logic; adds one helper alongside the existing `get_default_timezone`. The agent-context contextvar follows the existing `active_baby_id` pattern. |
| V | MAF First | **N/A** | Agent contract (tools, system prompt invariants) unchanged. Only the injected "Current local time:" prefix becomes user-aware. |

## Resolved decisions (locked before implementation)

1. **Settings UI to manually edit TZ?** Deferred. Auto-detection at signup + login-time refresh covers v1. A manual override is a future one-line PATCH against `/v1/users/me`.
2. **On login with a different browser TZ, silently update or prompt?** Silently update — no UI noise, no confirmation dialog. The `UPDATE` runs only when the supplied zone is valid (parseable by `ZoneInfo`) and differs from the stored value.

## Estimated effort

- Backend: ~2–3 hours (migration, 4 repos, 1 helper, 1 contextvar, agent context, 2 schema diffs, tests).
- Frontend: ~30 min (2 form fields, 1 zod field).
- Total: under half a day of focused work.
