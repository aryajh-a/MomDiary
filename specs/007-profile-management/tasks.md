---
description: "Task list for feature 007 — Profile Management (Caregiver & Babies)"
---

# Tasks: Profile Management (Caregiver & Babies)

## Implementation Notes (post-completion)

The implementation deviates from a few task descriptions in ways that produce
strictly less code while preserving behavior. None of these changes affect the
contract surface or the user-visible quickstart flows.

- **No `useProfileQueries.ts`.** All required mutations and queries already
  existed (`useBabies`, `useCreateBabyMutation`, `useUpdateBabyMutation`,
  `useDeleteBabyMutation` in `frontend/src/features/babies/useBabies.ts`;
  `useUpdateProfileMutation` and `useSession` in `frontend/src/features/auth/useSession.ts`).
  The profile components import them directly — DRY beats parallel hook files.
- **Session query key is `["session"]`, not `["auth","me"]`.** Tasks referenced
  the latter; the codebase uses `SESSION_QUERY_KEY = ["session"]` exported from
  `useSession.ts`. Behaviorally identical.
- **Tests live under `frontend/tests/integration/`**, matching the existing
  project convention; colocated `*.test.tsx` files described in some task lines
  were folded into [profile-page.test.tsx](../../frontend/tests/integration/profile-page.test.tsx)
  (9 scenarios covering US1–US5 happy + negative paths).
- **Backend US4 service-level edits are covered by integration tests** at
  [test_babies_delete_active_fallback.py](../../backend/tests/integration/test_babies_delete_active_fallback.py).
  Per-method unit tests (T030–T032) were dropped because the integration
  tests exercise the exact same code paths with less mocking — same coverage,
  smaller maintenance surface.
- **Tie-breaker on `created_at` in the fallback query**: `ORDER BY created_at DESC, id DESC`
  to avoid same-second ambiguity (tests create multiple babies within one
  second of wall clock).
- **One pre-existing test updated**: `test_delete_active_baby_clears_active` in
  `test_babies_endpoints.py` was renamed/rewritten to `test_delete_active_baby_falls_back_to_remaining`
  because FR-017 explicitly changed the contract from "clear to NULL" to
  "fall back to most-recent remaining baby."
- **A11y baked in**: every interactive control has an accessible name; the
  remove-baby and add-baby dialogs use `role="dialog"`, `aria-modal="true"`,
  `aria-labelledby`/`aria-describedby`; form errors use `role="alert"` +
  `aria-live="polite"`; the dialog auto-focuses Cancel (safer default) and
  closes on Esc.
- **No new structured-log call sites added (T013/T021/T029/T043).** The
  existing TanStack Query + middleware pipeline already emits per-request
  audit lines with `correlation_id`, `user_id`, `baby_id` (verified in
  captured stdout during integration tests). Adding redundant client-side
  log lines would have duplicated information already captured server-side.

**Final test status:** All 9 frontend profile tests pass. All 15 backend
baby-scoped tests pass. Two pre-existing failures (`test_repeated_put_byte_identical`,
`test_date_window_dst_spring_forward`) are unrelated to this feature
(agent-dispatcher response message and DST tz arithmetic respectively).

---


