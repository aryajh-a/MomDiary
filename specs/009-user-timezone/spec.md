# Feature Specification: Per-User Timezone (on the Clerk auth base)

**Feature Branch**: `per-user-timezone`
**Created**: 2026-06-02
**Status**: Draft (for review)
**Input**: User description: "The timezone is currently hardcoded to LA. I want the app to take the timezone from the user's timezone." — re-targeted onto the current `main`, which now uses Clerk authentication (features 007 profile-management + 008 clerk-auth are merged upstream).

## Problem Statement

Every date-windowed query in the backend (`GET /v1/{feeds,sleeps,poops,appointments}?date=YYYY-MM-DD`, plus the agent's `list_*` tools) computes the `[start, end)` UTC window for a local calendar date using a **single global timezone** stored in the singleton `settings` row (default `America/Los_Angeles`; see [`time_service.get_default_timezone`](../../backend/src/momdiary/services/time_service.py) and `date_window_in_tz`). The same global TZ is injected into the agent's `Current local time:` prefix ([`maf_runner._format_context`](../../backend/src/momdiary/agents/maf_runner.py)).

This is wrong for any caregiver outside the configured zone. Observed bug: a caregiver in IST (UTC+5:30) logs a feed at ~01:30 IST; it is stored correctly at ~20:00 UTC the previous day, but the LA-configured window for "today" excludes it, so Feed History and Recent Activity show "no entries today."

The fix scopes the timezone to the **caregiver** (the Clerk-authenticated local `users` row), so each person sees their own day boundaries everywhere — list endpoints, the home dashboard, and the chat agent — without server reconfiguration.

## Clarifications

### Session 2026-06-02 (carried over from the earlier build, re-confirmed for the Clerk base)

- Q: Per-user, per-baby, or per-request timezone? → **A: Per-user.** The Clerk-authenticated local user is the natural ownership boundary; everything else already scopes to `user_id` / `active_baby_id`.
- Q: How is the timezone first captured, now that `/login` + `/register` are gone? → **A: Via `PATCH /v1/users/me`.** The frontend auto-detects the browser zone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) and PATCHes it right after Clerk sign-in (once the local user is provisioned). JIT-created rows start `timezone = NULL` and fall back to the system default until that PATCH lands.
- Q: On a later sign-in from a browser whose zone differs from the stored value? → **A: Silently update.** The post-sign-in effect PATCHes whenever the detected zone differs from the stored one. No prompt.
- Q: Manual settings UI to edit the timezone? → **A: Defer.** Auto-detect + drift-refresh covers v1. A manual control can be added later to the existing Profile page (`CaregiverCard`) as a one-line extension of the same `PATCH /users/me`.
- Q: Existing users? → **A: None.** The dev DB is wiped and re-migrated against the Clerk schema; everyone re-registers through Clerk.

## Behavior of historical entries when the timezone changes

Every diary timestamp (`occurred_at`, `start_at`, `end_at`, `scheduled_at`) is stored as an **absolute UTC moment**. Changing a user's timezone does **not** rewrite any row. Only the *interpretation* changes:

1. The stored UTC instant is unchanged.
2. The calendar date an entry is **bucketed** under may shift (a `list_by_date` query now computes its window in the new zone) — correct, because "today" is observer-relative.
3. The displayed wall-clock time shifts — but note the frontend already renders timestamps in the **browser's** zone via `parseISO()/format()`, so display was never the bug; the **date bucketing** (backend) was.

Worked example: a feed at "10:00 PM May 29 LA" is stored `2026-05-30T05:00:00+00:00`. Under LA it buckets to May 29; under IST it buckets to May 30 and `GET /v1/feeds?date=2026-05-30` returns it. Same instant, different bucket. This is the intended, truthful behavior.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — New caregiver sees their own "today" (Priority: P1)

A caregiver signs up through Clerk from a browser in `Asia/Kolkata`. After the app provisions their local user and the post-sign-in effect stores their timezone, logging a feed at 01:00 their local time shows it under "today" in Feed History and Recent Activity.

**Why this priority**: This is the bug. Without it the app hides data for any caregiver not in the backend's configured zone.

**Independent Test**: A caregiver in a non-LA zone signs in via Clerk, logs a feed at a past-but-near-now time via the Feed History `+` modal, and sees it in the same day's history and on the dashboard.

**Acceptance Scenarios**:

