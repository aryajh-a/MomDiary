# Implementation Plan: Clerk-Powered Caregiver Authentication

**Branch**: `008-clerk-auth` | **Date**: 2026-05-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-clerk-auth/spec.md`

## Summary

Replace MomDiary's local email + Argon2id-password + HttpOnly-cookie auth (feature 006) with Clerk as the sole identity provider. The frontend mounts Clerk's prebuilt `<SignIn />` and `<SignUp />` components at in-app routes `/sign-in` and `/sign-up` (embedded, never redirecting off the MomDiary domain), and supplies a Clerk-issued short-lived JWT on every API request via `Authorization: Bearer <token>`. The backend stops issuing or validating its own session cookies; instead, a new FastAPI dependency verifies each request's Clerk JWT **networkless** against Clerk's JWKS (`well-known/jwks.json`), maps the `sub` claim (Clerk user ID) to an internal `users.id`, lazily provisions the MomDiary caregiver row on first sign-in, and enforces email-verification gating server-side on every write endpoint via a separate `require_verified_email` dependency that reads the JWT's `email_verified` custom claim. A Clerk webhook endpoint (`POST /v1/webhooks/clerk`, Svix-signed) handles `user.deleted` by cascade hard-deleting the caregiver row, every owned baby, and every diary entry. A single Alembic migration drops `user_sessions`, drops password columns from `users`, adds `clerk_user_id` (unique, not-null) and `email_verified_at`, and TRUNCATEs all pre-existing diary data per FR-012. No AI agent code is touched.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged), TypeScript 5.4 (frontend, unchanged).
**Primary Dependencies**:
- Backend (new): `clerk-backend-api ≥ 1.5.0` (official Clerk Python SDK; provides typed `authenticate_request` networkless JWT verification using JWKS), `svix ≥ 1.30.0` (Clerk webhook signature verification). Remove `argon2-cffi`.
- Backend (unchanged): FastAPI, SQLAlchemy 2.x async + `aiosqlite`, Alembic, Pydantic v2, `structlog`, `agent-framework==1.0.0rc6`, `agent-framework-azure-ai==1.0.0rc6`, `azure-identity`.
- Frontend (new): `@clerk/clerk-react ≥ 5.18.0`. Use its `<ClerkProvider>`, `<SignIn />`, `<SignUp />`, `<SignedIn>`, `<SignedOut>`, `<UserButton>`, `useAuth()`, `useUser()`. Replace the existing `useSession` hook.
- Frontend (unchanged): React 18, Vite 5, TanStack Query v5, Tailwind 3, `zod`, `date-fns` + `date-fns-tz`.
**Storage**: SQLite (`backend/momdiary.db`) via `sqlite+aiosqlite`. One new Alembic revision (`2026XXXX_008_clerk_users.py`).
**Testing**: `pytest` (unit + integration + contract), `pytest-asyncio`, `httpx.AsyncClient`. Clerk JWT validation tested with a locally-generated RSA key-pair + a fake JWKS endpoint served from a fixture (Constitution II: no live-model / no live-Clerk calls in CI). Frontend: `vitest` + `@testing-library/react` with `@clerk/testing` (vitest mock of `useAuth`).
**Target Platform**: Linux/macOS/Windows dev workstation; same deployment surface as the existing backend.
**Project Type**: Web application (backend + frontend already split).
**Performance Goals**: JWT verification p95 ≤ 5 ms (networkless, in-process JWKS cache; budget set by Constitution III's 2 s p95 minus everything else). Sign-in end-to-end (button click → baby page) p95 ≤ 10 s (SC-006). Webhook fan-out cascade completes within minutes (FR-015) — implemented as a synchronous SQL `DELETE ... WHERE baby_id IN (...)` chain inside a single transaction.
**Constraints**:
- Networkless JWT verification only; the request path MUST NOT call Clerk's REST API per request (latency budget).
- JWKS cached in-process with a TTL ≤ 1 h and a forced refresh on `kid` miss.
- No password material, no Clerk session tokens, no Google access tokens may ever appear in logs (FR-014, SC-005).
- Read endpoints stay open to unverified-email users with empty workspaces; **every** write endpoint MUST refuse them (FR-017).
- Email-verification state read from the JWT claim, NEVER from a client-supplied header (FR-009).
- Webhook handler MUST verify Svix signature before any DB write; replays MUST be idempotent (FR-015).
**Scale/Scope**: Single-tenant SQLite, low-thousands of caregivers, single uvicorn process. No replication.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-evaluated after Phase 1.*

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Code Quality & Maintainability | **Pass** | New `auth/clerk.py`, `auth/dependencies.py`, `auth/webhooks.py` carry docstrings and bounded function size. Lint/format CI gates apply. Dead code from feature 006 (`hasher.py`, `sessions.py`, the old `users.password_hash` column) is deleted, not commented out. |
| II | Testing Standards (NON-NEGOTIABLE) | **Pass** | Unit tests for JWT verifier (valid, expired, wrong-issuer, wrong-audience, unknown `kid`, tampered signature, missing claim), unverified-email gate, webhook signature verifier (valid, replay, wrong secret). Integration tests for every protected endpoint (auth required, baby-scope preserved, write-while-unverified rejected). Contract tests against `contracts/clerk-auth.openapi.yaml`. No live Clerk calls in CI; an `httpx.MockTransport` serves a fake JWKS document. Coverage floors inherited. |
| III | Performance Requirements | **Pass** | Networkless verification keeps per-request auth overhead ≤ 5 ms p95. JWKS cache eviction policy documented (Constitution III). A `tests/benchmarks/test_jwt_verify_perf.py` micro-benchmark guards regression. |
| IV | Modular Architecture | **Pass** | New `momdiary.auth` is a single module with a stated public interface (`get_current_user`, `require_verified_email`, `verify_clerk_jwt`); the rest of the codebase imports only through it. No cyclic deps. The `auth/sessions.py` and `auth/hasher.py` modules from feature 006 are removed in the same change so the seam stays clean. |
| V | MAF First (NON-NEGOTIABLE) | **N/A for new code** | This feature adds no new AI agent and changes no existing agent contract. The diary agent (`agents/diary_agent.py`), the chat session store, and `/v1/entries` MAF dispatch are untouched in shape; they simply receive the resolved `user_id` from the new dependency. |

**Gate result**: **PASS** — no Complexity Tracking entries required. Re-evaluated post-Phase 1: still PASS (Clerk SDK + Svix are the only new third-party deps, both pinned; both replace strictly larger surface area).

## Project Structure

### Documentation (this feature)

```text
specs/008-clerk-auth/
├── plan.md                            # this file
├── spec.md                            # /speckit.specify + /speckit.clarify output
├── research.md                        # Phase 0 — JWT verification, JWKS caching, webhook design
├── data-model.md                      # Phase 1 — users table delta, dropped tables, cascade rules
├── quickstart.md                      # Phase 1 — end-to-end manual validation script
├── contracts/
│   ├── clerk-auth.openapi.yaml        # New auth-shaped endpoints (/v1/users/me, webhook)
│   └── existing-endpoint-changes.md   # Cross-cutting changes to features 001/003/006/007
├── checklists/
│   └── requirements.md                # /speckit.checklist output (already produced)
└── tasks.md                           # /speckit.tasks output (NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/momdiary/
│   ├── api/
│   │   ├── main.py                            # MODIFIED — drop session-cookie middleware;
│   │   │                                      #            mount Clerk JWT dependency;
│   │   │                                      #            register webhook router
│   │   ├── auth.py                            # DELETED — replaced by Clerk; no /v1/auth/* endpoints
│   │   ├── users.py                           # MODIFIED — /v1/users/me reads from Clerk JWT
│   │   ├── babies.py                          # UNCHANGED in shape; depends on get_current_user
│   │   ├── entries.py                         # MODIFIED — write routes add require_verified_email
│   │   ├── feeds.py                           # MODIFIED — write routes add require_verified_email
│   │   ├── sleeps.py                          # MODIFIED — write routes add require_verified_email
│   │   ├── poops.py                           # MODIFIED — write routes add require_verified_email
│   │   ├── appointments.py                    # MODIFIED — write routes add require_verified_email
│   │   ├── dependencies.py                    # MODIFIED — get_current_user now Clerk-based
│   │   └── webhooks.py                        # NEW — POST /v1/webhooks/clerk (Svix-verified)
│   ├── auth/
│   │   ├── __init__.py                        # MODIFIED — re-export get_current_user, require_verified_email
│   │   ├── clerk.py                           # NEW — JWKS cache + verify_clerk_jwt() (networkless)
│   │   ├── dependencies.py                    # REWRITTEN — get_current_user (lazy-provisions row),
│   │   │                                      #            require_verified_email
│   │   ├── webhooks.py                        # NEW — handle user.deleted, user.updated (Svix verify)
│   │   ├── context.py                         # UNCHANGED — request-scoped user context container
│   │   ├── hasher.py                          # DELETED
│   │   ├── sessions.py                        # DELETED
│   │   ├── middleware.py                      # MODIFIED — no cookie parsing; only correlation-ID
│   │   └── README.md                          # REWRITTEN — Clerk model documented
│   ├── models/
│   │   └── orm.py                             # MODIFIED — drop UserSession class; drop password_hash,
│   │                                          #            password_updated_at columns;
│   │                                          #            add clerk_user_id (unique, not-null),
│   │                                          #            email_verified_at
│   ├── schemas/
│   │   ├── auth.py                            # MODIFIED — keep User-facing DTOs; drop login/register
│   │   └── webhooks.py                        # NEW — typed Clerk webhook payloads (user.deleted, ...)
│   ├── services/
│   │   └── chat_session_store.py              # UNCHANGED — key is still (user_id, baby_id, session_id);
│   │                                          #             user_id is now the resolved internal UUID
│   ├── config.py                              # MODIFIED — add CLERK_SECRET_KEY, CLERK_JWT_ISSUER,
│   │                                          #            CLERK_JWT_AUDIENCE, CLERK_WEBHOOK_SECRET
│   └── db/migrations/versions/
│       └── 2026XXXX_008_clerk_users.py        # NEW Alembic revision: drop user_sessions table,
│                                              #     drop password columns on users,
│                                              #     add clerk_user_id + email_verified_at,
│                                              #     TRUNCATE every diary table (FR-012)
└── tests/
    ├── unit/
    │   ├── test_clerk_jwt_verifier.py
    │   ├── test_clerk_webhook_verifier.py
    │   └── test_email_verification_gate.py
    ├── integration/
    │   ├── test_auth_required.py              # every protected endpoint returns 401 without JWT
    │   ├── test_users_me_lazy_provision.py
    │   ├── test_write_gating_unverified.py
    │   ├── test_webhook_user_deleted_cascade.py
    │   └── test_baby_scoping_preserved.py
    ├── contract/
    │   └── test_clerk_auth_contract.py
    └── benchmarks/
        └── test_jwt_verify_perf.py

