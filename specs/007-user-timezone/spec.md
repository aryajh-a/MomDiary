# Feature Specification: Per-User Timezone

**Feature Branch**: `007-user-timezone`
**Created**: 2026-05-30
**Status**: Draft (for review)
**Input**: User description: "The timezone is currently hardcoded to LA. I want the app to take the timezone from the user's timezone."

## Problem Statement

Every date-windowed query in the backend (the `GET /v1/{feeds,sleeps,poops,appointments}?date=YYYY-MM-DD` endpoints, plus the `list_*` tools the agent uses internally) computes the `[start, end)` UTC window for a local calendar date using a **single global timezone** stored in the singleton `settings` row (default `America/Los_Angeles`, see [`config.py:27`](../../backend/src/momdiary/config.py#L27) and [`time_service.py:17-31`](../../backend/src/momdiary/services/time_service.py#L17-L31)). The same global TZ is also injected into the agent's `Current local time:` prefix ([`maf_runner.py:220-234`](../../backend/src/momdiary/agents/maf_runner.py#L220-L234)).

This is wrong as soon as a caregiver lives in a timezone other than the configured one. A real bug seen during local testing: a caregiver in IST (UTC+5:30) logged feeds at ~01:30 IST on May 30. The backend (configured for LA) computed the May 30 window as `2026-05-30T07:00Z` → `2026-05-31T07:00Z`. The entries (stored correctly at ~20:00Z May 29) fell **before** that window, so the UI's Feed History and Recent Activity sections showed "no entries for today" even though the data was saved.

The fix is to scope the timezone to the **user**, so every caregiver sees their own day boundaries everywhere in the app — list endpoints, the home dashboard, and the chat agent — without manual server-side reconfiguration.

## Clarifications

### Session 2026-05-30

- Q: Per-user, per-baby, or per-request timezone? → **A: Per-user.** (Most caregivers live in one TZ; the user is the natural ownership boundary. Per-request via header is implicit and harder to debug. See Plan §"Design choice".)
- Q: How is the user's timezone first set? → **A: Auto-detected at registration from the browser's `Intl.DateTimeFormat().resolvedOptions().timeZone`.** The register payload gains an optional `timezone` field; if absent or invalid, the user inherits the system default and the bug returns for them — so the frontend always sends it.
- Q: Existing users in the DB? → **A: None to migrate.** The single pre-feature test account is being deleted before implementation; we re-register from scratch after the change ships. No backfill path needed in the migration.
- Q: Settings UI to manually edit the timezone after signup? → **A: Defer.** Auto-detection at signup + login-time refresh covers v1. A manual override can be added later as a small follow-up on `PATCH /v1/users/me`.
- Q: On login from a browser whose timezone differs from the stored value, what does the backend do? → **A: Silently update.** No prompt, no error — the stored value is overwritten when the supplied zone is valid and different.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — New caregiver sees their own "today" (Priority: P1)

A first-time caregiver registers from a browser whose system timezone is `Asia/Kolkata`. After signing in and logging a feed at 01:00 their local time, they see that feed listed under "today" in Feed History and Recent Activity, without any backend reconfiguration.

**Why this priority**: This is the bug. Without this, the app silently hides data for any caregiver not in the backend's configured timezone — i.e., almost every real user.

**Independent Test**: A caregiver registers from a non-LA timezone, immediately logs a feed via the Feed History `+` modal at any past-but-near-now time, and confirms the entry appears in the same day's history page and on the home dashboard's Recent Activity section.

**Acceptance Scenarios**:

1. **Given** a brand-new caregiver registering from a browser reporting `Asia/Kolkata`, **When** their sign-up succeeds, **Then** their stored `users.timezone` is `Asia/Kolkata`.
2. **Given** a signed-in caregiver in `Asia/Kolkata`, **When** they log a feed at `2026-05-30T01:00:00+05:30`, **Then** `GET /v1/feeds?date=2026-05-30` returns the entry.
3. **Given** a signed-in caregiver in `Asia/Kolkata`, **When** they open the home dashboard at 01:30 IST, **Then** Recent Activity shows entries for IST's May 30, not LA's May 29.
4. **Given** a signed-in caregiver in any timezone, **When** they POST a chat message via `/v1/entries`, **Then** the agent's injected `Current local time:` reflects **their** timezone, not the system default.

---

### User Story 2 — Auto-correction when the browser's timezone differs from the stored value (Priority: P2)

A caregiver who originally registered while travelling is later using the app from their home timezone. The app detects the mismatch and updates the stored timezone so subsequent date windows align with where they actually are.

**Why this priority**: Smooths the experience for travel / device-switch edge cases. Not blocking for the core bug but prevents stale-TZ confusion.

**Independent Test**: A caregiver whose `users.timezone` is `America/Los_Angeles` signs in from a browser reporting `Asia/Kolkata`. After sign-in, `GET /v1/auth/me` returns `timezone: "Asia/Kolkata"` and subsequent list endpoints use IST windows.

**Acceptance Scenarios**:

1. **Given** a stored timezone of `America/Los_Angeles`, **When** the user signs in from a browser sending `Asia/Kolkata`, **Then** the backend updates `users.timezone` to `Asia/Kolkata` and the change is reflected in `/v1/auth/me`.
2. **Given** a stored timezone that matches the browser's, **When** the user signs in, **Then** no update is performed and no extra DB write occurs.

---

## Functional Requirements

- **FR-001**: The `users` table MUST gain a `timezone` column holding an IANA zone string (e.g., `Asia/Kolkata`). Nullable in v1 to allow gradual backfill.
- **FR-002**: `POST /v1/auth/register` MUST accept an optional `timezone` field in the request body. When present and valid (parsable by `zoneinfo.ZoneInfo`), it MUST be persisted on the new user row. When absent or invalid, the user row is created with `timezone=NULL` (no signup failure).
- **FR-003**: `POST /v1/auth/login` MUST accept an optional `timezone` field. When present and the supplied zone differs from the stored value, the backend MUST update `users.timezone`. When stored value is NULL and a valid zone is supplied, the backend MUST set it.
- **FR-004**: `GET /v1/auth/me` MUST include the user's `timezone` in the response (null-tolerant for legacy users).
- **FR-005**: Every backend code path that currently calls `get_default_timezone(session)` to compute a date window MUST instead resolve the **active user's** timezone, falling back to the system default only when the user has none.
- **FR-006**: The agent's `Current local time:` context line MUST reflect the active user's timezone.
- **FR-007**: The frontend MUST send `Intl.DateTimeFormat().resolvedOptions().timeZone` as the `timezone` field on both `/v1/auth/register` and `/v1/auth/login`.
- **FR-008**: Invalid timezone strings sent by the client MUST be silently ignored on the backend (no 4xx response), so a buggy browser/client never breaks sign-in. The stored value is unchanged in that case.
- **FR-009**: No existing endpoint shapes change beyond the additions above. No frontend list-fetch URL changes.

## Behavior of historical entries when the timezone changes

Every diary timestamp (`occurred_at`, `start_at`, `end_at`, `scheduled_at`) is persisted as an **absolute moment in UTC**. Switching a user's timezone does **not** rewrite, shift, or otherwise mutate any stored row. What changes is purely the *interpretation* of those moments at display- and query-time:

1. **The absolute moment stays the same.** A feed stored as `2026-05-30T05:00:00+00:00` remains that exact instant forever.
2. **The calendar date the entry is bucketed under may shift.** A `list_by_date(d)` query now computes `[start, end)` in the user's new timezone, so an entry that fell into "May 29" under the old TZ may fall into "May 30" under the new one (or vice versa). This is correct — "today" is observer-relative.
3. **The displayed wall-clock time shifts to the new TZ.** The frontend already renders timestamps via `parseISO(...) + format(...)` against the browser's local TZ ([`HomePage.tsx`](../../frontend/src/features/home/HomePage.tsx#L413)), so once the browser TZ matches the stored user TZ, every past entry shows its local clock time in the new zone.

### Worked example

A caregiver logs a feed at "10:00 PM May 29" while their TZ is `America/Los_Angeles`. The DB row holds `2026-05-30T05:00:00+00:00`. After they switch their stored TZ to `Asia/Kolkata`:

| What | Under LA | Under IST |
|---|---|---|
| Stored `occurred_at` (UTC) | `2026-05-30T05:00:00+00:00` | `2026-05-30T05:00:00+00:00` (unchanged) |
| Calendar bucket in `list_by_date` | **May 29** | **May 30** |
| Time displayed in the UI | **10:00 PM** | **10:30 AM** |
| Returned by `GET /v1/feeds?date=2026-05-30` | no | yes |

### Why this design

- It's **truthful**: a moment in time is what it is; "yesterday vs today" is perspective, not a property of the event.
- It matches what the UI already does on the display side (browser-local rendering of UTC timestamps).
- The alternative — freezing each entry's display TZ to whatever was active when it was written — would produce a split-brain UI where some rows render in TZ_A and others in TZ_B, which is harder to reason about.

### Footgun to be aware of

Entries logged "late at night" in the old TZ may cross a calendar boundary into an adjacent date under the new TZ. This is correct behavior but can momentarily surprise a user who has just changed their location. No UI affordance is added in v1; if it becomes a real source of confusion, a future "first-time-after-TZ-change" toast can be added cheaply.

## Success Criteria

- **SC-001**: A caregiver registering from any IANA zone supported by `zoneinfo` sees their own local-day boundaries everywhere in the app (list endpoints, Recent Activity, agent prompt) immediately after signup, with no server reconfiguration.
- **SC-002**: A caregiver whose stored TZ differs from their current browser TZ sees the stored value updated on their next successful login.
- **SC-003**: For a caregiver whose `users.timezone IS NULL` (defensive case — only possible if a future client fails to send the field), list endpoints still respond 200 using the system-default fallback. No 500s, no NPEs.
- **SC-004**: Cross-tenant isolation is preserved: user A's stored timezone cannot influence any window query made on behalf of user B.

## Out of Scope

- Per-baby timezone (a single user always uses one zone in v1; siblings in different time zones is a future feature).
- A Settings UI to manually edit the timezone (deferred — auto-detection covers v1; manual override can come later as a one-line PATCH on the existing `PATCH /v1/users/me`).
- DST handling, historical timezone changes, or pre-1970 datetimes (all already correctly handled by `zoneinfo`; no change needed).
- Changing the agent's tool schemas or system-prompt invariants (FR-002, FR-011, FR-017, FR-018 from feature 001 are untouched).

## Dependencies

- Feature 006 (auth + baby profiles) — every endpoint touched here already has `CurrentUserDep` wired up.
- No new third-party packages.
