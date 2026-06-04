# Implementation Plan: Per-User Timezone (Clerk base)

**Branch**: `per-user-timezone` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Add a `timezone` column to `users`, capture the browser's zone via `PATCH /v1/users/me` right after Clerk sign-in (refreshing on drift), and resolve that per-user zone everywhere date windows are computed. Because the Clerk `get_current_user` dependency runs on **every** authenticated request (list endpoints reach it via `ActiveBabyDep`; `/v1/entries` depends on it directly), we set a per-request **timezone contextvar** there once, and every consumer — the four `list_by_date` repositories, the agent's read tools, and the `Current local time:` prefix — reads it through a single `get_request_timezone(session)` helper that falls back to the system default. One Alembic migration (`0004`), no new packages, no change to Clerk auth or the agent contract.

This is the feature-007-timezone work re-targeted onto the Clerk codebase, with a **simplification** (decided 2026-06-03): the original explicit `tz`-parameter threading through routers and repos is replaced by the contextvar-everywhere approach. Net result: **no API-router changes and no repository signature changes** — each consumer swaps its one `get_default_timezone(...)` call for `get_request_timezone(...)`. Smaller, safer diff; zero test churn (verified: no test calls the repos directly).

## Backend changes

### Data model + migration
- [`models/orm.py`](../../backend/src/momdiary/models/orm.py) — `User`: add `timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)`.
- New revision `backend/alembic/versions/0004_users_timezone.py` (down_revision `0003`): `op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))`; downgrade drops it. No backfill (DB wiped).

### Timezone resolution helpers
- [`services/time_service.py`](../../backend/src/momdiary/services/time_service.py) — add two helpers (keep `get_default_timezone` as the fallback):
  - `parse_zoneinfo_or_none(name: str | None) -> ZoneInfo | None` — returns `ZoneInfo(name)` if valid, else `None` (logs `user.timezone.invalid` on a bad string). Reused by `get_current_user` and the `PATCH /users/me` validation.
  - `get_request_timezone(session) -> ZoneInfo` — `get_active_user_timezone() or await get_default_timezone(session)`. **This is the single resolver every consumer calls.**

### Per-request contextvar
- [`auth/context.py`](../../backend/src/momdiary/auth/context.py) — add `_active_user_timezone: ContextVar[ZoneInfo | None]` + `set_active_user_timezone` / `get_active_user_timezone`, mirroring the existing `_active_baby_id` pattern.
- [`auth/dependencies.py`](../../backend/src/momdiary/auth/dependencies.py) — in `get_current_user`, after the local user row is resolved/provisioned, `set_active_user_timezone(parse_zoneinfo_or_none(user.timezone))`. Runs on every authed request, so the contextvar is populated for both REST and agent paths.

### Repositories — swap one call (no signature change)
- `db/repositories/{feeds,poops,appointments}.py` and `sleeps.py`: inside `list_by_date` / `list_by_start_date`, replace `tz = await get_default_timezone(self._session)` with `tz = await get_request_timezone(self._session)`. **Signatures unchanged.** (`date_window_in_tz(d, tz)` already takes the zone.)

### API routers — UNCHANGED
- `api/{feeds,sleeps,poops,appointments}.py`: no edits. They still depend on `ActiveBabyDep` (which runs `get_current_user` underneath, populating the contextvar before the repo call).

### Agent — swap one call
- [`agents/tools/reads.py`](../../backend/src/momdiary/agents/tools/reads.py) — `_resolve_date` and each `list_*` tool: use `await get_request_timezone(session)` instead of `get_default_timezone(session)`. (Repos resolve their own tz internally now, so the tools just need the right "today".)
- [`agents/maf_runner.py`](../../backend/src/momdiary/agents/maf_runner.py) — `_format_context`: `tz = await get_request_timezone(session)` (was `get_default_timezone`). No signature change.

