# Implementation Plan: Baby Profile Detail Screen

**Branch**: `010-baby-profile` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-baby-profile/spec.md`

## Summary

Add a dedicated **Baby Profile** screen, reachable by tapping a baby in the
existing Profile list, that shows the baby's identity (name, age, born date),
gender, date of birth, weight, and height, plus an **Edit profile**
affordance. Multi-baby aware.

This requires:

1. **Backend, additive**: three nullable columns on `babies`
   (`gender`, `weight_kg`, `height_cm`) **plus a `growth_measurements` table**
   for weight/height history (two Alembic migrations: `0006`, `0007`), and an
   extended `PATCH /v1/babies/{id}` (+ extended `BabyPublic` with a growth
   summary). **No new endpoint** — the profile reads the baby (incl. growth
   summary) from the existing `GET /v1/babies` list cache; the PATCH also logs
   the measurement.
2. **Frontend, new surface**: a `BabyProfilePage` (view + edit + growth card)
   under `features/profile/`, extended zod/types, and a tap-to-open navigation
   from the Profile list.

**In scope (2026-06-07)**: weight/height **growth history + delta + "last
measured"** (the 2026-06-05 "single snapshot" reduction is reversed).
**Deferred to v2**: allergies, birth weight, birth height. **Excluded**: head
circumference, blood type (HIPAA). **No new agent**, **no photo upload**.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 (frontend).
**Primary Dependencies**: existing only — FastAPI, SQLAlchemy 2 async +
`aiosqlite`, Alembic, Pydantic v2, `structlog` (backend); React 18, Vite 5,
TanStack Query v5, Tailwind 3, `zod`, `date-fns` (frontend). **No new packages.**
**Storage**: Postgres (asyncpg); **three new `babies` columns + one new
`growth_measurements` table across two Alembic migrations** (`0006`, `0007`).
**Testing**: pytest (backend, `PYTHONPATH=src`), Vitest + RTL (frontend).
**Target Platform**: Web, mobile-first, existing max-width app frame.
**Project Type**: Web application (`backend/` + `frontend/`).
**Performance Goals**: profile open ≤ 1 s P95 (served from cache); edit
round-trip ≤ 2 s P95 (spec SC-001/SC-002) — single-row read/write.
**Constraints**:
- Strict per-`(user_id, baby_id)` isolation; the extended PATCH reuses
  `BabyService.get_owned` and MUST NOT regress isolation (404 on non-owned).
- New columns nullable; existing baby rows stay valid with no backfill.
- Weight/height stored in display units (kg/cm); no conversion (SC-005 trivially holds).

## Constitution Check

Mapped against constitution v1.0.0 (`/.specify/memory/constitution.md`).

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Maintainability | PASS | Reuses module boundaries: `models/orm.py`, `schemas/babies.py`, `babies/service.py`, `api/babies.py`, `features/profile/`. Net new code is one frontend page + one migration + small schema/service edits. |
| II. Testing Standards (NON-NEGOTIABLE) | PASS | Tests authored before implementation: integration (extended PATCH happy + validation + ownership 404 + active-baby-unchanged), migration (existing rows survive), frontend component/integration (view, edit, isolation between babies, round-trip). No live model calls. |
| III. Performance Requirements | PASS | Single-row SQLite read/write; profile read is served from the already-loaded list cache. Trivially under 2 s P95. |
| IV. Modular Architecture | PASS | One new table (`growth_measurements`) reusing the existing `BabyService`; no new service class or route. The new frontend page lives in the existing `features/profile/` folder and accesses the backend only via the existing typed `apiClient`. |
| V. Microsoft Agent Framework First (NON-NEGOTIABLE) | N/A | No agent, tool, prompt, or orchestration added or modified. |

**Gate result**: PASS (Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/010-baby-profile/
├── plan.md                          # This file
├── spec.md                          # Feature spec
├── data-model.md                    # 4 new babies columns
├── contracts/
│   └── baby-profile-api.md          # Extended BabyPublic + PATCH
└── checklists/
    └── requirements.md              # Spec-quality checklist
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 0006_baby_profile_fields.py          # NEW migration (3 nullable columns)
└── src/momdiary/
    ├── models/orm.py                        # EDIT: 4 nullable columns on Baby
    ├── schemas/babies.py                    # EDIT: extend BabyPublic + BabyUpdate (Pydantic enums/ranges)
    ├── babies/service.py                    # EDIT: persist the 4 new attrs in update()
    └── api/babies.py                        # EDIT: PATCH passes new fields through (no new route)

backend/tests/
└── integration/test_baby_profile.py         # NEW: extended PATCH happy + validation + 404 + active-baby-unchanged + migration survival

frontend/
└── src/
    ├── shared/types.ts                      # EDIT: extend babySchema + babyUpdateSchema; add gender enum
    └── features/profile/
        ├── BabyProfilePage.tsx              # NEW: detail screen (view + edit modes)
        ├── babyProfileFormat.ts             # NEW: age/born/weight/height display helpers
        ├── ProfilePage.tsx                  # EDIT: baby row → open BabyProfilePage (internal state)
        ├── BabyCard.tsx                     # EDIT: make the baby row tappable
        └── BabyProfilePage.test.tsx         # NEW: component/integration tests
```

