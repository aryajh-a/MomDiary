# Phase 0 Research: User & Baby Profiles with Authentication

**Feature**: 006-user-and-baby-profiles
**Date**: 2026-05-21
**Status**: All `[NEEDS CLARIFICATION]` resolved (see `spec.md → ## Clarifications`).

---

## R1. Password hashing algorithm and parameters

**Decision**: Use Argon2id via `argon2-cffi` (≥ 23.1.0) with `argon2.PasswordHasher` default-tuned parameters: `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4`, `hash_len=32`, `salt_len=16`. Hash strings are stored verbatim (algorithm + parameters + salt + digest in PHC format), enabling transparent parameter upgrades on subsequent verifications via `hasher.check_needs_rehash()`.

**Rationale**: Argon2id is the OWASP-current recommendation (2025), purpose-built to resist GPU brute-force, and ships a maintained Python binding. The PHC string format makes future parameter increases zero-migration. `argon2-cffi`'s defaults pass OWASP's minimum (≥ 19 MiB, ≥ 2 iters, parallelism ≥ 1) by a comfortable margin and produce a per-verification cost in the 50–100 ms range on dev hardware, which fits the SC-002 budget of 2 s end-to-end sign-in.

**Alternatives considered**:
- **bcrypt (`passlib[bcrypt]`)** — Mature but capped at 72-byte inputs, less GPU-resistant. Rejected as the long-term choice.
- **scrypt** — Solid memory-hardness but no built-in parameter-upgrade signal in stdlib bindings. Rejected.
- **PBKDF2 (stdlib `hashlib.pbkdf2_hmac`)** — FIPS-approved but GPU-cheap. Rejected.

---

## R2. Session token mechanism

**Decision**: Opaque random session tokens (32 bytes from `secrets.token_urlsafe(32)`) stored server-side in a `user_sessions` table; the token itself is delivered in an HttpOnly + Secure + SameSite=Lax cookie named `momdiary_session`. Each authenticated request looks the token up, validates expiry, and slides `expires_at` to `now() + 30 days` on success.

**Rationale**: Spec FR-003 mandates **server-side invalidation on sign-out** and a **rolling 30-day idle expiry**. JWTs cannot satisfy server-side invalidation without a token denylist (which is effectively the same DB lookup as opaque tokens, with worse UX). Opaque tokens are simpler, smaller (~ 43 chars), and rotate naturally per device. SameSite=Lax blocks CSRF on POST/PUT/DELETE while still permitting top-level GET navigations.

**Alternatives considered**:
- **JWT in cookie** — Rejected (server-side invalidation requires a denylist anyway).
- **JWT in `Authorization: Bearer` header** — Rejected (forces frontend to manage tokens, exposes them to XSS via JS-accessible storage).
- **Signed-cookie-only sessions (no DB row)** — Rejected (no per-session revocation).

---

## R3. CSRF protection

**Decision**: Rely on `SameSite=Lax` for the session cookie + `Origin` / `Referer` header check on all state-changing endpoints (POST/PUT/PATCH/DELETE). No double-submit token in v1.

**Rationale**: SameSite=Lax cookies are not sent on cross-site sub-resource POSTs, eliminating the classical CSRF vector. The `Origin` check is a low-cost defense-in-depth against browser bugs and against subdomain takeover. A double-submit token adds frontend complexity that the current trust model does not justify.

**Alternatives considered**:
- **Double-submit CSRF token** — Defensible but adds a round-trip and frontend state. Defer to v2 if threat model demands.

---

## R4. Frontend auth integration with TanStack Query

**Decision**: A single `useSession()` hook fetches `GET /v1/auth/me` once on app boot, caches it in TanStack Query under key `["session"]` with `staleTime: Infinity`, and exposes `{ status: "loading" | "signed-out" | "signed-in", user, activeBabyId }`. Route gating is centralized in `<RequireAuth>` and `<RequireBaby>` wrappers; on a 401 from any mutation the global error handler invalidates `["session"]` and triggers a redirect to `/login`.

**Rationale**: Keeps the auth model in a single React-Query cache entry (one source of truth), avoids duplicating session state in React Context, and lets every query/mutation automatically refresh after sign-in/out by invalidation. Matches the existing `apiClient.ts` style already used by feature 005's `useChatEntry`.

