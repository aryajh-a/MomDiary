---
description: "Task list for feature 008 — Clerk-powered caregiver authentication"
---

# Tasks: Clerk-Powered Caregiver Authentication

**Input**: Design documents from `specs/008-clerk-auth/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/clerk-auth.openapi.yaml](./contracts/clerk-auth.openapi.yaml), [contracts/existing-endpoint-changes.md](./contracts/existing-endpoint-changes.md), [quickstart.md](./quickstart.md)

**Tests**: Included — Constitution Principle II (Testing Standards) is NON-NEGOTIABLE for this project. Every new behavior gets unit, integration, and contract coverage; tests are authored to fail before implementation lands.

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md). MVP = Phase 1 + Phase 2 + Phase 3 (US1).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Different file, no incomplete-dependency conflicts → safe to run in parallel.
- **[Story]**: User-story phase tasks only. Setup, Foundational, Polish phases carry no story label.
- Every task names exact file paths.

## Path Conventions

Web app layout (matches plan.md Project Structure):

- Backend root: `backend/src/momdiary/`
- Backend tests: `backend/tests/`
- Frontend root: `frontend/src/`
- Frontend tests: `frontend/src/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wire the new dependencies and configuration so any user story can start.

- [X] T001 Pin `clerk-backend-api>=1.5.0,<2.0.0` and `svix>=1.30.0,<2.0.0` and **remove** `argon2-cffi` in [backend/pyproject.toml](backend/pyproject.toml); regenerate the lockfile.
- [X] T002 [P] Add `@clerk/clerk-react@^5.18.0` to [frontend/package.json](frontend/package.json); run `npm install` and commit the lockfile.
- [X] T003 [P] Add Clerk settings to [backend/src/momdiary/config.py](backend/src/momdiary/config.py): `CLERK_SECRET_KEY`, `CLERK_JWT_ISSUER`, `CLERK_JWT_AUDIENCE`, `CLERK_WEBHOOK_SECRET` (all `SecretStr` where applicable, all read from `backend/.env`).
- [X] T004 [P] Add `VITE_CLERK_PUBLISHABLE_KEY` to [frontend/.env.example](frontend/.env.example) and document it in [frontend/README.md](frontend/README.md).
- [X] T005 [P] Document the required Clerk dashboard configuration in [specs/008-clerk-auth/quickstart.md](specs/008-clerk-auth/quickstart.md) prerequisites: enable email+password + Google, create the `momdiary-default` JWT template with `email` and `email_verified` claims, register the `POST /v1/webhooks/clerk` endpoint with `user.deleted` + `user.updated` events (already authored in quickstart §1 — verify and refine).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the Clerk verification core, the lazy-provisioning user resolver, the email-verification gate, the webhook handler, and the schema migration. **No user story can begin until this phase is complete.**

### 2A. Database schema & migration

- [X] T006 Modify [backend/src/momdiary/models/orm.py](backend/src/momdiary/models/orm.py): on the `User` ORM class, drop `password_hash` and `password_updated_at`; add `clerk_user_id: Mapped[str]` (unique, not-null) and `email_verified_at: Mapped[datetime | None]`. Delete the `UserSession` ORM class entirely.
- [X] T007 Create Alembic revision [backend/alembic/versions/0003_clerk_users.py](backend/alembic/versions/0003_clerk_users.py) (script_location is `alembic/`, not `db/migrations/`) implementing the upgrade per [data-model.md](specs/008-clerk-auth/data-model.md) §2: DELETE every diary table in FK order, drop `user_sessions`, batch-alter `users` to drop password columns and add `clerk_user_id` + `email_verified_at`, create `UNIQUE INDEX uq_users_clerk_user_id`. Downgrade raises `NotImplementedError`. (depends on T006)
- [X] T008 Ran `alembic upgrade head` against [backend/momdiary.db](backend/momdiary.db) (backed up to `momdiary.db.bak`); verified tables = `[agent_interactions, alembic_version, appointment_notes, appointments, babies, feeds, poops, settings, sleeps, users]` (user_sessions dropped ✓) and users columns = `[id, email, display_name, active_baby_id, created_at, updated_at, deleted_at, clerk_user_id, email_verified_at]` with index `uq_users_clerk_user_id` present.

### 2B. JWT verification core