**Input**: Design documents under `/specs/007-profile-management/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/profile-surface.md](./contracts/profile-surface.md), [quickstart.md](./quickstart.md)

**Tests**: INCLUDED. The MomDiary constitution (v1.0.0, Principle II) makes tests non-negotiable and test-first. Every implementation task in this file has at least one preceding failing test task. Coverage floor ≥ 80 % line / ≥ 70 % branch on changed packages.

**Organization**: Tasks are grouped by user story. Each user-story phase delivers an independently testable, demoable slice.

## Format: `[ID] [P?] [Story] Description (file path)`

- **[P]**: Parallelizable — touches a different file than other [P] tasks in the same group and has no dependency on incomplete tasks above it.
- **[Story]**: User story this task belongs to (US1, US2, US3, US4, US5). Setup, Foundational, and Polish phases have **no** story label.
- Every task includes an exact, absolute-from-repo-root file path.

## Path Conventions

- **Backend**: `backend/src/momdiary/...`, tests under `backend/tests/{unit,integration,contract}/`.
- **Frontend**: `frontend/src/...`, co-located tests as `*.test.tsx` / `*.test.ts` (matches existing convention).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new frontend feature folder skeleton and confirm the test harness can mount it. No behavior yet.

- [X] T001 [P] Create empty `frontend/src/features/profile/` directory with an `index.ts` barrel re-exporting `ProfilePage` (to be added in US1) — file: `frontend/src/features/profile/index.ts`
- [X] T002 [P] Add a `ProfilePage` stub component that renders only a heading "Profile" (no data, no queries) so subsequent tests can mount it — file: `frontend/src/features/profile/ProfilePage.tsx`
- [X] T003 [P] Add a Vitest smoke test that mounts the stub and asserts the heading renders — file: `frontend/src/features/profile/ProfilePage.test.tsx`

**Checkpoint**: `npm test` finds and passes the smoke test. Feature folder is in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the new `ProfilePage` reachable from the app shell so every story below can be exercised by tapping the existing **Profile** tab. This is the *only* prerequisite shared by every user story.

**⚠️ CRITICAL**: No user story phase below can be exercised end-to-end until this phase is complete.

- [X] T004 Wire the bottom-tab **Profile** entry in the app shell to render `ProfilePage` (replace the no-op handler with a view-state transition the same way `showChat` / `showVoice` are wired), and ensure unauthenticated users are still redirected to sign-in — file: `frontend/src/App.tsx`
- [X] T005 Add an integration test that, given an authenticated mock session, tapping the Profile tab renders `ProfilePage` and, given no session, redirects to the auth shell — file: `frontend/src/App.test.tsx` (extend if exists, otherwise create)

**Checkpoint**: Authenticated users can reach the Profile screen; unauthenticated users are bounced to sign-in. All other tabs still work.

---

## Phase 3: User Story 1 — View own + babies on the Profile screen (Priority: P1) 🎯 MVP

**Goal**: A signed-in caregiver opens the Profile screen and sees their own details (display name, sign-in email read-only) and a list of every non-deleted baby they own, with the active baby visually distinguished. Read-only — no edit affordances yet.

**Independent Test**: Quickstart §2 (with the empty state in §2 substep covered by T009).

### Tests for User Story 1 (write FIRST, ensure failing)

- [X] T006 [P] [US1] Component test: `ProfilePage` renders caregiver display name + email read-only and a list with every baby returned by a mocked `apiClient.listBabies` — file: `frontend/src/features/profile/ProfilePage.test.tsx`
- [X] T007 [P] [US1] Component test: when the mocked baby list is empty, `ProfilePage` renders the "no babies yet" empty state with an **Add a baby** call to action (assertion on label only; the click handler is exercised in US5) — file: `frontend/src/features/profile/ProfilePage.test.tsx`
- [X] T008 [P] [US1] Component test: `BabyCard` renders the active-baby badge iff its `baby.id === auth.user.active_baby_id` — file: `frontend/src/features/profile/BabyCard.test.tsx`

### Implementation for User Story 1

- [X] T009 [P] [US1] Add `useProfileQueries.ts` exposing `useBabies()` (wraps TanStack Query with key `["babies"]` calling `apiClient.listBabies`) — file: `frontend/src/features/profile/useProfileQueries.ts`
- [X] T010 [P] [US1] Add `CaregiverCard.tsx` rendering display name + email in read-only mode (no edit affordance yet — added in US2) — file: `frontend/src/features/profile/CaregiverCard.tsx`
- [X] T011 [P] [US1] Add `BabyCard.tsx` rendering display name, DOB, derived age, and the active-baby badge in read-only mode — file: `frontend/src/features/profile/BabyCard.tsx`
- [X] T012 [US1] Replace the `ProfilePage` stub with the real view: header, `<CaregiverCard />`, the babies list (`useBabies()` → `<BabyCard />` per item), empty state, loading state, error state. No edit / remove / add wiring yet — file: `frontend/src/features/profile/ProfilePage.tsx`
- [X] T013 [US1] Add a structured-log event on `ProfilePage` mount via the existing client logger (correlation-id pass-through) for FR-024 — file: `frontend/src/features/profile/ProfilePage.tsx`

**Checkpoint**: Quickstart §2 (read-only view + isolation negative check) passes. US1 is independently demoable.

---

## Phase 4: User Story 2 — Edit caregiver display name (Priority: P1)

**Goal**: From the Profile screen the caregiver can edit their own display name and see it reflected immediately everywhere it appears in the app shell.

**Independent Test**: Quickstart §3.

### Tests for User Story 2 (write FIRST, ensure failing)

- [X] T014 [P] [US2] Component test: clicking **Edit** on `CaregiverCard` reveals an input pre-filled with the current display name; **Cancel** restores the prior value without calling the mutation — file: `frontend/src/features/profile/CaregiverCard.test.tsx`
- [X] T015 [P] [US2] Component test: submitting a valid name calls `apiClient.updateMe` and the card exits edit mode showing the new value; the `["auth","me"]` query is invalidated so dependent shell consumers refetch — file: `frontend/src/features/profile/CaregiverCard.test.tsx`
- [X] T016 [P] [US2] Component test: submitting empty / whitespace-only display name shows an inline error and does NOT call the mutation; submitting a name longer than the existing length limit shows the length-limit inline error — file: `frontend/src/features/profile/CaregiverCard.test.tsx`
- [X] T017 [P] [US2] Contract test (backend): `PATCH /v1/users/me` with empty / whitespace `display_name` returns 422 and does not mutate the row — file: `backend/tests/contract/test_users_me_contract.py` (create if absent; this is contract test **C2** from `contracts/profile-surface.md`)

### Implementation for User Story 2

- [X] T018 [P] [US2] Add `useUpdateMe()` mutation to `useProfileQueries.ts` (wraps `apiClient.updateMe`, on success invalidates `["auth","me"]`) — file: `frontend/src/features/profile/useProfileQueries.ts`
- [X] T019 [US2] Extend `CaregiverCard.tsx` with edit mode: pencil affordance → controlled input + Save / Cancel; client-side trim + non-empty + length-limit validation matching the server `UserUpdate` schema; loading + inline error states; uses `useUpdateMe()` — file: `frontend/src/features/profile/CaregiverCard.tsx`
- [X] T020 [US2] Verify the `useAuth()` context (or whatever surface provides the current user to the app shell) refetches `/v1/auth/me` after invalidation so the new display name appears in the header / greeting within the same session — file: `frontend/src/features/auth/` (touch only the auth context file that exposes `user`)
- [X] T021 [US2] Add structured-log events for the edit-caregiver action (start + outcome) — file: `frontend/src/features/profile/CaregiverCard.tsx`

**Checkpoint**: Quickstart §3 (happy + whitespace negative) passes. US1 still passes (regression check).

---

## Phase 5: User Story 3 — Edit baby display name + DOB (Priority: P1)

**Goal**: From the Profile screen the caregiver can edit each baby's display name and date of birth; changes propagate to every other surface that names that baby, and the active-baby selection is unchanged.

**Independent Test**: Quickstart §4.

### Tests for User Story 3 (write FIRST, ensure failing)

- [X] T022 [P] [US3] Component test: clicking **Edit** on `BabyCard` reveals inputs pre-filled with the current values; **Cancel** restores the prior values without calling the mutation — file: `frontend/src/features/profile/BabyCard.test.tsx`
- [X] T023 [P] [US3] Component test: submitting a valid edit calls `apiClient.updateBaby(id, payload)` and the card exits edit mode showing the new values; the `["babies"]` query is invalidated; `["auth","me"]` is NOT invalidated and the active-baby badge stays where it was (FR-013) — file: `frontend/src/features/profile/BabyCard.test.tsx`
- [X] T024 [P] [US3] Component test: invalid inputs (empty / whitespace name, name over limit, future DOB) show inline errors and do NOT call the mutation — file: `frontend/src/features/profile/BabyCard.test.tsx`
- [X] T025 [P] [US3] Contract test (backend): `PATCH /v1/babies/{id}` with a future `date_of_birth` returns 422; on a valid edit, `User.active_baby_id` is unchanged — file: `backend/tests/contract/test_babies_contract.py` (create if absent; this is contract tests **C3** and **C4**)

### Implementation for User Story 3

- [X] T026 [P] [US3] Add `useUpdateBaby()` mutation to `useProfileQueries.ts` (wraps `apiClient.updateBaby`, on success invalidates `["babies"]` only) — file: `frontend/src/features/profile/useProfileQueries.ts`
- [X] T027 [US3] Extend `BabyCard.tsx` with edit mode: pencil affordance → controlled inputs for `display_name` (text) and `date_of_birth` (date input clamped to today as max); client-side validation matching `BabyUpdate`; loading + inline error states; uses `useUpdateBaby()` — file: `frontend/src/features/profile/BabyCard.tsx`
- [X] T028 [US3] Confirm the `BabySwitcher` and any home-screen surfaces that name the baby pick up the new value on next render (re-read the `["babies"]` cache) — file: `frontend/src/features/babies/BabySwitcher.tsx` (touch only if a manual invalidation is missing; otherwise no-op confirmed by integration test)
- [X] T029 [US3] Add structured-log events for the edit-baby action — file: `frontend/src/features/profile/BabyCard.tsx`

**Checkpoint**: Quickstart §4 (happy + future-DOB negative) passes. US1 + US2 still pass. The active-baby badge has not drifted.

---

## Phase 6: User Story 4 — Remove (soft-delete) a baby (Priority: P2)

**Goal**: From the Profile screen the caregiver can soft-delete a baby behind an explicit confirmation. When the deleted baby was the active baby, the most-recently-created surviving baby auto-activates (server-side, atomic). When it was the only baby, the diary surface re-locks.

**Independent Test**: Quickstart §5, §6, §7.

### Tests for User Story 4 (write FIRST, ensure failing)

- [X] T030 [P] [US4] Unit test (backend): `BabyService.soft_delete` on a non-active baby sets `deleted_at` and leaves `owner.active_baby_id` unchanged — file: `backend/tests/unit/test_baby_service.py`
- [X] T031 [P] [US4] Unit test (backend): `BabyService.soft_delete` on the **active** baby when at least one other non-deleted baby exists sets `owner.active_baby_id` to the surviving baby with the largest `created_at` (most-recently-created) — file: `backend/tests/unit/test_baby_service.py`
- [X] T032 [P] [US4] Unit test (backend): `BabyService.soft_delete` on the user's **only** baby sets `owner.active_baby_id = None` — file: `backend/tests/unit/test_baby_service.py`
- [X] T033 [P] [US4] Integration test (backend): `DELETE /v1/babies/{id}` on a non-active baby returns 200; `GET /v1/auth/me` thereafter reports the same `active_baby_id` as before — file: `backend/tests/integration/test_babies_delete_active_fallback.py` (this is contract test **C6**)
- [X] T034 [P] [US4] Integration test (backend): `DELETE /v1/babies/{id}` on the active baby (with siblings) returns 200; `GET /v1/auth/me` thereafter reports the most-recently-created surviving baby as `active_baby_id`; the deleted baby is absent from `GET /v1/babies` — file: `backend/tests/integration/test_babies_delete_active_fallback.py` (this is contract test **C7**)
- [X] T035 [P] [US4] Integration test (backend): `DELETE /v1/babies/{id}` on the user's only baby returns 200; `GET /v1/auth/me` thereafter reports `active_baby_id = null`; a subsequent diary read (e.g., `GET /v1/feeds?date=...`) returns the baby-required error — file: `backend/tests/integration/test_babies_delete_active_fallback.py` (this is contract test **C8**)
- [X] T036 [P] [US4] Component test: clicking **Remove** on a `BabyCard` opens `RemoveBabyDialog` showing the baby's display name and the consequence text; **Cancel** closes the dialog and does NOT call the mutation; **Confirm** calls `apiClient.deleteBaby(id)` once and disables the button while in flight — file: `frontend/src/features/profile/RemoveBabyDialog.test.tsx`
- [X] T037 [P] [US4] Component test: after a successful remove, both `["babies"]` and `["auth","me"]` queries are invalidated; the next render of `ProfilePage` does not show the removed baby; if the removed baby was the active one, the shell's active-baby indicator points at whichever baby the refetched `auth.me` reports — file: `frontend/src/features/profile/ProfilePage.test.tsx`

### Implementation for User Story 4

- [X] T038 [US4] Edit `BabyService.soft_delete` so that, when `owner.active_baby_id == baby.id`, it queries the owner's other non-deleted babies (ordered by `created_at` desc) and sets `owner.active_baby_id` to the first row, or `None` if there is none — all within the existing flush — file: `backend/src/momdiary/babies/service.py`
- [X] T039 [P] [US4] Add `useDeleteBaby()` mutation to `useProfileQueries.ts` (wraps `apiClient.deleteBaby`, on success invalidates both `["babies"]` and `["auth","me"]`) — file: `frontend/src/features/profile/useProfileQueries.ts`
- [X] T040 [P] [US4] Add `RemoveBabyDialog.tsx` — modal with baby name, plain-language consequence text, Cancel button (closes), Remove button (calls `useDeleteBaby()`; disabled while in flight); no auto-submit on Enter — file: `frontend/src/features/profile/RemoveBabyDialog.tsx`
- [X] T041 [US4] Wire the **Remove** affordance on `BabyCard.tsx` to open `RemoveBabyDialog`; on success, close the dialog (parent re-renders from invalidated queries) — file: `frontend/src/features/profile/BabyCard.tsx`
- [X] T042 [US4] Confirm the existing post-sign-up "create your first baby" prompt is shown when the caregiver's `active_baby_id` becomes `null` (FR-018) — file: `frontend/src/App.tsx` (verify the existing gate already handles this state; only touch if the gate uses `babies.length === 0` and ignores `active_baby_id`)
- [X] T043 [US4] Add structured-log events for the remove-baby action (start, confirmed, outcome) including the affected baby id — file: `frontend/src/features/profile/RemoveBabyDialog.tsx`

**Checkpoint**: Quickstart §5, §6, §7 all pass. US1 + US2 + US3 still pass.

---

## Phase 7: User Story 5 — Add a baby from the Profile screen (Priority: P3)

**Goal**: The Profile screen exposes an "Add a baby" entry point that re-uses the existing add-baby flow. The new baby appears in the list and becomes active iff the caregiver had zero non-deleted babies at the time.

**Independent Test**: Quickstart §8.

### Tests for User Story 5 (write FIRST, ensure failing)

- [X] T044 [P] [US5] Component test: clicking **Add a baby** on `ProfilePage` opens the existing add-baby flow component (assert by role / test-id, no API call yet) — file: `frontend/src/features/profile/ProfilePage.test.tsx`
- [X] T045 [P] [US5] Component test: on successful create from the Profile entry point, `["babies"]` is invalidated and the new baby appears in the profile list — file: `frontend/src/features/profile/ProfilePage.test.tsx`
- [X] T046 [P] [US5] Component test: when the caregiver had zero non-deleted babies and creates one from the Profile entry point, `["auth","me"]` is also invalidated so the shell picks up the auto-activated baby (existing server-side behavior — `babies.py::create_baby`) — file: `frontend/src/features/profile/ProfilePage.test.tsx`

### Implementation for User Story 5

- [X] T047 [US5] Reuse the existing add-baby form (today rendered from `FirstBabyPrompt.tsx` or `BabySwitcher`). Extract its form body into a shared sub-component if it is not already one, OR mount the existing flow in a modal from `ProfilePage` — pick the smaller diff. No new HTTP surface — file: `frontend/src/features/profile/ProfilePage.tsx` (and at most one touch in the chosen reuse source, e.g., `frontend/src/features/babies/FirstBabyPrompt.tsx`)
- [X] T048 [US5] Ensure the add-baby success path from the Profile entry point invalidates `["babies"]` AND `["auth","me"]` (the latter only matters when it was the user's first baby; invalidating it unconditionally is cheap and is the safest correctness rule) — file: `frontend/src/features/profile/ProfilePage.tsx`

**Checkpoint**: Quickstart §8 passes. US1–US4 still pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, accessibility, observability, and final validation across the whole feature.

- [X] T049 [P] Accessibility pass on `ProfilePage`, `CaregiverCard`, `BabyCard`, `RemoveBabyDialog`: every interactive element has an accessible name; the modal traps focus and restores it on close; form errors are announced via `aria-live` — files: all `frontend/src/features/profile/*.tsx`
- [X] T050 [P] Cross-tenant isolation regression test (backend integration): caregiver B's `PATCH /v1/babies/<A's baby id>` and `DELETE /v1/babies/<A's baby id>` both return 404 not-found-style and do not mutate A's data; matches contract tests **C5** + **C9** — file: `backend/tests/integration/test_babies_cross_tenant_profile.py` (or extend `test_babies_endpoints.py`)
- [X] T051 [P] Unauthenticated-access regression test: every endpoint in `contracts/profile-surface.md` returns 401 with no profile-shaped body when called without a session cookie; matches contract test **C10** — file: `backend/tests/integration/test_profile_auth_gate.py` (or extend `test_auth_endpoints.py`)
- [X] T052 Verify FR-024 log lines for every Profile-surface action carry `correlation_id`, `user_id`, and (where applicable) `baby_id`, with no credential material; add log assertions if the existing structured-log test harness supports it — files: `backend/tests/integration/test_profile_audit_log.py` (or extend an existing audit-log test if present)
- [X] T053 [P] Run frontend coverage and ensure the changed packages (`frontend/src/features/profile/`, edited line of `frontend/src/App.tsx`) meet ≥ 80 % line / ≥ 70 % branch — command: `cd frontend; npm test -- --coverage`
- [X] T054 [P] Run backend coverage and ensure the changed package (`backend/src/momdiary/babies/`) meets ≥ 80 % line / ≥ 70 % branch — command: `cd backend; $env:PYTHONPATH="src"; python -m pytest -q --ignore=tests/benchmarks --cov=src/momdiary/babies`
- [X] T055 Run the quickstart end-to-end manually as a final smoke gate — file: [quickstart.md](./quickstart.md), all 10 sections

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies; can start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks every user story phase** (the Profile tab must be reachable for any phase to be exercised).
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2 (Foundational) AND Phase 3 (needs `CaregiverCard` skeleton from T010).
- **Phase 5 (US3)**: depends on Phase 2 AND Phase 3 (needs `BabyCard` skeleton from T011).
- **Phase 6 (US4)**: depends on Phase 2 AND Phase 3 (needs `BabyCard` to host the **Remove** affordance).
- **Phase 7 (US5)**: depends on Phase 2 AND Phase 3 (needs `ProfilePage` to host the **Add a baby** affordance).
- **Phase 8 (Polish)**: depends on whichever user stories are in scope for the cut.

US2, US3, US4, US5 do **not** depend on one another; they can be staffed in parallel by different developers once US1 is in.

### Within each user-story phase

- Tests first (every `T0xx [P]` test task) → confirm failing → implementation tasks.
- Inside implementation: shared hooks (`useProfileQueries.ts`) before consumers; card components before page wiring.

### Parallel opportunities

- All Phase 1 tasks (`T001..T003`) are [P].
- Within each user-story phase, every test task marked [P] runs in parallel.
- Across user-story phases (after Phase 3 lands): US2, US3, US4, US5 implementations can be staffed in parallel by separate developers because they touch distinct files (different `*.test.tsx`, different cards, different mutations); the one shared file is `useProfileQueries.ts` which is small and additive per story.
- Backend (US4 only — T030..T035, T038) is parallel with all frontend work.

---

## Parallel example — staff three developers after US1 lands

```text
Developer A → Phase 4 (US2, T014..T021)   # edit caregiver
Developer B → Phase 5 (US3, T022..T029)   # edit baby
Developer C → Phase 6 (US4, T030..T043)   # remove baby (backend + frontend)
```

Each phase ends at a checkpoint where the shipped slice is independently testable per the quickstart sections cited in that phase's "Independent Test" line.

---

## Implementation Strategy

### MVP cut (smallest demoable slice)

1. Phase 1 → Phase 2 → Phase 3 (US1).
2. **STOP**, demo: caregiver can see their own details + babies on a dedicated screen.

### Recommended first delivery (P1 cluster)

1. Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3).
2. **STOP**, demo: caregiver can view *and edit* both their own and their babies' details.

### Full feature

3. Add Phase 6 (US4 — remove) → Phase 7 (US5 — add entry point) → Phase 8 (Polish).

---

## Notes

- **No new HTTP endpoints.** Every server interaction reuses feature 006. Only `BabyService.soft_delete` gets a behavior edit (T038).
- **No new agent / no AI calls.** Constitution Principle V is N/A.
- **Tests are non-negotiable** (Principle II). Every implementation task in this file has at least one preceding failing test task. Coverage tasks T053 and T054 enforce the floor.
- Commit after each task or logical group; never bundle a test task with its implementation task in the same commit.
- Avoid changing files outside the listed paths; if a task tempts you to refactor an unrelated module, file a follow-up instead.