**Alternatives considered**:
- **React Context-only AuthProvider** — Rejected (forces every component to opt in to context; doesn't compose with the existing TanStack Query mutation error path).
- **Redux/Zustand auth slice** — Rejected (no existing global store; would be over-engineering).

---

## R5. Alembic schema migration strategy

**Decision**: A single Alembic revision implementing four ordered steps:
1. **Create** `users`, `user_sessions`, `babies` tables with their indexes.
2. **Hard-delete** all existing rows from `feeds`, `sleeps`, `poops`, `appointments`, `appointment_notes`, `agent_interactions` (per FR-018).
3. **Add** `baby_id` column to each of those tables (typed TEXT, NOT NULL, ON DELETE RESTRICT).
4. **Add** indexes on `(baby_id, deleted_at)` and on the existing time columns combined with `baby_id` (e.g., `(baby_id, occurred_at)` on `feeds`).

The downgrade reverses 4 → 3 → 1 only (deletions are not restored).

**Rationale**: Spec FR-018 chose hard-delete on rollout because the data is pre-production. Deleting **before** adding the `NOT NULL` column lets us add the column directly without a temporary nullable phase or an UPDATE pass. The combined `(baby_id, occurred_at)` indexes preserve the existing date-list query performance after the new filter is added.

**Alternatives considered**:
- **Add nullable column, backfill, alter to NOT NULL** — Rejected (FR-018 says hard-delete; this adds two unnecessary migration phases).
- **Per-table migration revisions** — Rejected (atomicity matters here; all-or-nothing in one revision is safer).

---

## R6. Chat session store partitioning (feature 003 reuse)

**Decision**: Extend the in-memory `SessionStore` key from the current `session_id` opaque string to a composite key `(user_id, baby_id, session_id)`. The session-id portion is still client-generated (existing `X-Session-ID` request header), but the server prefixes it internally with the authenticated `(user_id, baby_id)` before lookup. A baby switch on the client does not destroy server-side sessions; instead, the client emits a new session-id for the new baby.

**Rationale**: Satisfies FR-017 (turns from baby A must not influence baby B) without breaking the existing client contract. The session store's TTL / max_turns / max_sessions / message_max_bytes / prompt_token_budget bounds remain unchanged but apply per-tuple.

**Alternatives considered**:
- **Reset the entire session store on baby switch** — Rejected (kills other users' unrelated sessions in the same process).
- **Forbid baby switch with active session** — Rejected (poor UX).

---

## R7. Active-baby preference storage

**Decision**: Persist the current active baby per user as a nullable `active_baby_id` foreign-key column on the `users` table. The frontend sends `X-Active-Baby-Id` on every authenticated request; the server validates that the header matches a baby owned by the user and 400s on mismatch. If the header is absent, the server falls back to `users.active_baby_id`. The server updates `users.active_baby_id` only when the explicit `POST /v1/users/me/active-baby` endpoint is called (not on every request) to keep restoration deterministic.

**Rationale**: Spec FR-010 requires a per-session active baby; FR-011 requires restoring it on next sign-in. A simple FK column gives a durable, restorable record without a separate preferences table. Sending the header on every request makes the server stateless w.r.t. the in-session active baby (allowing the same user to use two browser tabs for two babies if they wish).

**Alternatives considered**:
- **Server holds active baby in the session row only** — Rejected (does not survive a fresh session after a 30-day idle window).
- **Dedicated `user_preferences` table** — Premature generalization for a single column.

---

## R8. Sign-in error message uniformity

**Decision**: All sign-up and sign-in rejections return HTTP 401 with a single payload shape `{"error":{"code":"invalid_credentials","message":"Email or password is incorrect."}}`. Registration-time identifier collisions also map to the same uniform response, with the existing-user case taking a constant-time path (a dummy Argon2 verification) to defeat timing-based enumeration.

**Rationale**: FR-006 mandates no enumeration. A single response shape + constant-time path eliminates both content-based and timing-based oracles.

**Alternatives considered**:
- **Distinct "email already in use" message on registration** — Rejected explicitly by FR-006.

---

## Constitution alignment summary

| Principle | How this plan satisfies it |
|---|---|
| **I. Code Quality** | New modules (`auth`, `babies`) carry docstrings, lint clean, complexity bounded; no new TODOs without owners. |
| **II. Testing (NON-NEGOTIABLE)** | Unit tests for hashing, session-token issuance, ownership checks; integration tests for `/v1/auth/*`, `/v1/babies/*`, and `baby_id` scoping on every existing endpoint; contract tests for the new OpenAPI surface; no live-model calls. |
| **III. Performance** | SC-002 (2 s sign-in p95) is within the constitution's 2 s p95 budget. Argon2id parameters chosen so a single verification fits well within budget. A micro-benchmark for sign-in latency is added to `tests/benchmarks/`. |
| **IV. Modular Architecture** | Auth and baby modules are pluggable: auth lives behind a `SessionService` interface, baby ownership lives behind a `BabyResolver` dependency injected into the existing dispatchers. |
| **V. Microsoft Agent Framework First (NON-NEGOTIABLE)** | This feature adds NO new AI agents and changes NO existing agent contracts; the existing `/v1/entries` MAF dispatch and `/v1/chatentry/` direct-LLM dispatcher remain on their respective stacks. Principle V is therefore N/A for the code introduced here, while still binding on any future change those modules touch. |