- [ ] T009 [P] Write failing unit tests in [backend/tests/unit/test_clerk_jwt_verifier.py](backend/tests/unit/test_clerk_jwt_verifier.py) covering: valid JWT, expired, wrong-issuer, wrong-audience, unknown `kid` (triggers JWKS refresh), tampered signature, missing `sub`, missing `email_verified`. Use a locally-generated RSA keypair + `httpx.MockTransport` for the JWKS endpoint.
- [X] T010 Implement [backend/src/momdiary/auth/clerk.py](backend/src/momdiary/auth/clerk.py): in-process JWKS cache (1 h TTL, `asyncio.Lock`-deduplicated force-refresh on `kid` miss) and `verify_clerk_jwt(token: str) -> ClerkClaims` returning a typed claims object (`sub`, `email`, `email_verified`, `sid`, `exp`, `iat`). PyJWT + httpx + `clerk-backend-api` deps. (depends on T003, T009)

### 2C. FastAPI dependencies & middleware

- [ ] T011 [P] Write failing unit tests in [backend/tests/unit/test_email_verification_gate.py](backend/tests/unit/test_email_verification_gate.py): `require_verified_email` raises `HTTPException(403, "email_not_verified")` when claim is `False`, passes through when `True`.
- [X] T012 Rewrite [backend/src/momdiary/auth/dependencies.py](backend/src/momdiary/auth/dependencies.py): `get_current_user` reads `Authorization: Bearer`, calls `verify_clerk_jwt`, looks up or lazy-provisions the `users` row (per [data-model.md](specs/008-clerk-auth/data-model.md) §3), mirrors `email` + `email_verified_at`, returns a `CurrentUser` dataclass. Add `require_verified_email(user: CurrentUser = Depends(get_current_user))`. Raise uniform 401 `{"error":"not_signed_in",...}` on any verification failure. (depends on T010, T011)
- [X] T013 [P] Strip cookie parsing from [backend/src/momdiary/auth/middleware.py](backend/src/momdiary/auth/middleware.py): keep only correlation-ID enrichment and `auth_mode="clerk_jwt"` structured-log field. Ensure the JWT string is never logged. Also removed `OriginCsrfMiddleware`.
- [X] T014 Deleted legacy local-auth files: `backend/src/momdiary/auth/hasher.py`, `backend/src/momdiary/auth/sessions.py`, `backend/src/momdiary/api/auth.py`. Updated [backend/src/momdiary/auth/\_\_init\_\_.py](backend/src/momdiary/auth/__init__.py) to re-export only Clerk-derived symbols. (depends on T012, T013)
- [ ] T015 Update [backend/src/momdiary/auth/README.md](backend/src/momdiary/auth/README.md) to describe the new Clerk-based contract (Principle IV: module-level README required).

### 2D. Webhook handler

- [ ] T016 [P] Write failing unit tests in [backend/tests/unit/test_clerk_webhook_verifier.py](backend/tests/unit/test_clerk_webhook_verifier.py): valid Svix signature accepted, replay accepted (idempotent), wrong secret rejected 401, malformed body rejected 400.
- [X] T017 [P] Pydantic models added in [backend/src/momdiary/schemas/webhooks.py](backend/src/momdiary/schemas/webhooks.py): `ClerkWebhookEnvelope`, `UserDeletedData`, `UserUpdatedData`.
- [X] T018 Implemented Svix signature verification + dispatcher in [backend/src/momdiary/auth/webhooks.py](backend/src/momdiary/auth/webhooks.py): `verify_svix(headers, body) -> None`, `handle_user_deleted(clerk_user_id)`, `handle_user_updated(clerk_user_id, email, email_verified)`. `handle_user_deleted` runs the cascade in [data-model.md](specs/008-clerk-auth/data-model.md) §4 inside one SQLAlchemy transaction AND calls `purge_user(user_id)` on the chat store. (depends on T012, T016, T017)
- [X] T019 [P] Added `purge_user(user_id: int) -> int` to [backend/src/momdiary/agents/session_store.py](backend/src/momdiary/agents/session_store.py): evicts every entry whose key starts with `(user_id, ...)` and surfaces a `session.purged_user` log line.
- [X] T020 Mounted `POST /v1/webhooks/clerk` router in [backend/src/momdiary/api/webhooks.py](backend/src/momdiary/api/webhooks.py) wiring T018; registered in [backend/src/momdiary/main.py](backend/src/momdiary/main.py) (no `get_current_user` dependency; signature is the auth).

### 2E. App wire-up

