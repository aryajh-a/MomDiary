---
description: "Task list for feature 010 — Baby Profile Detail Screen"
---

# Tasks: Baby Profile Detail Screen

**Input**: Design documents under `/specs/010-baby-profile/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [contracts/baby-profile-api.md](./contracts/baby-profile-api.md)

**Tests**: INCLUDED. The MomDiary constitution (v1.0.0, Principle II) makes tests non-negotiable and test-first. Every implementation task has at least one preceding failing test task. Coverage floor ≥ 80 % line / ≥ 70 % branch on changed packages.

**Organization**: Tasks are grouped by user story. Each user-story phase delivers an independently testable, demoable slice. There is no `quickstart.md`; the "Independent Test" lines cite the acceptance scenarios in [spec.md](./spec.md).

## Format: `[ID] [P?] [Story] Description (file path)`

- **[P]**: Parallelizable — different file, no dependency on incomplete tasks above it.
- **[Story]**: US1, US2. Setup, Foundational, and Polish phases have **no** story label.
- Every task includes an exact, repo-root-relative file path.

## Path Conventions

- **Backend**: `backend/src/momdiary/...`, tests under `backend/tests/{unit,integration}/`, `$env:PYTHONPATH="src"` to run.
- **Frontend**: `frontend/src/...`, co-located tests as `*.test.tsx` / `*.test.ts`.

## Key decisions baked into these tasks

- **Three new nullable `babies` columns** — `gender`, `weight_kg`, `height_cm` — **plus a new `growth_measurements` table** for weight/height history (2026-06-07). (Blood type removed for HIPAA; head circumference excluded.)
- **Weight/height are a tracked series** (`growth_measurements`, one row per measurement date) stored in display units (kg/cm) — no conversion. `babies.weight_kg`/`height_cm` cache the latest. The profile shows current + ↑/↓ delta vs previous + "last measured".
- **Validation in Pydantic** (plain nullable columns, no DB CHECK, no batch rebuild).
- **No new read endpoint** — the profile screen reads from the existing `GET /v1/babies` list cache; only `PATCH /v1/babies/{id}` changes.
- **No new agent / no AI** (Principle V N/A). **No photo upload** — inert placeholder only.
- **Navigation stays inside `features/profile/`** — `ProfilePage` holds which baby is open and renders `BabyProfilePage`; no `App.tsx` change.

---

## Phase 1: Setup

- [ ] T001 Create feature branch `010-baby-profile` off the current default branch (no code) — git
- [ ] T002 [P] Stub `BabyProfilePage` (renders only a heading + Back button) and a smoke test that mounts it — files: `frontend/src/features/profile/BabyProfilePage.tsx`, `frontend/src/features/profile/BabyProfilePage.test.tsx`

**Checkpoint**: `npm test` finds and passes the `BabyProfilePage` smoke test.

---

## Phase 2: Foundational (Data Layer — BLOCKING)

**Purpose**: Add the four nullable `babies` columns + migration. **Both user stories depend on this.**

### Tests (write FIRST, ensure failing)

- [ ] T003 [P] Migration test: applying `0005` upgrade against a DB seeded with a pre-010 baby row leaves that row valid and readable; `downgrade` then `upgrade` is idempotent — file: `backend/tests/integration/test_migration_0005.py`

### Implementation

- [ ] T004 Add the three nullable columns (`gender`, `weight_kg` Float, `height_cm` Float) to the `Baby` model — **no** DB CHECK constraints (validation is in Pydantic) — file: `backend/src/momdiary/models/orm.py`
- [ ] T005 Author Alembic revision `0006_baby_profile_fields` (down-revision `0005`): `add_column` ×3 on `babies` (plain nullable); `downgrade` drops the three columns — file: `backend/alembic/versions/0005_baby_profile_fields.py`
- [ ] T006 Back up `backend/momdiary.db`, run `alembic upgrade head`, confirm the schema; hard-restart the backend afterwards (OneDrive/uvicorn reload caveat) — command/file: `backend/`

**Checkpoint**: T003 passes; `alembic upgrade head` succeeds; existing babies still load.

---

## Phase 3: User Story 1 — View a baby's profile (Priority: P1) 🎯 MVP

**Goal**: Tapping a baby in the Profile list opens a dedicated, read-only profile screen showing identity (name, age, born date), gender, DOB, weight, and height, with explicit placeholders for unset fields.

**Independent Test**: spec.md US1 acceptance scenarios 1–5.

### Tests for User Story 1 (write FIRST, ensure failing)

- [ ] T007 [P] [US1] Integration test: `GET /v1/babies` returns the three new fields (gender, weight_kg, height_cm) on each baby, null when unset — file: `backend/tests/integration/test_baby_profile.py`
- [ ] T008 [P] [US1] Component test: `BabyProfilePage` renders name, derived age, born date, gender, DOB, weight (kg), height (cm), or a "Not set" placeholder per unset field, from a mocked baby — file: `frontend/src/features/profile/BabyProfilePage.test.tsx`
- [ ] T009 [P] [US1] Component test: tapping a baby in `ProfilePage` opens that baby's `BabyProfilePage`; opening baby A then returning and opening baby B shows only B's data (FR-007) — file: `frontend/src/features/profile/ProfilePage.test.tsx`

### Implementation for User Story 1

- [ ] T010 [US1] Extend `BabyPublic` with `gender`, `weight_kg`, `height_cm` (all nullable) and update the `_public(baby)` projection — files: `backend/src/momdiary/schemas/babies.py`, `backend/src/momdiary/api/babies.py`
- [ ] T011 [P] [US1] Extend `babySchema` with the three nullable fields and add the `genderSchema` enum — file: `frontend/src/shared/types.ts`
- [ ] T012 [P] [US1] Add `babyProfileFormat.ts` helpers: derived age string, born-date format, weight/height display (kg/cm), gender labels, "Not set" placeholder — file: `frontend/src/features/profile/babyProfileFormat.ts`
- [ ] T013 [US1] Build `BabyProfilePage` view mode: avatar placeholder + inert photo button, identity header, details list (gender, DOB, weight, height) with placeholders, Back affordance — file: `frontend/src/features/profile/BabyProfilePage.tsx`
- [ ] T014 [US1] Make `ProfilePage` open `BabyProfilePage` on baby tap (internal `selectedBabyId` state, reads the baby from the `["babies"]` list) and make the baby row tappable in `BabyCard` — files: `frontend/src/features/profile/ProfilePage.tsx`, `frontend/src/features/profile/BabyCard.tsx`

**Checkpoint**: spec US1 scenarios pass. The screen is demoable read-only.

---

## Phase 4: User Story 2 — Edit a baby's profile (Priority: P1)

**Goal**: From the profile screen, edit name, DOB, gender, weight, height; values persist, propagate to every surface naming the baby, and the active baby is unchanged.

**Independent Test**: spec.md US2 acceptance scenarios 1–7.

### Tests for User Story 2 (write FIRST, ensure failing)

- [ ] T015 [P] [US2] Integration test: `PATCH /v1/babies/{id}` with valid new fields returns the updated `BabyPublic`; future DOB, bad gender enum, and non-positive/out-of-range weight or height each return `422` and do not mutate; explicit `null` clears an optional field; `active_baby_id` is unchanged (FR-016); a non-owned baby returns `404` — file: `backend/tests/integration/test_baby_profile.py`
- [ ] T016 [P] [US2] Integration test: a weight/height value survives a save → re-read round-trip unchanged (SC-005) — file: `backend/tests/integration/test_baby_profile.py`
- [ ] T017 [P] [US2] Component test: Edit reveals a form pre-filled with current values; Cancel restores prior values without calling the mutation; a valid Save calls `apiClient.updateBaby`, exits edit mode, and invalidates `["babies"]`; invalid inputs show inline errors and do not call the mutation — file: `frontend/src/features/profile/BabyProfilePage.test.tsx`

### Implementation for User Story 2

- [ ] T018 [US2] Extend `BabyUpdate` with the three new optional fields, Pydantic-enforced (gender enum, weight/height `> 0` within sane bounds, all clearable to `null`); future-DOB already rejected — file: `backend/src/momdiary/schemas/babies.py`
- [ ] T019 [US2] Extend `BabyService.update` to persist the four new attributes; bump `updated_at` only on real change — file: `backend/src/momdiary/babies/service.py`
- [ ] T020 [US2] Add edit mode to `BabyProfilePage`: text/date/select/number inputs for all editable fields, client-side validation mirroring the server schema, clear-to-unset support, loading + inline error states, reusing the existing `useUpdateBabyMutation` (invalidates `["babies"]`) — file: `frontend/src/features/profile/BabyProfilePage.tsx`
- [ ] T021 [US2] Confirm a renamed baby propagates to `BabySwitcher` / day-view on next render via the `["babies"]` invalidation (touch only if a manual invalidation is missing) — file: `frontend/src/features/babies/BabySwitcher.tsx`

**Checkpoint**: spec US2 scenarios pass. US1 still passes. Active baby has not drifted.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Cross-tenant isolation regression (backend): caregiver B's `PATCH /v1/babies/<A's id>` returns `404` and mutates nothing — file: `backend/tests/integration/test_baby_profile.py`
- [ ] T023 [P] Accessibility pass on `BabyProfilePage`: every control has an accessible name; the inert photo button is labelled non-interactive; form errors use `role="alert"` + `aria-live` — file: `frontend/src/features/profile/BabyProfilePage.tsx`
- [ ] T024 [P] Verify FR-018 audit log line for the edit carries `correlation_id`, `user_id`, `baby_id`, no credential material — file: `backend/tests/integration/test_baby_profile.py`
- [ ] T025 [P] Backend coverage ≥ 80 % line / ≥ 70 % branch on changed packages — command: `cd backend; $env:PYTHONPATH="src"; python -m pytest -q --cov=src/momdiary/babies --cov=src/momdiary/api`
- [ ] T026 [P] Frontend coverage ≥ 80 % line / ≥ 70 % branch on `features/profile/` — command: `cd frontend; npm test -- --coverage`
- [ ] T027 Manual smoke: walk all spec US1–US2 acceptance scenarios end-to-end against a running backend + frontend — file: [spec.md](./spec.md)

