# Implementation Plan: User & Baby Profiles with Authentication

**Branch**: `006-user-and-baby-profiles` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-user-and-baby-profiles/spec.md`

## Summary

Introduce caregiver accounts (email + Argon2id-hashed password, rolling 30-day HttpOnly session cookies) and baby profiles (single-owner per caregiver in v1), and rewire every existing diary endpoint to be gated by an authenticated session and scoped to one resolved "active baby". A single Alembic migration creates the new tables, hard-deletes pre-existing diary rows (acceptable per FR-018 because the data is pre-production), and adds a `baby_id NOT NULL` FK to every existing entry table. The in-memory chat session store from feature 003 is repartitioned by `(user_id, baby_id, session_id)` so that turns from one baby cannot influence another. No new AI agent is introduced; the existing `/v1/entries` MAF dispatch and `/v1/chatentry/` direct-LLM path are preserved and simply gain auth + scoping.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged), TypeScript 5.4 (frontend, unchanged)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x async + `aiosqlite`, Alembic, Pydantic v2, `structlog`, **`argon2-cffi ≥ 23.1.0` (new)**. Frontend uses the existing React 18 + Vite 5 + TanStack Query v5 + Tailwind 3 + zod stack; no new packages required.
**Storage**: SQLite (`backend/momdiary.db`) via `sqlite+aiosqlite`. Schema delta managed by Alembic (one new revision).
**Testing**: `pytest` (unit + integration + contract), `pytest-asyncio`, `httpx.AsyncClient` against the FastAPI app, `vitest` + `@testing-library/react` on the frontend, micro-benchmark under `tests/benchmarks/test_auth_perf.py`.
**Target Platform**: Linux/macOS/Windows dev workstation; same deployment surface as the existing backend.
**Project Type**: Web application (backend + frontend already split).
**Performance Goals**: Sign-up & sign-in p95 ≤ 2 s end-to-end (Constitution III, SC-002). Argon2id verification budgeted at 50–100 ms per call on dev hardware. List-endpoint p95 unchanged after adding `baby_id` filter (composite indexes ensure no regression).
**Constraints**: Server-side session invalidation MUST be possible on sign-out (FR-003); zero cross-tenant data leakage (SC-003); ownership probes MUST return 404 (FR-016, never 403); credential rejections MUST be uniform (FR-006); password material MUST never be logged or returned.
**Scale/Scope**: Small (single-tenant SQLite, low-thousands of caregivers). No load-balancing or replication concerns in v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-evaluated after Phase 1.*

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Code Quality & Maintainability | **Pass** | New `auth/` and `babies/` modules carry docstrings; each function bounded; lint/format CI gates apply. |
| II | Testing Standards (NON-NEGOTIABLE) | **Pass** | Unit tests for hasher, session-token issuance, ownership resolver. Integration tests for every new endpoint and for `baby_id` scoping on every retrofitted endpoint. Contract tests against `contracts/auth-and-profiles.openapi.yaml`. Coverage gates inherited. |
| III | Performance Requirements | **Pass** | SC-002 = 2 s p95 (within the 2 s constitutional p95). Argon2id parameters chosen so verification ≤ 100 ms; a `tests/benchmarks/test_auth_perf.py` benchmark guards regression. |
| IV | Modular Architecture | **Pass** | `momdiary.auth` (hashing + session service + middleware), `momdiary.babies` (ownership resolver + CRUD), and `momdiary.auth.dependencies` are pluggable and decoupled from existing dispatchers. No new cyclic dependencies. |
| V | MAF First (NON-NEGOTIABLE) | **N/A for new code** | This feature adds no new AI agent and changes no existing agent contract. The existing MAF dispatch (`/v1/entries`) and direct-LLM dispatch (`/v1/chatentry/`) remain on their respective stacks; both simply gain a session dependency and a baby-scoping resolver. |

**Gate result**: PASS — no Complexity Tracking entries required. (Re-evaluated post-Phase 1 below.)

## Project Structure

### Documentation (this feature)

```text
specs/006-user-and-baby-profiles/
├── plan.md                            # this file
├── spec.md                            # /speckit.specify + /speckit.clarify output
├── research.md                        # Phase 0 — algorithmic & design decisions
├── data-model.md                      # Phase 1 — schemas, indexes, invariants
├── quickstart.md                      # Phase 1 — end-to-end manual validation script
├── contracts/
│   ├── auth-and-profiles.openapi.yaml # New endpoints
│   └── existing-endpoint-changes.md   # Cross-cutting changes to features 001/003/005
├── checklists/
│   └── requirements.md
└── tasks.md                           # /speckit.tasks output (NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/momdiary/
│   ├── api/
│   │   ├── main.py                    # mount new routers; install auth middleware
│   │   └── routes/
│   │       ├── auth.py                # NEW — /v1/auth/register|login|logout|me
│   │       ├── users.py               # NEW — /v1/users/me, /v1/users/me/active-baby
│   │       ├── babies.py              # NEW — /v1/babies, /v1/babies/{id}
│   │       ├── entries.py             # MODIFIED — Depends(get_current_user, get_active_baby)
│   │       ├── chatentry.py           # MODIFIED — same dependencies
│   │       ├── feeds.py               # MODIFIED — filter by baby_id
│   │       ├── sleeps.py              # MODIFIED — filter by baby_id
│   │       ├── poops.py               # MODIFIED — filter by baby_id
│   │       └── appointments.py        # MODIFIED — filter by baby_id
│   ├── auth/                          # NEW MODULE
│   │   ├── __init__.py
│   │   ├── hasher.py                  # Argon2id wrapper + constant-time enumeration-defense
│   │   ├── sessions.py                # SessionService: issue / validate / slide / revoke
│   │   ├── dependencies.py            # get_current_user, get_session, get_active_baby
│   │   ├── middleware.py              # cookie parser, structured-log enrichment (user_id, baby_id)
│   │   └── README.md                  # module contract (per Constitution IV)
│   ├── babies/                        # NEW MODULE
│   │   ├── __init__.py
│   │   ├── service.py                 # CRUD + soft-delete + active-baby fallback resolver
│   │   └── README.md
│   ├── models/orm.py                  # MODIFIED — add User, UserSession, Baby ORM classes;
│   │                                  #            add baby_id FK on Feed/Sleep/Poop/Appointment/
│   │                                  #            AppointmentNote/AgentInteraction
│   ├── schemas/                       # NEW Pydantic schemas mirroring contracts/
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── babies.py
│   ├── services/
│   │   ├── chat_session_store.py      # MODIFIED — key by (user_id, baby_id, session_id)
│   │   ├── entries_dispatcher.py      # MODIFIED — receive baby_id, set on writes
│   │   └── chatentry_dispatcher.py    # MODIFIED — same
│   └── db/migrations/versions/
│       └── 2026XXXX_006_users_babies.py  # NEW Alembic revision
└── tests/
    ├── unit/
    │   ├── test_argon2_hasher.py
    │   ├── test_session_service.py
    │   └── test_baby_resolver.py
    ├── integration/
    │   ├── test_auth_endpoints.py
    │   ├── test_users_endpoints.py
    │   ├── test_babies_endpoints.py
    │   ├── test_entries_scoping.py
    │   ├── test_chatentry_scoping.py
    │   └── test_list_endpoints_scoping.py
    ├── contract/
    │   └── test_auth_and_profiles_contract.py
    └── benchmarks/
        └── test_auth_perf.py