- [X] T021 Modified [backend/src/momdiary/main.py](backend/src/momdiary/main.py) (actual factory; task plan referenced `api/main.py` which does not exist): removed `OriginCsrfMiddleware`; removed import of deleted `api/auth.py`; restricted CORS to known headers (`Authorization`, `Content-Type`, `X-Active-Baby-Id`, `X-Session-ID`); switched `allow_credentials=False`; mounted the new webhook router from T020. (depends on T014, T020)

**Checkpoint**: Foundation ready — JWT auth dependency, email-verification gate, webhook cascade, and migration all in place. User story phases can now begin.

---

## Phase 3: User Story 1 — New caregiver signs up with email + password (Priority: P1) 🎯 MVP

**Goal**: A first-time caregiver can sign up via embedded Clerk `<SignUp />` at `/sign-up`, verify their email, land in MomDiary signed-in, and be ready to create their first baby.

**Independent Test**: From a clean browser session, visit MomDiary, click "Sign up", complete the embedded form at `/sign-up`, verify the email, confirm landing on the baby-creation screen with an active authenticated session and zero baby rows for the new caregiver.

### Tests for User Story 1

- [ ] T022 [P] [US1] Failing contract test in [backend/tests/contract/test_clerk_auth_contract.py](backend/tests/contract/test_clerk_auth_contract.py) covering `GET /v1/users/me` per [contracts/clerk-auth.openapi.yaml](specs/008-clerk-auth/contracts/clerk-auth.openapi.yaml) (200 shape, 401 shape).
- [ ] T023 [P] [US1] Failing integration test in [backend/tests/integration/test_users_me_lazy_provision.py](backend/tests/integration/test_users_me_lazy_provision.py): first `GET /v1/users/me` for a previously-unseen Clerk `sub` creates a `users` row; second call is a no-op; mirrored `email` + `email_verified_at` reflect the JWT claims.
- [ ] T024 [P] [US1] Failing integration test in [backend/tests/integration/test_write_gating_unverified.py](backend/tests/integration/test_write_gating_unverified.py): JWT with `email_verified=false` → `POST /v1/babies` returns 403 `email_not_verified`; reads (e.g., `GET /v1/babies`) still return 200 with empty list.
- [ ] T025 [P] [US1] Failing frontend test [frontend/src/tests/SignUpPage.test.tsx](frontend/src/tests/SignUpPage.test.tsx): `SignUpPage` renders `<SignUp routing="path" path="/sign-up" />` (mocked via `@clerk/clerk-react` test utilities).
- [ ] T026 [P] [US1] Failing frontend test [frontend/src/tests/VerifyEmailBanner.test.tsx](frontend/src/tests/VerifyEmailBanner.test.tsx): banner shown when `useUser()` returns user with unverified primary email; hidden when verified.

### Implementation for User Story 1

