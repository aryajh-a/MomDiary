# `momdiary.auth` — feature 008 (Clerk)

Caregiver identity for MomDiary. Authoritative identity provider is
[Clerk](https://clerk.com); the backend never sees or stores passwords.
Every request is authenticated by a short-lived RS256 JWT minted by
Clerk and verified in-process using JWKS.

| Module           | Purpose                                                                    |
|------------------|-----------------------------------------------------------------------------|
| `clerk.py`       | JWKS cache + `verify_clerk_jwt` (issuer / audience / signature / exp).      |
| `dependencies.py`| `get_current_user`, `require_verified_email`, `CurrentUser`.                |
| `middleware.py`  | `AuthLogContextMiddleware` (binds `user_id` / `clerk_user_id` to logs).     |
| `context.py`     | `set_active_baby_id` / `get_active_baby_id` contextvar for the request.     |
| `webhooks.py`    | Svix-verified `POST /v1/webhooks/clerk` for user lifecycle events.          |

See `specs/008-clerk-auth/{research.md, data-model.md, contracts/}`.

---

## Transport

* Frontend attaches `Authorization: Bearer <jwt>` on every API call. No
  cookies are exchanged with the backend — `allow_credentials=False` in
  CORS, `credentials` is not `"include"` in the browser client.
* JWT is minted by Clerk from the **`momdiary-default`** custom template,
  which must include the claims `email` and `email_verified`.
* Tokens are short-lived (~60 s). The Clerk SDK caches the current token
  for ~50 s and silently refreshes on the next outbound call.

---

## Configuration (`backend/.env`)

```dotenv
CLERK_JWT_ISSUER=https://<your-instance>.clerk.accounts.dev
CLERK_JWT_AUDIENCE=          # optional; leave empty to skip aud check
CLERK_SECRET_KEY=sk_test_... # required only for outbound Clerk REST calls
CLERK_WEBHOOK_SECRET=whsec_... # required for /v1/webhooks/clerk verification
```

If `CLERK_JWT_ISSUER` is missing, every request fails with
`401 auth_not_configured`.

---

## Error envelope

All 4xx responses follow:

```json
{ "error": "<code>", "message": "...", "correlation_id": "..." }
```

| Code                       | When                                                          |
|----------------------------|---------------------------------------------------------------|
| `not_signed_in`            | Missing or malformed `Authorization` header.                  |
| `auth_not_configured`      | Backend env vars missing.                                     |
| `malformed_token` / `missing_kid` | JWT failed structural parse.                           |
| `unknown_kid` / `jwks_unavailable` | Signing key not in JWKS even after force-refresh.     |
| `invalid_signature`        | Signature did not verify against the resolved key.            |
| `invalid_issuer` / `invalid_audience` | Claims don't match configured values.               |
| `token_expired`            | `exp` is in the past.                                         |
| `missing_email` / `missing_email_verified` | Custom template doesn't expose required claims.|
| `email_not_verified`       | Write endpoint hit with `email_verified=false` (FR-017).      |
| `no_active_baby`           | Endpoint requires `X-Active-Baby-Id` and none was supplied.   |

---

## Browser → Clerk network traffic

When debugging in DevTools, filter the Network tab by `clerk.accounts.dev`
to isolate Clerk traffic.

| Endpoint                                                         | Layer            | Cadence                         |
|------------------------------------------------------------------|------------------|----------------------------------|
| `GET /v1/environment`                                            | Static config    | Once per page load               |
| `GET /v1/client`                                                 | Browser state    | Once per page load + after auth  |
| `POST /v1/client/sign_ins/{id}/attempt_first_factor`             | Sign-in flow     | Once per sign-in                 |
| `POST /v1/client/sessions/{sessionId}/touch`                     | Liveness ping    | ~1× per minute while tab focused |
| `POST /v1/client/sessions/{sessionId}/tokens/momdiary-default`   | Token mint       | ~1× per 50 s of API activity     |

Detail:

* **`GET /v1/environment`** — Clerk instance configuration (enabled auth
  strategies, social providers, branding, allow-list of JWT templates).
  The widget needs this before it can render. Cached by the SDK.
* **`GET /v1/client`** — The browser's current Clerk Client object: array
  of active sessions, any in-progress sign-in / sign-up attempt, and
  `last_active_session_id`. Drives `isSignedIn` and `useUser()`. Empty
  client = signed out.
* **`attempt_first_factor`** — Submits the user's first auth factor for
  an existing sign-in attempt (password, email code, magic link, OAuth
  callback). On success the response contains `created_session_id` and a
  `Set-Cookie: __session=...`. MFA users follow up with
  `attempt_second_factor`.
* **`touch`** — Heartbeat that keeps the session from expiring on the
  inactivity timeout (default 7 days). Returns a fresh session + user
  snapshot so the SDK picks up profile edits or admin revocations made
  elsewhere. Pauses when the tab is backgrounded.
* **`tokens/momdiary-default`** — The only endpoint that gates backend
  access. Mints a fresh RS256 JWT from the named template. The SDK
  attaches it to the next outbound `localhost:8000/...` request as
  `Authorization: Bearer ...`. **404 here means the template name is
  wrong or not yet created in the Clerk dashboard** (case-sensitive:
  `momdiary-default`).

### Triage table

| Symptom                                                | Likely cause                                       |
|--------------------------------------------------------|----------------------------------------------------|
| `tokens/momdiary-default` → **404**                    | Template missing or misnamed in Clerk dashboard.   |
| `tokens/momdiary-default` → **200**, backend → **401** | `CLERK_JWT_ISSUER` / template claims misconfigured.|
| No `tokens/...` call before a backend request          | `setTokenProvider` not wired in `ClerkTokenBridge`.|
| Backend call has no `Authorization` header             | `isSignedIn` was `false` when the request fired.   |
| `client` returns empty after a successful sign-in      | Third-party cookies blocked (custom domain in prod).|

---

## Backend → Clerk network traffic

The backend is **mostly networkless**:

* JWKS is fetched on cold start and on a `kid` miss (de-duplicated by an
  `asyncio.Lock`), then cached for `CLERK_JWKS_CACHE_TTL_SECONDS`
  (default 3600 s).
* Webhook verification (`POST /v1/webhooks/clerk`) is signature-only and
  never calls Clerk back.
* Outbound Clerk REST calls (via `CLERK_SECRET_KEY`) are reserved for
  future admin operations; none are made today.

---

## Lazy provisioning

On the first verified request for a new `clerk_user_id`,
`get_current_user` inserts a row into `users` mirroring `email` and
`email_verified_at` from the JWT. Subsequent requests update these
fields if the claims have changed (e.g. the user verified their email
since last seen).