frontend/
├── src/
│   ├── App.tsx                                # MODIFIED — wrap in <ClerkProvider>; add routes
│   │                                          #            /sign-in, /sign-up; gate protected routes
│   │                                          #            with <SignedIn>/<SignedOut>
│   ├── features/
│   │   └── auth/                              # REWRITTEN
│   │       ├── SignInPage.tsx                 # renders <SignIn routing="path" path="/sign-in" />
│   │       ├── SignUpPage.tsx                 # renders <SignUp routing="path" path="/sign-up" />
│   │       ├── RequireAuth.tsx                # uses <SignedIn>/<RedirectToSignIn />
│   │       ├── useClerkSession.ts             # thin wrapper over useAuth()
│   │       └── VerifyEmailBanner.tsx          # NEW — shown when isSignedIn && !user.primaryEmailAddress.verified
│   ├── shared/
│   │   └── apiClient.ts                       # MODIFIED — inject `Authorization: Bearer ${await getToken()}`
│   │                                          #            on every fetch; on 401 → trigger sign-in redirect
│   └── tests/
│       ├── SignInPage.test.tsx
│       ├── apiClient.auth.test.tsx
│       └── VerifyEmailBanner.test.tsx
└── package.json                               # MODIFIED — add @clerk/clerk-react
```

**Structure Decision**: Web application with existing `backend/` + `frontend/` split (matches features 002, 006, 007). Backend gets one new module (`auth/clerk.py`), one new router (`api/webhooks.py`), and an Alembic migration; the legacy local-auth code paths (`auth/hasher.py`, `auth/sessions.py`, `api/auth.py`, `user_sessions` table, password columns) are deleted in the same change. Frontend replaces its in-house auth pages with Clerk's prebuilt components and switches the API client from cookie auth to bearer-token auth.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| — | — | — |