- [X] T027 [US1] Implemented `GET /v1/users/me` in [backend/src/momdiary/api/users.py](backend/src/momdiary/api/users.py): depends on `get_current_user`, returns the `CurrentUserOut` projection per contract. Removed legacy `/v1/auth/*` routes (file `api/auth.py` deleted in T014). (depends on T012)
- [X] T028 [P] [US1] Updated [backend/src/momdiary/schemas/auth.py](backend/src/momdiary/schemas/auth.py): deleted `LoginRequest`, `RegisterRequest`, `PasswordStr`; added `CurrentUserOut` matching the OpenAPI `CurrentUser` schema; `UserPublic` now carries `email_verified`.
- [ ] T029 [P] [US1] Add Pydantic `WriteForbiddenUnverifiedError` body and a FastAPI `exception_handler` for `email_not_verified` in [backend/src/momdiary/api/main.py](backend/src/momdiary/api/main.py) (one consistent 403 shape across all writes).
- [X] T030 [P] [US1] Implemented [frontend/src/features/auth/SignUpPage.tsx](frontend/src/features/auth/SignUpPage.tsx) rendering `<SignUp routing="path" path="/sign-up" />` (plus matching [SignInPage.tsx](frontend/src/features/auth/SignInPage.tsx)) with MomDiary `bg-amber-50` shell.
- [X] T031 [P] [US1] Implemented [frontend/src/features/auth/VerifyEmailBanner.tsx](frontend/src/features/auth/VerifyEmailBanner.tsx): subscribes to `useUser()`, surfaces "Verify your email" + a "Resend email" button calling `primaryEmailAddress.prepareVerification({ strategy: "email_code" })`. Renders nothing once `verification.status === "verified"`.
- [X] T032 [US1] Implemented [frontend/src/features/auth/useClerkSession.ts](frontend/src/features/auth/useClerkSession.ts): thin wrapper over `useAuth()` exposing `{ isLoaded, isSignedIn, userId, getToken }` with `getToken()` hard-coded to the `momdiary-default` template.
- [X] T033 [US1] Modified [frontend/src/shared/apiClient.ts](frontend/src/shared/apiClient.ts): dropped cookie credentials, removed `register`/`login`/`logout`, switched `me()` to flat `currentUserSchema` against `GET /v1/users/me`, added `setTokenProvider()` + per-request `Authorization: Bearer` injection; the existing `onUnauthorized` listener is now wired in [App.tsx](frontend/src/App.tsx) to call Clerk `signOut()` + navigate to `/sign-in`.
- [X] T034 [US1] Rewrote [frontend/src/main.tsx](frontend/src/main.tsx) and [frontend/src/App.tsx](frontend/src/App.tsx): `<BrowserRouter>` + `<ClerkProvider>` (with `routerPush`/`routerReplace` adapters) + `<ClerkTokenBridge>` register the JWT provider on sign-in; routes `/sign-in/*`, `/sign-up/*`, and a gated `/*` that wraps the shell in `<SignedIn>` / `<SignedOut><RedirectToSignIn/></SignedOut>` and mounts `<VerifyEmailBanner>` at the top. Legacy `AuthShell.tsx`, `LoginPage.tsx`, `SignupPage.tsx` deleted; `useSession.ts` rewritten as a Clerk-backed shim that preserves the existing `useSession` / `SESSION_QUERY_KEY` / `useLogoutMutation` / `useUpdateProfileMutation` API used by `App`, `CaregiverCard`, and `useBabies`. `frontend/src/shared/types.ts` gained `CurrentUser` + `email_verified` on `UserPublic` and lost the password/login/register schemas. Verified: `npx tsc --noEmit` clean and `npx vite build` succeeds.
- [X] T035 [US1] Applied `Depends(require_verified_email)` to the write routes used in US1 baby creation: every `POST/PUT/DELETE` in [backend/src/momdiary/api/babies.py](backend/src/momdiary/api/babies.py) (via decorator-level `dependencies=[...]`). Read routes remain on `Depends(get_current_user)` only.
- [ ] T036 [US1] Add structured log fields `user_id`, `clerk_user_id`, `email_verified`, `auth_mode="clerk_jwt"` to the per-request log line per [contracts/existing-endpoint-changes.md](specs/008-clerk-auth/contracts/existing-endpoint-changes.md) §4 (touch the existing structlog processor pipeline in `auth/middleware.py` or the app factory — single edit).

**Checkpoint**: A new caregiver can sign up, verify, sign in, and create a baby. MVP complete.

---

## Phase 4: User Story 2 — Returning caregiver signs in (Priority: P1)

**Goal**: An existing caregiver can sign in at `/sign-in` via email+password OR Google and recover their previously logged baby data; any protected page hit by an unauthenticated visitor redirects to `/sign-in`.

**Independent Test**: Sign out an existing caregiver, sign back in via each method, confirm caregiver row resolves, baby selection restores, and previously logged entries are visible. Directly URL-load a protected page while signed out → bounced to `/sign-in`.

### Tests for User Story 2

- [ ] T037 [P] [US2] Failing integration test [backend/tests/integration/test_auth_required.py](backend/tests/integration/test_auth_required.py): sweep every protected endpoint listed in [contracts/existing-endpoint-changes.md](specs/008-clerk-auth/contracts/existing-endpoint-changes.md) §2 with no `Authorization` header → 401 with uniform body shape (SC-003).
- [ ] T038 [P] [US2] Failing integration test [backend/tests/integration/test_baby_scoping_preserved.py](backend/tests/integration/test_baby_scoping_preserved.py): caregiver A's JWT cannot read or write caregiver B's baby's entries; cross-tenant attempts return 404 (not 403), preserving FR-011.
- [ ] T039 [P] [US2] Failing frontend test [frontend/src/tests/SignInPage.test.tsx](frontend/src/tests/SignInPage.test.tsx): renders `<SignIn routing="path" path="/sign-in" />`; "Continue with Google" surface visible (Clerk renders it from dashboard config — test asserts the component mount only).
- [ ] T040 [P] [US2] Failing frontend test [frontend/src/tests/apiClient.auth.test.tsx](frontend/src/tests/apiClient.auth.test.tsx): every outbound fetch carries `Authorization: Bearer <token>`; 401 response triggers redirect to `/sign-in`.