frontend/
├── src/
│   ├── features/
│   │   ├── auth/                      # NEW
│   │   │   ├── LoginPage.tsx
│   │   │   ├── SignupPage.tsx
│   │   │   ├── useSession.ts
│   │   │   └── RequireAuth.tsx
│   │   ├── babies/                    # NEW
│   │   │   ├── FirstBabyPrompt.tsx
│   │   │   ├── BabySwitcher.tsx
│   │   │   ├── useBabies.ts
│   │   │   └── RequireBaby.tsx
│   │   ├── chat/                      # MODIFIED — partition session-id per (user, baby)
│   │   └── chatentry/                 # MODIFIED — same
│   ├── shared/
│   │   ├── apiClient.ts               # MODIFIED — withCredentials, X-Active-Baby-Id, 401 handler
│   │   └── types.ts                   # MODIFIED — add User, Baby, Session zod schemas
│   └── App.tsx                        # MODIFIED — top-level <RequireAuth><RequireBaby>…</></>
└── tests/
    ├── auth.test.tsx
    ├── babies.test.tsx
    └── apiClient.test.ts
```

**Structure Decision**: Web application (`backend/` + `frontend/`), matching the existing repository layout. Two new backend modules (`momdiary.auth`, `momdiary.babies`) sit alongside the existing services; two new frontend feature folders (`features/auth/`, `features/babies/`) sit alongside the existing chat panels. No new top-level project is introduced.

## Phase 0 — Outline & Research

Status: **Complete**. See [research.md](./research.md). Eight decisions resolved:

1. Argon2id via `argon2-cffi` with PHC-string storage and on-verify rehash check.
2. Opaque random session tokens in an HttpOnly + Secure + SameSite=Lax cookie backed by a `user_sessions` table.
3. CSRF defense via `SameSite=Lax` + `Origin`/`Referer` check on state-changing endpoints (no double-submit token in v1).
4. Frontend auth via single TanStack Query cache entry `["session"]` + `<RequireAuth>` / `<RequireBaby>` wrappers + global 401 handler.
5. Single Alembic revision that creates the new tables, hard-deletes existing diary rows, then adds `baby_id NOT NULL` to those tables.
6. Chat session store keyed by `(user_id, baby_id, session_id)`; client emits a fresh session-id on baby switch.
7. Active-baby preference persisted as `users.active_baby_id`; `X-Active-Baby-Id` header overrides per-request only.
8. Uniform 401 envelope for all credential rejections, with constant-time dummy Argon2 verification on the registration collision path to defeat timing enumeration.

All initial `[NEEDS CLARIFICATION]` markers were already resolved during `/speckit.clarify`. No new ones surfaced during research.

## Phase 1 — Design & Contracts

Status: **Complete**. Artifacts:

- [data-model.md](./data-model.md) — `users`, `user_sessions`, `babies` schemas + indexes; `baby_id` column added to every existing entry table with table-specific composite indexes; authorization invariants enumerated.
- [contracts/auth-and-profiles.openapi.yaml](./contracts/auth-and-profiles.openapi.yaml) — OpenAPI 3.0.3 for the 9 new endpoints (`/v1/auth/register`, `/v1/auth/login`, `/v1/auth/logout`, `/v1/auth/me`, `/v1/users/me`, `/v1/users/me/active-baby`, `/v1/babies`, `/v1/babies/{id}` PATCH + DELETE).
- [contracts/existing-endpoint-changes.md](./contracts/existing-endpoint-changes.md) — Diff against features 001/003/005: every diary endpoint now requires the `momdiary_session` cookie, accepts the optional `X-Active-Baby-Id` header, returns 401/404/409 with the specified envelopes, and logs `user_id` + `baby_id` in structured records.
- [quickstart.md](./quickstart.md) — 9-step end-to-end manual validation script (apply migration → register → create baby → log entry → verify cross-tenant isolation → sign out → frontend smoke → reset).

### Re-evaluated Constitution Check (post-Phase 1)

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Code Quality | **Pass** | Module READMEs declared in the source tree (per IV); no complexity hot-spots introduced. |
| II | Testing | **Pass** | Test layout covers unit + integration + contract tiers per Principle II; no live-model dependence on the new path. |
| III | Performance | **Pass** | `tests/benchmarks/test_auth_perf.py` added (Argon2id verify + session-slide). List-endpoint regression covered by composite indexes; existing `test_chatentry_perf.py` budget unchanged. |
| IV | Modular Architecture | **Pass** | Two new modules with single responsibilities, accessed only through their stated APIs; no cyclic dependencies. |
| V | MAF First | **N/A** | Confirmed: no new agent code introduced; preserved on existing surfaces. |

**Final gate**: PASS. No Complexity Tracking entries required.

## Complexity Tracking

> No constitution violations to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| _(none)_ | — | — |
