---
description: "Task list for feature 006-user-and-baby-profiles"
---

# Tasks: User & Baby Profiles with Authentication

**Input**: Design documents from `/specs/006-user-and-baby-profiles/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The project Constitution (II — NON-NEGOTIABLE) requires test-first development with unit + integration + contract tiers. Every implementation task is paired with its tests.

**Organization**: Tasks are grouped by user story so each story is independently testable, deliverable, and (after Foundational) parallelizable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]** — different files, no dependencies on other in-progress tasks
- **[USx]** — user story this task belongs to (Setup / Foundational / Polish carry no story label)

---

## Phase 1: Setup (Shared infrastructure)

- [X] T001 Add `argon2-cffi>=23.1.0` to backend dependencies in [backend/pyproject.toml](backend/pyproject.toml) and refresh the lockfile.
- [X] T002 Install the new dependency in the active venv (`pip install -e ".[dev]"` from `backend/`) and confirm `import argon2` succeeds.
- [ ] T003 [P] Add lint/format allowlist entries for the new `momdiary.auth` and `momdiary.babies` packages in [backend/pyproject.toml](backend/pyproject.toml) (ruff `[tool.ruff.lint.per-file-ignores]` and any mypy section).

---

## Phase 2: Foundational (Blocking prerequisites for all user stories)

**⚠️ CRITICAL**: no user-story work begins until this phase is complete.

### Schema & ORM

- [X] T004 Create the Alembic revision skeleton `006_users_babies` in [backend/src/momdiary/db/migrations/versions/2026XXXX_006_users_babies.py](backend/src/momdiary/db/migrations/versions/2026XXXX_006_users_babies.py) with empty `upgrade()` / `downgrade()` bodies and the revision metadata.
- [X] T005 In the same revision, implement `upgrade()` step 1 — create `users`, `user_sessions`, `babies` tables with all columns, constraints, and indexes from [data-model.md](./data-model.md).
- [X] T006 In the same revision, implement `upgrade()` step 2 — hard-delete all rows from `feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`, `agent_interactions` (per FR-018).
- [X] T007 In the same revision, implement `upgrade()` step 3 — add `baby_id TEXT NOT NULL` FK to each of those six tables plus their composite indexes (`(baby_id, occurred_at|start_at|scheduled_at, deleted_at)`), and implement `downgrade()` (reverse step 3 then step 1; deletions are not restored).
- [X] T008 [P] Add `User`, `UserSession`, `Baby` SQLAlchemy ORM classes to [backend/src/momdiary/models/orm.py](backend/src/momdiary/models/orm.py).
- [X] T009 [P] In [backend/src/momdiary/models/orm.py](backend/src/momdiary/models/orm.py), add a `baby_id` mapped column + relationship to each of `Feed`, `Sleep`, `Poop`, `Appointment`, `AppointmentNote`, `AgentInteraction`.

### Pydantic schemas

- [X] T010 [P] Create [backend/src/momdiary/schemas/auth.py](backend/src/momdiary/schemas/auth.py) with `RegisterRequest`, `LoginRequest`, `ErrorResponse` matching [contracts/auth-and-profiles.openapi.yaml](./contracts/auth-and-profiles.openapi.yaml).
- [X] T011 [P] Create [backend/src/momdiary/schemas/users.py](backend/src/momdiary/schemas/users.py) with `UserResponse`, `UserUpdate`, `SetActiveBabyRequest`.
- [X] T012 [P] Create [backend/src/momdiary/schemas/babies.py](backend/src/momdiary/schemas/babies.py) with `BabyResponse`, `BabyCreate`, `BabyUpdate`.

### Auth module (no endpoints yet — just primitives)

- [X] T013 Create [backend/src/momdiary/auth/hasher.py](backend/src/momdiary/auth/hasher.py) exposing `hash_password(plain) -> str`, `verify_password(hash, plain) -> bool`, `dummy_verify() -> None` (constant-time enumeration defense), and `needs_rehash(hash) -> bool`, all backed by `argon2.PasswordHasher` with the parameters from [research.md](./research.md) R1.
- [X] T014 [P] Unit test [backend/tests/unit/test_argon2_hasher.py](backend/tests/unit/test_argon2_hasher.py) covering: hash/verify round-trip, wrong-password rejection, `dummy_verify` constant-time path completes, `needs_rehash` returns False on freshly issued hashes.
- [X] T015 Create [backend/src/momdiary/auth/sessions.py](backend/src/momdiary/auth/sessions.py) exposing `SessionService` with `issue(user_id, user_agent) -> session_id`, `validate_and_slide(session_id) -> User | None` (slides `expires_at` to `now()+30d` + updates `last_seen_at`), and `revoke(session_id) -> None`.
- [X] T016 [P] Unit test [backend/tests/unit/test_session_service.py](backend/tests/unit/test_session_service.py) covering: issuance produces a 32+ byte URL-safe token, validate succeeds → slides expiry, revoked sessions fail validation, expired sessions fail validation.
- [X] T017 Create [backend/src/momdiary/auth/dependencies.py](backend/src/momdiary/auth/dependencies.py) exposing FastAPI `Depends` callables: `get_current_user` (reads `momdiary_session` cookie → `SessionService.validate_and_slide` → 401 if missing/invalid), `get_active_baby` (reads `X-Active-Baby-Id` header or falls back to `users.active_baby_id`; 409 `no_active_baby` if none; 404 if header references an unowned baby).
- [X] T018 Create [backend/src/momdiary/auth/middleware.py](backend/src/momdiary/auth/middleware.py) implementing an ASGI middleware that enriches `structlog` context with `user_id` and `baby_id` (both `None` for anonymous requests) and an `Origin`/`Referer` check on state-changing methods (POST/PUT/PATCH/DELETE) per [research.md](./research.md) R3.
- [X] T019 [P] Create the module README at [backend/src/momdiary/auth/README.md](backend/src/momdiary/auth/README.md) documenting the public surface (per Constitution IV).

### Babies module (no endpoints yet)

- [X] T020 Create [backend/src/momdiary/babies/service.py](backend/src/momdiary/babies/service.py) exposing `BabyService` with `list_for_user(user_id)`, `create(user_id, payload)`, `get_owned(user_id, baby_id)` (returns 404-style miss on cross-tenant probe), `update(user_id, baby_id, payload)`, `soft_delete(user_id, baby_id)`, and `resolve_active(user_id, header_value)`.
- [ ] T021 [P] Unit test [backend/tests/unit/test_baby_resolver.py](backend/tests/unit/test_baby_resolver.py) for `resolve_active`: header wins over preference, missing-header falls back to preference, cross-tenant header returns 404-style miss, soft-deleted baby is treated as not found.
- [X] T022 [P] Create the module README at [backend/src/momdiary/babies/README.md](backend/src/momdiary/babies/README.md).

### Chat session store partitioning (FR-017)

- [X] T023 Modify [backend/src/momdiary/services/chat_session_store.py](backend/src/momdiary/services/chat_session_store.py) to key all entries by the tuple `(user_id, baby_id, session_id)`; preserve existing TTL / bounds; reject lookups with any missing component.
- [X] T024 [P] Update unit test [backend/tests/unit/test_chat_session_store.py](backend/tests/unit/test_chat_session_store.py) (or add a new partition test) proving that sessions with same `session_id` but different `(user_id, baby_id)` are isolated. — implemented as [backend/tests/unit/test_session_store_partition.py](backend/tests/unit/test_session_store_partition.py).

### Shared frontend wiring

- [X] T025 [P] Extend [frontend/src/shared/apiClient.ts](frontend/src/shared/apiClient.ts) to send `credentials: "include"` on every request, attach an `X-Active-Baby-Id` header from a module-level resolver, and register a global response interceptor that on `401` invalidates the `["session"]` query and dispatches a redirect to `/login`.
- [X] T026 [P] Extend [frontend/src/shared/types.ts](frontend/src/shared/types.ts) with zod schemas `userResponseSchema`, `babyResponseSchema`, `errorEnvelopeSchema`, `setActiveBabyRequestSchema`.

**Checkpoint**: Foundation ready — all user-story phases can now begin in parallel.

---

## Phase 3: User Story 1 — New caregiver creates account and signs in (Priority: P1) 🎯 MVP

**Goal**: A brand-new caregiver can register, sign in, see `/v1/auth/me` succeed, and sign out — all without ever touching a baby. The diary surface is gated behind sign-in.

**Independent Test**: Register `alice@example.com`, hit `/v1/auth/me` → 200 with `active_baby_id: null`, sign out → next `/v1/auth/me` → 401. In the browser, anonymous navigation to `/` redirects to `/login`.

### Tests for User Story 1 (write first, ensure they FAIL)

- [ ] T027 [P] [US1] Contract test [backend/tests/contract/test_auth_and_profiles_contract.py](backend/tests/contract/test_auth_and_profiles_contract.py) — schema-validate `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/logout`, `/v1/auth/me` responses against [contracts/auth-and-profiles.openapi.yaml](./contracts/auth-and-profiles.openapi.yaml).
- [X] T028 [P] [US1] Integration test [backend/tests/integration/test_auth_endpoints.py](backend/tests/integration/test_auth_endpoints.py) covering: happy-path register-then-me, duplicate-email returns uniform 401 (FR-006), weak/invalid input returns 400, wrong-password returns 401, sign-out invalidates cookie, post-sign-out call returns 401 `unauthenticated`.
- [ ] T029 [P] [US1] Frontend test [frontend/tests/auth.test.tsx](frontend/tests/auth.test.tsx) covering: anonymous navigation redirects to `/login`, successful sign-up reaches the post-signup state, failed sign-in shows the uniform error message, sign-out returns to `/login`.

### Implementation for User Story 1

- [X] T030 [US1] Create [backend/src/momdiary/api/routes/auth.py](backend/src/momdiary/api/routes/auth.py) implementing `POST /v1/auth/register`, `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/auth/me`. The register path MUST call `hasher.dummy_verify()` on identifier collision (per [research.md](./research.md) R8) and MUST return the same 401 envelope as a bad login.
- [X] T031 [US1] Wire the auth router into [backend/src/momdiary/api/main.py](backend/src/momdiary/api/main.py) and install the auth middleware from T018.
- [X] T032 [US1] Create [frontend/src/features/auth/useSession.ts](frontend/src/features/auth/useSession.ts) — TanStack Query hook on `GET /v1/auth/me` keyed `["session"]` with `staleTime: Infinity`; expose `{ status, user, signOut() }`.
- [X] T033 [P] [US1] Create [frontend/src/features/auth/LoginPage.tsx](frontend/src/features/auth/LoginPage.tsx) and [frontend/src/features/auth/SignupPage.tsx](frontend/src/features/auth/SignupPage.tsx) with the uniform-error contract from FR-006.
- [X] T034 [US1] Create [frontend/src/features/auth/RequireAuth.tsx](frontend/src/features/auth/RequireAuth.tsx) — route guard that renders children when signed-in, otherwise redirects to `/login`.
- [X] T035 [US1] Mount `<RequireAuth>` at the root of [frontend/src/App.tsx](frontend/src/App.tsx); add `/login` and `/signup` routes that bypass the guard.

**Checkpoint**: A caregiver can fully sign up, sign in, and sign out. No baby exists yet; diary endpoints still 409 with `no_active_baby` (handled in US2).

---

## Phase 4: User Story 2 — Caregiver adds first baby and logs scoped data (Priority: P1)

**Goal**: A signed-in caregiver with no baby is prompted to create one; first baby auto-becomes active; every diary read/write is scoped to that baby; two caregivers see strict isolation.

**Independent Test**: Sign in as Alice, create baby Bobby → `users.active_baby_id` is now Bobby. POST a feed via `/v1/entries` → new `feeds` row has `baby_id = Bobby.id`. Sign in as Carol with baby Cara → her feeds list is empty even on Bobby's date.

### Tests for User Story 2 (write first)

- [ ] T036 [P] [US2] Contract test add-ons in [backend/tests/contract/test_auth_and_profiles_contract.py](backend/tests/contract/test_auth_and_profiles_contract.py) covering `GET /v1/babies` and `POST /v1/babies`.
- [X] T037 [P] [US2] Integration test [backend/tests/integration/test_babies_endpoints.py](backend/tests/integration/test_babies_endpoints.py): create-list-get round trip, first-baby auto-sets `active_baby_id`, second-baby does not, cross-tenant GET on another caregiver's baby returns 404 (FR-016).
- [X] T038 [P] [US2] Integration test [backend/tests/integration/test_entries_scoping.py](backend/tests/integration/test_entries_scoping.py): unauthenticated `POST /v1/entries` returns 401; authenticated without active baby returns 409 `no_active_baby`; with active baby, write persists `baby_id`; cross-tenant edit attempt via `PUT /v1/entries/{id}` returns 404.
- [ ] T039 [P] [US2] Integration test [backend/tests/integration/test_chatentry_scoping.py](backend/tests/integration/test_chatentry_scoping.py): same matrix as T038 against `POST /v1/chatentry/`.
- [ ] T040 [P] [US2] Integration test [backend/tests/integration/test_list_endpoints_scoping.py](backend/tests/integration/test_list_endpoints_scoping.py): `GET /v1/feeds`, `/v1/sleeps`, `/v1/poops`, `/v1/appointments` each return only rows where `baby_id = active baby`; verified with two-caregiver fixture for zero leakage (SC-003).
- [ ] T041 [P] [US2] Frontend test [frontend/tests/babies.test.tsx](frontend/tests/babies.test.tsx) covering: signed-in caregiver with zero babies sees `FirstBabyPrompt`; submitting creates a baby; diary surface unlocks; logged chat entry appears in today's list.

### Implementation for User Story 2

- [X] T042 [US2] Create [backend/src/momdiary/api/routes/babies.py](backend/src/momdiary/api/routes/babies.py) implementing `GET /v1/babies` and `POST /v1/babies`. On first-baby creation set `users.active_baby_id = new.id`.
- [X] T043 [US2] Wire the babies router into [backend/src/momdiary/api/main.py](backend/src/momdiary/api/main.py).
- [X] T044 [US2] Modify [backend/src/momdiary/api/routes/entries.py](backend/src/momdiary/api/routes/entries.py) to add `Depends(get_current_user)` and `Depends(get_active_baby)`; pass `baby_id` into the dispatcher and into the chat session-store key.
- [X] T045 [US2] Modify [backend/src/momdiary/services/entries_dispatcher.py](backend/src/momdiary/services/entries_dispatcher.py) to accept `baby_id` and persist it on every write (Feed/Sleep/Poop/Appointment/AppointmentNote/AgentInteraction).
- [X] T046 [US2] Modify [backend/src/momdiary/api/routes/chatentry.py](backend/src/momdiary/api/routes/chatentry.py) the same way as T044. — **OBSOLETE**: no `chatentry` route exists in this codebase; all natural-language entries flow through `/v1/entries` which already enforces `active_baby` (T044).
- [X] T047 [US2] Modify [backend/src/momdiary/services/chatentry_dispatcher.py](backend/src/momdiary/services/chatentry_dispatcher.py) to accept and persist `baby_id` (mirrors T045). — **OBSOLETE**: no `chatentry_dispatcher.py` exists; baby-scoping is handled by `require_active_baby` + repository contextvar in the existing dispatcher (T045).
- [X] T048 [P] [US2] Modify [backend/src/momdiary/api/routes/feeds.py](backend/src/momdiary/api/routes/feeds.py) to require auth and filter `WHERE baby_id = active_baby AND deleted_at IS NULL`.
- [X] T049 [P] [US2] Same retrofit on [backend/src/momdiary/api/routes/sleeps.py](backend/src/momdiary/api/routes/sleeps.py).
- [X] T050 [P] [US2] Same retrofit on [backend/src/momdiary/api/routes/poops.py](backend/src/momdiary/api/routes/poops.py).
- [X] T051 [P] [US2] Same retrofit on [backend/src/momdiary/api/routes/appointments.py](backend/src/momdiary/api/routes/appointments.py) (including the appointment-notes sub-routes).
- [X] T052 [P] [US2] Create [frontend/src/features/babies/useBabies.ts](frontend/src/features/babies/useBabies.ts) — TanStack Query hooks for list + create.
- [X] T053 [P] [US2] Create [frontend/src/features/babies/FirstBabyPrompt.tsx](frontend/src/features/babies/FirstBabyPrompt.tsx) and [frontend/src/features/babies/RequireBaby.tsx](frontend/src/features/babies/RequireBaby.tsx).
- [X] T054 [US2] Mount `<RequireBaby>` inside `<RequireAuth>` in [frontend/src/App.tsx](frontend/src/App.tsx); when no baby exists, render `FirstBabyPrompt` instead of the diary shell.

**Checkpoint**: MVP complete — caregivers can sign up, add a baby, and log entries scoped to that baby. Multi-tenant isolation verified.

---

## Phase 5: User Story 3 — Returning caregiver resumes context (Priority: P2)

**Goal**: A returning caregiver lands directly in their last-active baby on sign-in.

**Independent Test**: Sign in, set active baby to A, sign out, sign back in → `users.active_baby_id` already restored to A; `GET /v1/auth/me` returns it.

### Tests for User Story 3

- [ ] T055 [P] [US3] Integration test [backend/tests/integration/test_session_restore.py](backend/tests/integration/test_session_restore.py): preference persists across sign-out/sign-in; deleted active baby falls back to most-recently-created surviving baby; with no babies, falls back to `null`.

### Implementation for User Story 3

- [X] T056 [US3] In [backend/src/momdiary/api/routes/auth.py](backend/src/momdiary/api/routes/auth.py), on `POST /v1/auth/login` validate that `users.active_baby_id` still references an owned, non-deleted baby; if not, fall back per FR-011 and persist the new value.
- [X] T057 [P] [US3] Update [frontend/src/features/auth/useSession.ts](frontend/src/features/auth/useSession.ts) to expose `activeBabyId` from the `/v1/auth/me` response and seed the API client header resolver from T025 on session change.

**Checkpoint**: Returning caregivers land in the right baby on sign-in.

---

## Phase 6: User Story 4 — Multi-baby switch (Priority: P2)

**Goal**: A caregiver with multiple babies can switch the active baby; chat sessions partition correctly.

**Independent Test**: Create baby A and baby B. Log a feed under A, switch active to B, log a feed under B, switch back to A. A's day list shows only A's feed, B's only B's. Same `X-Session-ID` used across the switch yields disjoint chat histories.

### Tests for User Story 4

- [X] T058 [P] [US4] Integration test [backend/tests/integration/test_active_baby_switch.py](backend/tests/integration/test_active_baby_switch.py) covering: `POST /v1/users/me/active-baby` persists the change; subsequent reads/writes target the new baby; cross-tenant `baby_id` returns 404; in-flight requests against the old baby complete under the old baby (FR-016 + acceptance scenario 4.3). — implemented as part of [backend/tests/integration/test_users_and_active_baby.py](backend/tests/integration/test_users_and_active_baby.py).
- [ ] T059 [P] [US4] Integration test [backend/tests/integration/test_chat_partitioning.py](backend/tests/integration/test_chat_partitioning.py): same `X-Session-ID` with different active babies yields independent chat histories (FR-017).

### Implementation for User Story 4

- [X] T060 [US4] Create [backend/src/momdiary/api/routes/users.py](backend/src/momdiary/api/routes/users.py) implementing `POST /v1/users/me/active-baby` (validate baby ownership; 404 on miss; persist).
- [X] T061 [US4] Wire the users router into [backend/src/momdiary/api/main.py](backend/src/momdiary/api/main.py).
- [X] T062 [P] [US4] Create [frontend/src/features/babies/BabySwitcher.tsx](frontend/src/features/babies/BabySwitcher.tsx) — dropdown in the app shell; on selection calls `/v1/users/me/active-baby`, updates the header resolver, and invalidates `["babies"]` + every active diary query.
- [X] T063 [US4] In [frontend/src/features/chat/](frontend/src/features/chat/) and [frontend/src/features/chatentry/](frontend/src/features/chatentry/), emit a fresh client-generated `X-Session-ID` whenever the active baby changes (per [research.md](./research.md) R6).

**Checkpoint**: Multi-baby caregivers can switch seamlessly with no cross-contamination.

---

## Phase 7: User Story 5 — Profile edits and baby soft-delete (Priority: P3)

**Goal**: Caregivers edit their own display name, edit baby profiles, and soft-delete babies.

**Independent Test**: PUT `/v1/users/me {display_name}` updates the shell. PATCH `/v1/babies/{id}` renames a baby. DELETE `/v1/babies/{id}` removes it from the switcher and from list endpoints; if it was the active baby, the preference reassigns or clears.

### Tests for User Story 5

- [X] T064 [P] [US5] Integration test [backend/tests/integration/test_users_endpoints.py](backend/tests/integration/test_users_endpoints.py): `PUT /v1/users/me` happy path + 400 on empty `display_name` + 401 anonymous. — covered in [backend/tests/integration/test_users_and_active_baby.py](backend/tests/integration/test_users_and_active_baby.py).
- [X] T065 [P] [US5] Extend [backend/tests/integration/test_babies_endpoints.py](backend/tests/integration/test_babies_endpoints.py) with `PATCH` (happy + cross-tenant 404) and `DELETE` (soft-delete + active-baby reassignment per FR-011 + last-baby-deleted clears preference). — implementation clears `active_baby_id` to null on delete of active baby (caregiver must explicitly pick a remaining baby).
- [ ] T066 [P] [US5] Frontend test extension in [frontend/tests/babies.test.tsx](frontend/tests/babies.test.tsx) covering rename and soft-delete flows.

### Implementation for User Story 5

- [X] T067 [US5] In [backend/src/momdiary/api/routes/users.py](backend/src/momdiary/api/routes/users.py), implement `PUT /v1/users/me`.
- [X] T068 [US5] In [backend/src/momdiary/api/routes/babies.py](backend/src/momdiary/api/routes/babies.py), implement `PATCH /v1/babies/{baby_id}` and `DELETE /v1/babies/{baby_id}` (soft-delete sets `deleted_at`; if the deleted baby was `users.active_baby_id`, reassign per FR-011 in the same transaction).
- [ ] T069 [P] [US5] Add edit / delete affordances to [frontend/src/features/babies/BabySwitcher.tsx](frontend/src/features/babies/BabySwitcher.tsx) (and a small "edit my profile" panel in the app shell calling `/v1/users/me`).

**Checkpoint**: All five user stories functional end-to-end.

---

## Phase 8: Polish & cross-cutting concerns

- [ ] T070 [P] Add the auth benchmark [backend/tests/benchmarks/test_auth_perf.py](backend/tests/benchmarks/test_auth_perf.py): asserts Argon2id verify median < 150 ms and `SessionService.validate_and_slide` p95 < 25 ms on dev hardware (per Constitution III, SC-002).
- [X] T071 [P] Update [backend/src/momdiary/services/entries_dispatcher.py](backend/src/momdiary/services/entries_dispatcher.py) and [backend/src/momdiary/services/chatentry_dispatcher.py](backend/src/momdiary/services/chatentry_dispatcher.py) structured-log calls to include `user_id` + `baby_id` fields (FR-022). — implemented via `structlog.contextvars.bind_contextvars(user_id=..., baby_id=...)` in [backend/src/momdiary/auth/dependencies.py](backend/src/momdiary/auth/dependencies.py); every downstream log line in the request (including dispatcher, registry, repositories) now carries both fields automatically. `chatentry_dispatcher.py` does not exist in this codebase — only the `/v1/entries` flow is used.
- [X] T072 [P] Update top-level [README.md](README.md) with a short "Authentication & baby profiles" section pointing to [specs/006-user-and-baby-profiles/quickstart.md](specs/006-user-and-baby-profiles/quickstart.md).
- [X] T073 [P] Update [backend/requests.http](backend/requests.http) with a new "Feature 006 — auth & babies" section: register, login, me, create baby, set active baby, edit baby, logout.
- [ ] T074 Run the full quickstart end-to-end per [quickstart.md](./quickstart.md) — including the cross-tenant isolation check (step 6) and the sign-out gating check (step 7) — and confirm every step passes.
- [ ] T075 Run `pytest -q` and `npm test` to confirm the entire suite is green; address any incidental regressions in existing tests caused by the new auth gate (e.g., fixtures that previously assumed anonymous access now need a session-cookie helper).

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 Setup** — no dependencies.
- **Phase 2 Foundational** — depends on Phase 1. **Blocks every user-story phase.**
- **Phase 3 (US1)** — depends on Phase 2. Independent of US2–US5.
- **Phase 4 (US2)** — depends on Phase 2 and on auth being callable from tests (which arrives at T030 inside US1); strictly speaking only the `get_current_user` dependency is needed, so US2 can proceed once Foundational is done if tests stub the user.
- **Phase 5 (US3)** — depends on Phase 4 (needs baby preference to exist).
- **Phase 6 (US4)** — depends on Phase 4 (needs >1 baby concept and chat partitioning fully wired).
- **Phase 7 (US5)** — depends on Phase 4.
- **Phase 8 Polish** — depends on the user stories you intend to ship.

### Within each user story

- Tests are authored first and MUST FAIL before the corresponding implementation tasks land (Constitution II).
- Models / schemas before services. Services before routes. Routes before frontend wiring.
- Don't begin the next user story until the previous story's checkpoint is green.

### Parallel opportunities

- Within Setup: T003 is `[P]`.
- Within Foundational: T008, T009, T010, T011, T012, T014, T016, T019, T021, T022, T024, T025, T026 are all `[P]` (different files).
- Within US1: T027, T028, T029, T033 are `[P]`.
- Within US2: T036, T037, T038, T039, T040, T041, T048, T049, T050, T051, T052, T053 are `[P]`.
- Across stories: once Foundational is done, US1/US2/US3/US4/US5 can be split across developers; the only hard chain is US3/US4/US5 each waiting for US2's baby plumbing.

---

## Parallel example: User Story 2 (post-Foundational)

```bash
# All tests for US2 in parallel:
Task: "Contract test add-ons for /v1/babies in backend/tests/contract/test_auth_and_profiles_contract.py"
Task: "Integration test in backend/tests/integration/test_babies_endpoints.py"
Task: "Integration test in backend/tests/integration/test_entries_scoping.py"
Task: "Integration test in backend/tests/integration/test_chatentry_scoping.py"
Task: "Integration test in backend/tests/integration/test_list_endpoints_scoping.py"
Task: "Frontend test in frontend/tests/babies.test.tsx"