### Implementation for User Story 2

- [ ] T041 [P] [US2] Implement [frontend/src/features/auth/SignInPage.tsx](frontend/src/features/auth/SignInPage.tsx) rendering `<SignIn routing="path" path="/sign-in" afterSignInUrl="/" />`.
- [ ] T042 [P] [US2] Implement [frontend/src/features/auth/RequireAuth.tsx](frontend/src/features/auth/RequireAuth.tsx): wraps children in `<SignedIn>{children}</SignedIn><SignedOut><RedirectToSignIn redirectUrl={...} /></SignedOut>` and preserves the originally-requested path so post-sign-in lands back on it.
- [ ] T043 [US2] Wire `/sign-in/*` route in [frontend/src/App.tsx](frontend/src/App.tsx); wrap every protected route under `RequireAuth`. (depends on T034, T041, T042)
- [ ] T044 [P] [US2] Delete the legacy in-house auth pages: any `frontend/src/features/auth/LoginPage.tsx`, `SignupPage.tsx`, `useSession.ts` from feature 006. Update imports across the tree.
- [ ] T045 [US2] Apply `Depends(get_current_user)` (reads) and `Depends(require_verified_email)` (writes) per [contracts/existing-endpoint-changes.md](specs/008-clerk-auth/contracts/existing-endpoint-changes.md) §2 to: [backend/src/momdiary/api/feeds.py](backend/src/momdiary/api/feeds.py), [backend/src/momdiary/api/sleeps.py](backend/src/momdiary/api/sleeps.py), [backend/src/momdiary/api/poops.py](backend/src/momdiary/api/poops.py), [backend/src/momdiary/api/appointments.py](backend/src/momdiary/api/appointments.py), [backend/src/momdiary/api/entries.py](backend/src/momdiary/api/entries.py). Keep all existing baby-ownership 404 checks unchanged (FR-011).
- [ ] T046 [US2] Update [backend/src/momdiary/api/dependencies.py](backend/src/momdiary/api/dependencies.py): `get_active_baby` continues to read the `X-Active-Baby-Id` header (or path param) but resolves ownership against the Clerk-derived `users.id`. No shape change for the chat session store keying. (depends on T012)
- [X] T046a [US2] Migrated `PUT /v1/users/me` in [backend/src/momdiary/api/users.py](backend/src/momdiary/api/users.py) from cookie session to bearer JWT: swapped the dependency to `Depends(get_current_user)` (via `CurrentUserDep`), dropped cookie-only branches, kept existing request/response shape. **No** `require_verified_email` (profile field update). Failing integration test [backend/tests/integration/test_users_me_put_bearer.py](backend/tests/integration/test_users_me_put_bearer.py) still pending. Closes analysis finding **M2**. (depends on T012, T027)

**Checkpoint**: Returning users can sign in via either method; unauthenticated traffic is uniformly rejected. US1 + US2 = full P1 surface.

---

## Phase 5: User Story 3 — Caregiver signs up with Google in one click (Priority: P2)

**Goal**: A new caregiver can complete sign-up with Google in a single round-trip; no email verification step is shown; immediate write access (bypasses FR-017 because the Google email is pre-verified).

**Independent Test**: From a clean browser session, click "Sign up", choose "Continue with Google", complete Google consent → new MomDiary caregiver row exists with `email_verified_at IS NOT NULL` and `POST /v1/babies` succeeds without ever showing the verify-email banner.

### Tests for User Story 3

- [ ] T047 [P] [US3] Failing integration test [backend/tests/integration/test_google_signup_bypasses_gate.py](backend/tests/integration/test_google_signup_bypasses_gate.py): a JWT minted with `email_verified=true` on first sight (simulating Google sign-up) triggers lazy provision with `email_verified_at = now()`; immediately succeeds on `POST /v1/babies`.
- [ ] T048 [P] [US3] Failing integration test [backend/tests/integration/test_identity_link_no_duplicate.py](backend/tests/integration/test_identity_link_no_duplicate.py): when the same Clerk `sub` later returns with a different verified email (Google linked to existing account), no second `users` row is created (FR-007).

