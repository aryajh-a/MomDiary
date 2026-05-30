# Phase 0 Research: Clerk-Powered Caregiver Authentication

**Feature**: 008-clerk-auth
**Date**: 2026-05-27
**Status**: Complete

All "NEEDS CLARIFICATION" items from the spec were resolved in the `/speckit.clarify`
session (5/5 questions answered). This document records the remaining technical
research needed for Phase 1 design.

---

## 1. JWT verification strategy: networkless vs. introspection

### Decision

**Networkless verification using Clerk's JWKS (`https://<frontend-api>/.well-known/jwks.json`)
and the official `clerk-backend-api` Python SDK's `authenticate_request()` helper.**

### Rationale

- Constitution III caps interactive p95 at 2 s. A REST round-trip to Clerk per
  request (`GET /v1/sessions/{id}`) would consume 50–200 ms of that budget and
  scale poorly. Networkless verification is in-process RSA signature verification
  against a cached JWKS document — measured at ≤ 1 ms on dev hardware.
- The Clerk Python SDK (`clerk-backend-api`) ships a typed `authenticate_request`
  helper that wraps JWKS fetch + cache + signature/claim verification, so we do
  not have to hand-roll PyJWT + httpx + custom caching.
- The JWT payload already carries every claim we need (`sub` = Clerk user ID,
  `email`, `email_verified`, `exp`, `iat`, `iss`, `aud`, `sid` = session ID).
  No supplementary API call is required for the hot path.

### Alternatives considered

- **Token introspection (call `GET /v1/sessions/verify` per request)**: rejected
  on latency grounds (Constitution III) and external-dep fragility (every
  request becomes a network round-trip to Clerk).
- **PyJWT + manual JWKS fetch**: rejected because the official SDK does this
  correctly already; rolling our own multiplies attack-surface review and
  delays SDK security fixes.
- **Trusting a client-supplied `X-User-Id` header**: prohibited by FR-009 (the
  server MUST NOT rely on caller-supplied identity claims).

---

## 2. JWKS caching policy

### Decision

**In-process LRU-style cache with a 1-hour TTL and forced refresh on any `kid`
miss.** Cache lives on the FastAPI app state, populated lazily on first request.

### Rationale

- Clerk rotates signing keys infrequently (months) but advertises every key in
  JWKS, so a 1-hour TTL is a safe upper bound between routine refreshes.
- A `kid` miss on an incoming JWT is the unambiguous signal that the key set
  has rotated, so we trigger a single immediate JWKS refetch (deduplicated
  across concurrent requests with an `asyncio.Lock`) before failing the
  request. This avoids a flood of refetches on a single bad token.
- Caching at app-state scope (one cache per uvicorn worker) is appropriate for
  our single-process deployment topology. If we ever scale horizontally, each
  worker simply maintains its own copy — JWKS is public and idempotent to
  fetch.

### Alternatives considered

- **No cache, fetch JWKS per request**: rejected (latency, fragility).
- **Disk-backed cache**: rejected as unnecessary complexity for SQLite-scale
  deployment.

---

## 3. Where to read `email_verified` from

### Decision

**Read from the JWT claim `email_verified` (boolean), supplied via a custom
JWT template configured in the Clerk dashboard.**

### Rationale

- Default Clerk JWTs include `sub`, `iss`, `aud`, `exp`, `iat`, and `sid` but
  do not include email or verification state. We define a JWT template named
  `momdiary-default` whose claims block includes:
  ```json
  {
    "email": "{{user.primary_email_address}}",
    "email_verified": "{{user.email_verified}}"
  }
  ```
- The frontend then calls `getToken({ template: 'momdiary-default' })` to mint
  tokens that carry these claims. Backend treats `email_verified === true` as
  the gate for FR-017.
- Reading the claim from the JWT keeps the hot path networkless. The alternative
  — querying Clerk's `GET /v1/users/{id}` per write — would re-introduce a
  network round-trip on the most latency-sensitive endpoints.

### Alternatives considered

- **Query Clerk's user API per write request**: rejected on latency and
  Constitution III grounds.
- **Trust a `email_verified` flag in our own `users` table**: rejected because
  it would lag Clerk's source of truth and require a webhook for every change.
  The JWT claim updates on the very next token mint after the user verifies
  (which `@clerk/clerk-react` does automatically on every `getToken()` call),
  satisfying FR-019's "gate lifts on the very next request" requirement.

---

## 4. Webhook handling for account deletion (FR-015 / FR-016)

### Decision

**`POST /v1/webhooks/clerk` endpoint, Svix-signed (Clerk uses Svix), handling
`user.deleted` and `user.updated` events. The handler runs a single
transaction that deletes every diary row scoped to each baby owned by the
caregiver, then the baby rows, then the user row, in that order.**

### Rationale

- Clerk delivers webhooks via Svix; signature verification uses the
  `svix-id`, `svix-timestamp`, and `svix-signature` headers against the
  shared `CLERK_WEBHOOK_SECRET`. This is the documented and supported path
  and gives us replay-protection out of the box.
- Doing the cascade in a single SQLAlchemy transaction means partial failure
  rolls back cleanly; Svix retries the event until we return 2xx, so the
  cascade is idempotent (a second delivery finds no rows to delete and is
  still a 2xx).
- The cascade order (entries → babies → user) respects the FK chain that
  feature 006 established (`baby_id NOT NULL` on every diary table; `user_id`
  on `babies`).
- We MUST also accept `user.updated` for completeness (email change, etc.),
  but in this feature it simply mirrors the new `email` into our `users`
  table and updates `email_verified_at`; no cascade.

### Alternatives considered