1. **Given** a caregiver signing in via Clerk from `Asia/Kolkata`, **When** the app loads their session and runs the post-sign-in timezone effect, **Then** their `users.timezone` becomes `Asia/Kolkata` (via `PATCH /v1/users/me`).
2. **Given** that caregiver, **When** they log a feed at `2026-06-02T01:00:00+05:30`, **Then** `GET /v1/feeds?date=2026-06-02` returns the entry.
3. **Given** that caregiver on the home dashboard at 01:30 IST, **When** Recent Activity renders, **Then** it shows entries for IST's June 2, not LA's June 1.
4. **Given** that caregiver, **When** they send a chat message via `/v1/entries`, **Then** the agent's injected `Current local time:` reflects their timezone.

---

### User Story 2 — Timezone refreshes when the browser zone changes (Priority: P2)

A caregiver who set up in one zone later uses the app from another. On sign-in the app detects the mismatch and updates the stored zone.

**Why this priority**: Handles travel / device switches. Not blocking the core bug.

**Independent Test**: A caregiver whose `users.timezone` is `America/Los_Angeles` signs in from a browser reporting `Asia/Kolkata`; afterwards `GET /v1/users/me` returns `timezone: "Asia/Kolkata"` and list windows use IST.

**Acceptance Scenarios**:

1. **Given** a stored timezone of `America/Los_Angeles`, **When** the user signs in from a browser sending `Asia/Kolkata`, **Then** the post-sign-in effect PATCHes and the stored value updates.
2. **Given** a stored timezone equal to the browser's, **When** the user signs in, **Then** no PATCH is sent (no redundant write).

---

### User Story 3 — Existing baby scoping and agent flow keep working (Priority: P1)

Per-baby data isolation, `active_baby_id`, and the chat agent all keep working, now resolving timezone from the Clerk-authenticated user.

**Independent Test**: Two Clerk users each see only their own active baby's entries; each user's timezone governs their own day windows and agent prompt.

**Acceptance Scenarios**:

1. **Given** two Clerk caregivers A and B, **When** both list feeds, **Then** each sees only their active baby's entries (no leakage), each under their own zone's day boundaries.
2. **Given** a caregiver whose `users.timezone IS NULL`, **When** any list endpoint is called, **Then** it responds 200 using the system-default fallback (no 500).

---

## Functional Requirements

- **FR-001**: Add a nullable `timezone` column (IANA string) to `users`, via Alembic revision `0004` (after upstream's `0003_clerk_users`).
- **FR-002**: `PATCH /v1/users/me` (and its `PUT` twin) MUST accept an optional `timezone`. When present and valid (`zoneinfo.ZoneInfo` parses it) and different from the stored value, persist it. Invalid values MUST be silently ignored (no 4xx), so a buggy client never breaks profile updates.
- **FR-003**: `GET /v1/users/me` (`CurrentUserOut`) and the `UserPublic` envelope MUST include `timezone` (nullable).
- **FR-004**: A new `get_user_timezone(session, user)` helper MUST resolve the caregiver's TZ, falling back to the system default when `users.timezone` is NULL or invalid.
- **FR-005**: Every date-window computation MUST use the active user's timezone: the four `list_by_date`/`list_by_start_date` repositories (TZ passed in by the API routers via `get_user_timezone`), and the agent's read tools + `_format_context` (via a per-request contextvar set in `get_current_user`, since the agent has no `User` in scope).
- **FR-006**: The frontend MUST, once signed in via Clerk and the local user is loaded, send the browser's detected timezone to `PATCH /v1/users/me` whenever it differs from the stored value.
- **FR-007**: No change to Clerk auth, the agent's tool schemas, or the system-prompt invariants. No endpoint shapes change beyond the additive `timezone` field.

## Success Criteria

- **SC-001**: A caregiver in any `zoneinfo` zone sees their own local-day boundaries everywhere immediately after the post-sign-in timezone capture, with no server reconfiguration.
- **SC-002**: A caregiver whose browser zone differs from the stored value sees it updated on next sign-in.
- **SC-003**: `users.timezone IS NULL` still yields 200 (system-default fallback) on every list endpoint.
- **SC-004**: Cross-tenant isolation preserved — one user's timezone never affects another's window query.

## Out of Scope

- Per-baby timezone; a manual timezone picker UI (deferred to the Profile page later); DST/historical-zone edge cases (handled by `zoneinfo`); changes to Clerk auth or the agent contract; upstream's webhook/Google paths.

## Dependencies

- Builds on the merged Clerk auth (features 007/008). Every list endpoint already resolves a `CurrentUser`; `PATCH /v1/users/me` already exists (currently display_name only).
- No new backend or frontend packages.