### Implementation for User Story 3

- [ ] T049 [P] [US3] Confirm the lazy-provisioner from T012 sets `email_verified_at = now()` when JWT claim is `true` (this is the implementation seam exercised by T047 — patch as needed to make the test pass).
- [ ] T050 [P] [US3] Update [specs/008-clerk-auth/quickstart.md](specs/008-clerk-auth/quickstart.md) S3 if any prerequisite is missing (Google OAuth client wired into Clerk dashboard).

No frontend code change is required for US3 because Clerk's `<SignUp />` renders the "Continue with Google" button automatically when the provider is enabled in the dashboard.

**Checkpoint**: Google sign-up path validated end-to-end.

---

## Phase 6: User Story 4 — Caregiver signs out (Priority: P3)

**Goal**: Signed-in caregiver can sign out from any signed-in page; the Clerk session ends and the browser cannot resurrect it; protected URLs hit afterwards redirect to `/sign-in`.

**Independent Test**: Click sign-out, verify subsequent protected-route navigation bounces to `/sign-in`, re-opening the app does NOT auto-restore the previous session, and a request replaying the prior JWT (after `exp`) returns 401.

### Tests for User Story 4

- [ ] T051 [P] [US4] Failing frontend test [frontend/src/tests/SignOutControl.test.tsx](frontend/src/tests/SignOutControl.test.tsx): clicking the sign-out control invokes `useAuth().signOut()` and routes to `/`.
- [ ] T052 [P] [US4] Failing integration test [backend/tests/integration/test_expired_jwt_rejected.py](backend/tests/integration/test_expired_jwt_rejected.py): an expired JWT against any protected endpoint returns 401 `not_signed_in` (covers FR-010 + sign-out semantics).

### Implementation for User Story 4

- [ ] T053 [P] [US4] Add a sign-out control to the signed-in chrome in [frontend/src/App.tsx](frontend/src/App.tsx) or the existing top-bar component, using Clerk's `<UserButton afterSignOutUrl="/" />` (renders avatar + sign-out menu). Alternatively a bare `<button onClick={() => signOut()}>` — choose `<UserButton>` for parity with Clerk's a11y + i18n.

No backend code change is required for US4: sign-out is a Clerk-side session revocation; the next request's JWT is invalid and the existing 401 path from T012 handles it.

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Webhook Cascade Integration (cross-cutting; satisfies FR-015 / FR-016)

**Purpose**: End-to-end validation of the account-deletion cascade across the full data graph + chat session store.

- [ ] T054 [P] Failing integration test [backend/tests/integration/test_webhook_user_deleted_cascade.py](backend/tests/integration/test_webhook_user_deleted_cascade.py): seed a user with babies + feeds + sleeps + poops + appointments + appointment_notes + agent_interactions + chat-session entries; POST a Svix-signed `user.deleted` to `/v1/webhooks/clerk`; assert all rows gone, chat store purged, response 200. Replay the same event → still 200, still no rows (idempotency).
- [ ] T055 [P] Failing integration test [backend/tests/integration/test_webhook_post_delete_session_rejected.py](backend/tests/integration/test_webhook_post_delete_session_rejected.py): after T054 cascade, present a JWT whose `sub` was the deleted user → 401 `not_signed_in` (FR-016).
- [ ] T056 Verify T054 / T055 pass against the implementation from T018–T020. Fix any cascade ordering or chat-store purge bug surfaced.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Performance guard, log-hygiene CI gate, and quickstart validation per Constitution III and SC-005.