- **Poll Clerk for deletions**: rejected (latency, cost, Clerk does not expose
  a "deleted users since" endpoint).
- **Cascade via SQL `ON DELETE CASCADE` only**: rejected because the
  `users.id → babies.user_id → feeds.baby_id` chain already does the right
  thing, but we still need the webhook to *initiate* the user-row delete; the
  webhook is non-optional.
- **Async background job**: rejected as unnecessary complexity for our scale
  (low-thousands of caregivers, modest baby/entry counts per caregiver). If
  cascade ever exceeds a few hundred ms, we revisit.

---

## 5. Frontend integration: prebuilt components vs. headless hooks

### Decision

**Use `@clerk/clerk-react`'s prebuilt `<SignIn />` and `<SignUp />` components,
mounted at `/sign-in/*` and `/sign-up/*` with `routing="path"` (path-based
routing inside MomDiary, no domain redirect).**

### Rationale

- Clarification Q4 locks the UX shape: "Embedded Clerk components inside
  MomDiary routes; users never leave the MomDiary domain." Prebuilt components
  with `routing="path"` are exactly that.
- Prebuilt components already implement email verification, password reset,
  Google one-tap, error messaging, and MFA prompts. Rebuilding them with
  headless hooks would multiply UI work for no functional gain in MVP.
- Email/password and Google are toggled on/off in the Clerk dashboard, not in
  code. The frontend code does not name the providers; this keeps the
  component-level surface minimal and lets us add Apple/Microsoft later
  without a code change.

### Alternatives considered

- **Hosted Account Portal (Clerk-hosted pages)**: rejected — Clarification Q4
  ruled this out (redirect off domain).
- **Modal `<SignInButton>` / `<SignUpButton>` with `mode="modal"`**: rejected
  because the spec calls for routes (`/sign-in`, `/sign-up`) so the URL
  reflects the page and is bookmarkable / shareable.
- **Headless hooks (`useSignIn`, `useSignUp`) + bespoke UI**: rejected on cost
  and on consistency with Clerk's accessibility and i18n work.

---

## 6. API client: cookie auth vs. bearer token

### Decision

**Bearer token in the `Authorization` header on every API call. Frontend calls
`await getToken({ template: 'momdiary-default' })` in the `apiClient`
interceptor; backend reads the header in the FastAPI dependency.**

### Rationale

- Clerk's React SDK exposes `getToken()`, which always returns a fresh
  short-lived JWT (it refreshes against a long-lived session cookie that
  Clerk owns). We do not have to manage refresh logic.
- A bearer header is explicit, CSRF-immune by construction, and works
  identically for SSR, mobile, and tooling clients.
- The previous cookie-based flow (feature 006) used a same-domain HttpOnly
  cookie set by the backend. Continuing to use cookies here would force a
  copy/paste of Clerk's token into our cookie on every refresh, with no
  benefit; the header path is strictly simpler.

### Alternatives considered

- **`Cookie: __session=...` (Clerk's session cookie)**: works but is
  cross-domain-fragile and would require us to call Clerk's "session sync"
  endpoint on first navigation. Bearer header is simpler.

---

## 7. Backend Python SDK choice: `clerk-backend-api` vs. `clerk-sdk-python`

### Decision

**`clerk-backend-api` (the new, officially-supported Speakeasy-generated SDK).**

### Rationale

- `clerk-sdk-python` is the legacy SDK and is in maintenance mode (no new
  features, eventual deprecation). `clerk-backend-api` is the SDK Clerk
  recommends for new projects as of 2026.
- `clerk-backend-api` ships `authenticate_request()` with built-in JWKS
  caching and explicit `authorized_parties` + `clock_skew_in_seconds`
  options that align with our verification needs.
- Pinned at `>= 1.5.0, < 2.0.0` to stay reproducible (Constitution V
  reproducibility requirement also applies to non-MAF deps).

### Alternatives considered

- **`clerk-sdk-python` (legacy)**: rejected (maintenance mode).
- **Hand-rolled with PyJWT + httpx**: rejected (re-implements a vetted SDK).

---

## 8. Backwards-compatibility / cutover

### Decision

**Hard cutover. One Alembic migration drops `user_sessions`, drops password
columns, adds Clerk columns, and TRUNCATEs every diary table. No "claim my
old account" flow.**

### Rationale

- Clarification Q2 locks this: "No migration — existing local users, babies,
  and diary entries are discarded." The product is pre-broad-launch and the
  user base is a known small set.
- A clean cutover means we delete the local-auth code paths in the same
  change. Keeping both auth paths "just in case" would double the test
  matrix and create a permanent fork in the dependency graph (Constitution
  IV: modular boundaries, no copy-paste reuse).

### Alternatives considered

- **Side-by-side auth with feature-flag switchover**: rejected (cost without
  benefit at this stage of the product).
- **Email-match auto-link of old data**: rejected by Q2 (no migration path).

---

## Open items resolved by Phase 0

| Item | Resolution |
|---|---|
| JWT verification path | Networkless via `clerk-backend-api.authenticate_request` |
| JWKS caching | In-process, 1 h TTL, force-refresh on `kid` miss |
| `email_verified` source | JWT claim populated by `momdiary-default` JWT template |
| Account-delete cascade | Svix-signed webhook → single SQL transaction |
| Frontend embedding | `<SignIn />` + `<SignUp />` with `routing="path"` |
| Token transport | `Authorization: Bearer` header on every API call |
| Python SDK | `clerk-backend-api ≥ 1.5.0` |
| Cutover | Single Alembic migration, TRUNCATE diary data, drop legacy auth code |

No "NEEDS CLARIFICATION" items remain.
