# Implementation Plan: Profile Management (Caregiver & Babies)

**Branch**: `007-profile-management` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-profile-management/spec.md`

## Summary

Add a single Profile surface in the existing React app that lets a signed-in
caregiver view their own details (display name, sign-in email) and their
non-deleted babies, edit their own display name, edit each baby's display
name and date of birth, soft-delete a baby (with confirmation and active-baby
fallback), and reach the existing add-baby flow. **No new agent.** **No new
backend endpoints in the primary path** — every required server action is
already provided by feature 006 (`GET /v1/babies`, `PATCH /v1/babies/{id}`,
`DELETE /v1/babies/{id}`, `PATCH /v1/users/me`, `POST /v1/users/me/active-baby`).
The only backend follow-up is a small UX-affecting behavior change in the
soft-delete service path so the *most-recently-created surviving baby* is
auto-activated when the deleted baby was the active one (today the field is
cleared, forcing a manual switch). The frontend is responsible for the entire
new view + edit + remove + confirm UX, TanStack Query cache invalidation, and
the optimistic shell-name update.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged surface area); TypeScript 5.4 (frontend)
**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy 2.x async + `aiosqlite`, Alembic, Pydantic v2, `structlog`, `argon2-cffi` (existing — no new packages).
- Frontend: React 18, Vite 5, TanStack Query v5, Tailwind CSS 3, `zod`, `date-fns` (existing — no new packages).
**Storage**: SQLite (`backend/momdiary.db`); no new tables, no new columns, no Alembic migration.
**Testing**: pytest (backend), Vitest + React Testing Library (frontend, using the existing harness).
**Target Platform**: Web (mobile-first, the same orange-themed app shell used today). Same surface deploys unchanged to a future mobile wrapper.
**Project Type**: Web application (existing `backend/` + `frontend/` layout).
**Performance Goals**: Profile-screen open ≤ 1 s P95; edit save round-trip ≤ 2 s P95 (per spec SC-001..SC-005); aligns with constitution Principle III (interactive P95 ≤ 2 s).
**Constraints**:
- Strict data isolation: every Profile-surface call MUST be scoped to the authenticated caregiver and (where applicable) to a baby they own; this is already enforced by the existing dependencies (`CurrentUserDep`, baby-owner check in service layer) and MUST NOT regress.
- No new dependency, no new datastore, no new migration.
- No new agent — Constitution Principle V is not triggered by this feature (no AI invocation).
**Scale/Scope**: 1 caregiver, typically 1–3 babies; the list endpoint already returns all of them in a single call.

## Constitution Check

Mapped against constitution v1.0.0 (`/.specify/memory/constitution.md`):

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Maintainability | PASS | Reuses existing module boundaries (`features/babies`, `features/auth`, `api/users.py`, `api/babies.py`, `babies/service.py`). New code is one frontend feature folder (`features/profile/`) plus one tiny service edit. Naming, docstrings, and lint rules already enforced in CI. |
| II. Testing Standards (NON-NEGOTIABLE) | PASS | New tests required at three tiers: (a) unit — soft-delete fallback selection in `BabyService`; (b) integration — `DELETE /v1/babies/{id}` activates fallback baby; (c) frontend component/integration tests for view, edit caregiver, edit baby, remove with confirmation, and remove-the-active-baby fallback. Tests authored before implementation per principle. No live model calls; this feature has no AI. |
| III. Performance Requirements | PASS | All Profile-surface actions are single-row reads/writes against SQLite; trivially under the 2 s P95 budget. No streaming, no hot path touched. No benchmark required. |
| IV. Modular Architecture | PASS | New `frontend/src/features/profile/` is self-contained; cross-module access only via existing typed `apiClient` and the existing `useAuth()` context. No cyclic dependencies introduced. The backend edit is confined to `babies/service.py` (its public interface is unchanged: still `soft_delete(baby, owner=...)`). |
| V. Microsoft Agent Framework First (NON-NEGOTIABLE) | N/A | No AI agent, tool, prompt, or orchestration is introduced or modified. No prerelease pinning question raised. |

**Gate result**: PASS (no violations; Complexity Tracking left empty).

## Project Structure

### Documentation (this feature)

```text
specs/007-profile-management/
├── plan.md                          # This file
├── research.md                      # Phase 0 — decisions & rationale
├── data-model.md                    # Phase 1 — entities (referenced from 006)
├── quickstart.md                    # Phase 1 — how to exercise the feature end-to-end
├── contracts/
│   └── profile-surface.md           # Phase 1 — endpoint contracts consumed (all pre-existing)
├── checklists/
│   └── requirements.md              # Spec-quality checklist (already authored)
└── spec.md                          # Feature spec
```

### Source Code (repository root)

```text
backend/
└── src/momdiary/
    ├── babies/
    │   └── service.py               # EDIT: soft_delete picks fallback active baby instead of nulling
    └── tests/ (under backend/tests/)
        ├── unit/test_baby_service.py            # NEW or EXTEND: fallback-selection cases
        └── integration/test_babies_delete.py    # NEW or EXTEND: DELETE activates fallback

frontend/
└── src/
    ├── features/
    │   └── profile/                            # NEW feature module
    │       ├── ProfilePage.tsx                 # Top-level screen (view + entry points)
    │       ├── CaregiverCard.tsx               # View + edit display name + read-only email
    │       ├── BabyCard.tsx                    # View + edit display name + DOB; remove affordance
    │       ├── RemoveBabyDialog.tsx            # Explicit destructive confirmation
    │       ├── useProfileQueries.ts            # TanStack Query hooks (list babies, mutations)
    │       └── ProfilePage.test.tsx            # Component + integration tests
    ├── shared/
    │   └── (no changes — apiClient & types reused as-is)
    └── App.tsx                                 # EDIT: wire Profile tab → ProfilePage view
```

**Structure Decision**: Use the existing web-app layout (`backend/` + `frontend/`).
This feature adds **one new frontend feature folder** (`features/profile/`),
**one tiny backend service edit** (`babies/service.py`), and **one App-shell
wire-up** (`App.tsx`). No new top-level packages, no new shared modules, no
new API routes.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                              |