- [ ] T057 [P] Add micro-benchmark [backend/tests/benchmarks/test_jwt_verify_perf.py](backend/tests/benchmarks/test_jwt_verify_perf.py) using `pytest-benchmark`: verify p95 of `verify_clerk_jwt` (warm JWKS cache) ≤ 5 ms; benchmark BLOCKS merge on regression > 10% (Constitution III).
- [ ] T058 [P] Add log-scan CI gate as [backend/tests/integration/test_log_redaction.py](backend/tests/integration/test_log_redaction.py): run a representative request flow, scan the captured log output with a regex for `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.` (JWT pattern) and the literal substring `password`; both MUST be zero matches (SC-005, FR-014).
- [ ] T059 [P] Run lint/format gates: `cd backend; ruff check .; ruff format --check .` and `cd frontend; npm run lint`. Fix any drift introduced by the new files.
- [ ] T060 [P] Update [README.md](README.md) "Auth" section to point at Clerk (replace any feature-006 cookie-auth language).
- [ ] T061 Execute the manual validation script in [specs/008-clerk-auth/quickstart.md](specs/008-clerk-auth/quickstart.md) end-to-end against a test Clerk instance; record any deltas back into quickstart.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies — start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1 completion — **BLOCKS** every user story.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2 (independent of US1; can run in parallel with US1 if staffed).
- **Phase 5 (US3)**: depends on Phase 2 (independent of US1 / US2 once the lazy-provisioner from T012 is in place).
- **Phase 6 (US4)**: depends on Phase 2 (sign-out simply leverages the auth dependency).
- **Phase 7 (Webhook cascade)**: depends on Phase 2.D (T016–T020) and on Phase 3's seedable data layer; can run after Phase 3 lands.
- **Phase 8 (Polish)**: depends on every prior phase.

### Within Phase 2 (Foundational)

- 2A schema (T006 → T007 → T008) is strictly sequential.
- 2B JWT core (T009 → T010) is sequential.
- 2C dependencies/middleware (T011 → T012 → T013/T014/T015): T012 depends on T010 and T011; T014 depends on T012/T013; T015 is doc and can run any time after T012.
- 2D webhook (T016/T017 → T018 → T020); T019 (chat store purge) is independent and can land in parallel with T016/T017.
- 2E (T021) is the last foundational step.

### Within each user-story phase

- All tests for the story (`[P]`-marked test tasks) MUST be written first and MUST fail (Constitution II test-first).
- Then `[P]`-marked implementation tasks in parallel.
- Then sequential integration tasks.

### Parallel opportunities

- T002, T003, T004, T005 across Phase 1.
- T009, T011, T013, T016, T017, T019 within Phase 2 (different files, no incomplete-dep conflicts).
- All test tasks within a single user story phase (T022–T026, T037–T040, T047–T048, T051–T052).
- All `[P]`-marked implementation tasks within a single user story phase (T028–T031, T041/T042/T044, T049/T050).
- All polish tasks T057–T060 in parallel.
- US1, US2, US3, US4 can be developed in parallel by different team members once Phase 2 ends.

---

## Parallel Execution Examples

### Phase 1 (Setup) — kick off in parallel

```text
T002 (frontend deps) || T003 (backend config) || T004 (frontend env example) || T005 (quickstart prereqs)
```

### Phase 2D (Webhook) — overlap with 2C

```text
T013 (middleware strip) || T016 (webhook verifier tests) || T017 (webhook schemas) || T019 (chat purge)
```

### Phase 3 (US1) — write all tests first, then implement in parallel

```text
T022 || T023 || T024 || T025 || T026          # tests (must all fail)
↓
T028 || T029 || T030 || T031                  # implementation in parallel
↓
T027, T032, T033, T034, T035, T036            # integration in sequence
```

### Phase 8 (Polish) — entirely parallel

```text
T057 || T058 || T059 || T060
↓
T061  (final manual quickstart)
```

---

## Implementation Strategy

**MVP** = Phase 1 + Phase 2 + Phase 3 (US1 alone). At that point, a new caregiver can sign up with email+password, verify their email, sign in, and create a baby. The migration has discarded any pre-existing local-auth data (FR-012, SC-004), the JWT path is the only auth path, and the email-verification gate is enforced server-side (FR-017).

**Incremental delivery**:

1. Land Phases 1 + 2 in one PR (foundation; no user-visible change beyond the data reset).
2. Land Phase 3 (US1) → ship MVP.
3. Land Phase 4 (US2) → returning users + Google sign-in surface.
4. Land Phase 5 (US3) → validated Google sign-up bypass.
5. Land Phase 6 (US4) → polished sign-out UX.
6. Land Phase 7 (Webhook cascade) → account-deletion contract met.
7. Land Phase 8 (Polish) → perf gate, log-scan gate, lint/docs.

**Total task count**: 62. **Per-story counts**: Setup = 5; Foundational = 16; US1 = 15; US2 = 11; US3 = 4; US4 = 3; Webhook = 3; Polish = 5.

**Format validation**: every task above starts with `- [ ] T###`, includes the `[Story]` label inside a user-story phase, omits the `[Story]` label in Setup / Foundational / Webhook / Polish phases, and names an exact file path.