**Structure Decision**: existing web-app layout. Backend gains two migrations
and one new table (`growth_measurements`) plus edits to existing files (no new
module, no new service class, no new route). Frontend gains one page (view +
edit + growth card in a single component, mirroring how `BabyCard` already
co-locates view + edit today) inside `features/profile/`.
Navigation stays in the current `useState`-based view pattern: `ProfilePage`
holds which baby is open and renders `BabyProfilePage`; no `App.tsx` change.

## Phasing (suggested implementation order)

- **Phase 0 — Data foundation**: 3 `babies` columns (Alembic `0006`) +
  `growth_measurements` table (Alembic `0007`). Run `alembic upgrade head`;
  confirm existing rows survive.
- **Phase 1 — View (US1)**: extend `BabyPublic`; frontend `BabyProfilePage`
  view mode + tap-to-open from the Profile list. Reads from the list cache.
- **Phase 2 — Edit (US2)**: extend `BabyUpdate` + `BabyService.update`;
  add edit mode to `BabyProfilePage` with validation; cache invalidation so the
  switcher/day-view reflect a rename.
- **Phase 3 — Polish**: placeholders for unset fields, inert photo button,
  isolation/auth regression tests, observability log line.

## Key Design Decisions

- **History via one table, current cached on the baby** *(2026-06-07)*: weight
  and height are a tracked series in `growth_measurements` (one row per
  measurement date, holding both values); `babies.weight_kg`/`height_cm` cache
  the latest row for cheap list reads. The profile shows current + ↑/↓ delta vs
  the previous measurement + "last measured". The PATCH write path upserts
  today's measurement — so there is still **no new endpoint, no new service
  class, and no measurement CRUD surface**. Head circumference is excluded.
  _(Supersedes the 2026-06-05 "snapshot, not history" decision below.)_
- **(Superseded) Snapshot, not history**: weight and height were two editable
  baby fields. No measurement table, no deltas, no "last measured".
  This removed a table, a service, a repository, and four CRUD endpoints from
  the original plan.
- **Store in display units (kg/cm)**: no base-unit conversion layer; what you
  see is what's stored, so the round-trip is lossless by construction (SC-005).
- **No new read endpoint**: the profile screen reads the selected baby from the
  already-loaded `GET /v1/babies` list cache; the only new server behavior is
  the extended PATCH. Smaller surface, fewer tests, same UX.
- **Validation in Pydantic**: the four new columns are range/enum-checked in
  the request schema; columns are added plain-nullable (no SQLite CHECK, no
  batch table-rebuild).
- **Photo deferred cleanly**: no `photo_url` column, no storage dependency; the
  camera button is a styled inert control matching the mockup.
- **Reuse existing Profile navigation**: no react-router screen added;
  `ProfilePage` opens the detail page via the existing view-switch pattern.

## Risks & Mitigations

- **R1 — Cross-baby bleed-through in cache** (FR-007): the profile page must
  render strictly the selected baby. *Mitigation*: pass the baby id and select
  from the `["babies"]` cache by id; a frontend test opens two babies in
  sequence and asserts no carryover.
- **R2 — Stale switcher after rename** (FR-015): *Mitigation*: the edit
  mutation invalidates `["babies"]` (and `["session"]` only if needed); covered
  by an integration test.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                              |