### Capture endpoint + schemas
- [`schemas/users.py`](../../backend/src/momdiary/schemas/users.py) — `UserUpdate`: make `display_name` **optional**, add optional `timezone: str | None` (≤64 chars).
- [`schemas/auth.py`](../../backend/src/momdiary/schemas/auth.py) — add `timezone: str | None = None` to `UserPublic` and `CurrentUserOut`.
- [`api/users.py`](../../backend/src/momdiary/api/users.py) — `_apply_profile_update`: **only** touch `display_name` when `payload.display_name is not None` (so a tz-only PATCH doesn't blank the name); when `payload.timezone` is present, valid (`parse_zoneinfo_or_none`), and ≠ stored, set `user.timezone` (silently ignore invalid per FR-002). Include `timezone` in `_public(...)` and `get_me`.

## Frontend changes

### Types + client
- [`shared/types.ts`](../../frontend/src/shared/types.ts) — add `timezone: z.string().nullable().optional()` to the `CurrentUser`/`UserPublic` schemas; add optional `timezone` to the `UserUpdate` schema.
- [`shared/time.ts`](../../frontend/src/shared/time.ts) — add `detectBrowserTimezone(): string | undefined` (`try { Intl.DateTimeFormat().resolvedOptions().timeZone } catch {}`).
- `apiClient.updateMe` already exists (used by `useUpdateProfileMutation`); no client change beyond the wider `UserUpdate` type.

### Post-sign-in capture effect
- After Clerk sign-in, once `useSession()` resolves the local user, compare `detectBrowserTimezone()` to `user.timezone`; if different, fire `apiClient.updateMe({ timezone })` once. Implement as a small effect/hook (e.g. in the signed-in branch of [`App.tsx`](../../frontend/src/App.tsx) or a dedicated `useTimezoneSync` hook) that runs when the session loads. Update the cached session on success (extend `useUpdateProfileMutation`'s `onSuccess` to also patch `timezone`).

## Testing / verification

Requires the Clerk app running (keys + `momdiary-default` JWT template) and a wiped+migrated DB.

1. `alembic upgrade head` (adds `users.timezone`).
2. Sign in via Clerk from an IST browser → confirm a `PATCH /v1/users/me` fires and `SELECT timezone FROM users` shows `Asia/Kolkata`.
3. Log a feed at "now" → appears under the correct local day in Feed History + Recent Activity; `GET /v1/feeds?date=<IST today>` returns it.
4. Drift test: `UPDATE users SET timezone='America/Los_Angeles'`, sign out/in → stored value flips back to the browser's zone.
5. NULL-fallback: `UPDATE users SET timezone=NULL`, hit a list endpoint → 200 via default (no 500).
6. (Agent, needs Azure) `/v1/entries` `Current local time:` reflects the user's zone.

## Constitution check

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Code Quality | Pass | One column, one helper, one contextvar; mirrors existing patterns. |
| II | Testing | Pass | Unit (`get_user_timezone` fallback/invalid), integration (PATCH stores TZ; list buckets to user zone; NULL fallback). |
| III | Performance | Pass | One column read inside the already-loaded user row; at most one extra PATCH per sign-in on drift. |
| IV | Modular Architecture | Pass | `time_service` stays the single TZ source; contextvar follows the `active_baby_id` precedent. |
| V | MAF First | N/A | Agent tools/prompt invariants unchanged; only the injected local-time line becomes user-aware. |

## Migration & PR notes

- This branches off the synced `main` (Clerk). Migration is `0004`, so **no collision** with upstream's `0003_clerk_users` (the collision that doomed the earlier branch).
- Target the PR at `sjha3/MomDiary:main` from `aryajh-a/MomDiary:per-user-timezone`.
- Unrelated: while reading the code we found the owner committed a real `CLERK_SECRET_KEY` in `frontend/.env.example` — worth a separate heads-up/issue to the owner (rotate the key); not part of this PR.

## Estimated effort
- Backend ~1.5–2 h (column+migration, 2 helpers, contextvar, 4 one-line repo swaps, 2 agent swaps, capture endpoint + schemas, tests). No router changes.
- Frontend ~45 min (types, `detectBrowserTimezone`, post-sign-in sync effect).

## Implementation order (step by step)
1. `users.timezone` column + migration `0004` → migrate.
2. `time_service` helpers (`parse_zoneinfo_or_none`, `get_request_timezone`) + `auth/context` contextvar.
3. Set the contextvar in `get_current_user`.
4. Swap the one resolver call in the 4 repos + `reads.py` + `maf_runner`.
5. Capture endpoint: `UserUpdate` + `_apply_profile_update` + `UserPublic`/`CurrentUserOut`.
6. Frontend: types, `detectBrowserTimezone`, post-sign-in sync effect.
7. Verify end-to-end (sign in from IST, log a feed, confirm bucketing).