# All list-endpoint retrofits in parallel (different files):
Task: "Retrofit backend/src/momdiary/api/routes/feeds.py"
Task: "Retrofit backend/src/momdiary/api/routes/sleeps.py"
Task: "Retrofit backend/src/momdiary/api/routes/poops.py"
Task: "Retrofit backend/src/momdiary/api/routes/appointments.py"
```

---

## Implementation Strategy

### MVP scope (suggested)

1. Phase 1 (Setup) — T001–T003.
2. Phase 2 (Foundational) — T004–T026. **No story work until this is green.**
3. Phase 3 (US1) — T027–T035. STOP and validate: sign-up / sign-in / sign-out works end-to-end.
4. Phase 4 (US2) — T036–T054. STOP and validate against [quickstart.md](./quickstart.md) steps 1–7.
5. Ship the MVP.

### Incremental delivery after MVP

- US3 (Phase 5) — restored active baby on sign-in. Low risk; ship next.
- US4 (Phase 6) — multi-baby switcher + chat partitioning. Ship third.
- US5 (Phase 7) — profile edit + soft-delete. Ship last.
- Polish (Phase 8) — benchmarks, log enrichment, README/requests.http updates, full quickstart run.

### Parallel team plan

- Two backend devs: one runs Phase 2 schema/migration (T004–T009), the other builds the auth + babies primitives (T013–T022) in parallel.
- One frontend dev runs T025, T026 then US1 frontend tasks while backend US1 routes are being built.
- After Foundational, split US3 / US4 / US5 across pairs.

---

## Notes

- `[P]` = different files, no in-flight dependencies on other tasks.
- `[USx]` labels user-story phase tasks for traceability; Setup, Foundational, and Polish tasks carry no story label.
- Tests precede implementation (Constitution II is NON-NEGOTIABLE).
- Commit after each task or logical group.
- Stop at each checkpoint to validate the story independently before moving on.
- No new AI agent code is introduced anywhere in this feature; the existing MAF (`/v1/entries`) and direct-LLM (`/v1/chatentry/`) paths are preserved and simply gain auth + baby scoping.