---

## Dependencies & Execution Order

- **Phase 1 (Setup)**: no dependencies.
- **Phase 2 (Foundational / data layer)**: depends on Phase 1; **blocks both user stories**.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2 + Phase 3 (needs `BabyProfilePage` + extended schema/types).
- **Phase 5 (Polish)**: depends on US1 + US2.

### Within each phase

- Tests first → confirm failing → implementation.
- Backend: schema → service → route. Frontend: types/zod → format helpers → page → navigation wiring.
- Backend and frontend tracks within a story run in parallel (distinct files); the contract in [contracts/baby-profile-api.md](./contracts/baby-profile-api.md) is the seam.

---

## Implementation Strategy

### MVP cut (smallest demoable slice)

1. Phase 1 → Phase 2 → Phase 3 (US1).
2. **STOP**, demo: tap a baby → see its full profile (read-only).

### Full feature

3. Add Phase 4 (US2 — edit) → Phase 5 (Polish).

---

## Notes

- **Two Alembic migrations**: `0006` (3 additive nullable `babies` columns) and `0007` (new `growth_measurements` table). Runtime is Postgres; hard-restart the backend after `upgrade` (OneDrive/uvicorn reload caveat).
- **No new endpoint** — reads come from the existing `GET /v1/babies` list (now incl. the growth summary); only `PATCH /v1/babies/{id}` is extended, and it also logs today's measurement.
- **No new agent / no AI calls** — Constitution Principle V is N/A.
- **No photo storage** — the camera button is an inert labelled placeholder (FR-017).
- **Validation lives in Pydantic** for the new columns; no DB CHECK.
- **Tests are non-negotiable** (Principle II); never bundle a test task with its implementation task in the same commit.
- Keep changes within the listed paths; file a follow-up rather than refactoring unrelated modules.
