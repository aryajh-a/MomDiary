# Existing Endpoint Changes — Feature 008-clerk-auth

This document enumerates how feature 008 modifies endpoints that were
introduced by features 001 (diary endpoints), 003 (chat session header),
006 (auth + babies + scoping), and 007 (profile management). It is the
contract companion to [`clerk-auth.openapi.yaml`](./clerk-auth.openapi.yaml).

---

## 1. Endpoints REMOVED

The following endpoints (introduced by feature 006) are deleted in this
feature. Their functionality is replaced by Clerk's prebuilt
sign-in/sign-up components on the frontend.

| Method | Path | Replaced by |
|---|---|---|
| `POST` | `/v1/auth/register` | Clerk `<SignUp />` (frontend) |
| `POST` | `/v1/auth/login` | Clerk `<SignIn />` (frontend) |
| `POST` | `/v1/auth/logout` | Clerk `signOut()` (frontend) |
| `GET`  | `/v1/auth/me`     | `GET /v1/users/me` (kept) |

---

## 2. Endpoints whose auth shape changes

Every endpoint previously protected by the feature-006 cookie session is
now protected by a Clerk JWT bearer token. The change is entirely in the
dependency chain (`Depends(get_current_user)`) — request and response
bodies are unchanged.

| Method + Path | Auth (before) | Auth (after) | Email-verified gate |
|---|---|---|---|
| `GET    /v1/users/me`                | Cookie | Bearer JWT | NO (read) |
| `PUT    /v1/users/me`                | Cookie | Bearer JWT | NO (profile read/update, no diary write) |
| `PUT    /v1/users/me/active-baby`    | Cookie | Bearer JWT | NO |
| `GET    /v1/babies`                  | Cookie | Bearer JWT | NO (read) |
| `POST   /v1/babies`                  | Cookie | Bearer JWT | **YES** (FR-017) |
| `GET    /v1/babies/{id}`             | Cookie | Bearer JWT | NO (read) |
| `PUT    /v1/babies/{id}`             | Cookie | Bearer JWT | **YES** |
| `DELETE /v1/babies/{id}`             | Cookie | Bearer JWT | **YES** |
| `GET    /v1/feeds`                   | Cookie | Bearer JWT | NO |
| `POST   /v1/feeds`                   | Cookie | Bearer JWT | **YES** |
| `PUT    /v1/feeds/{id}`              | Cookie | Bearer JWT | **YES** |
| `DELETE /v1/feeds/{id}`              | Cookie | Bearer JWT | **YES** |
| `GET    /v1/sleeps`                  | Cookie | Bearer JWT | NO |
| `POST   /v1/sleeps`                  | Cookie | Bearer JWT | **YES** |
| `PUT    /v1/sleeps/{id}`             | Cookie | Bearer JWT | **YES** |
| `DELETE /v1/sleeps/{id}`             | Cookie | Bearer JWT | **YES** |
| `GET    /v1/poops`                   | Cookie | Bearer JWT | NO |
| `POST   /v1/poops`                   | Cookie | Bearer JWT | **YES** |
| `PUT    /v1/poops/{id}`              | Cookie | Bearer JWT | **YES** |
| `DELETE /v1/poops/{id}`              | Cookie | Bearer JWT | **YES** |
| `GET    /v1/appointments`            | Cookie | Bearer JWT | NO |
| `POST   /v1/appointments`            | Cookie | Bearer JWT | **YES** |
| `PUT    /v1/appointments/{id}`       | Cookie | Bearer JWT | **YES** |
| `DELETE /v1/appointments/{id}`       | Cookie | Bearer JWT | **YES** |
| `POST   /v1/appointments/{id}/notes` | Cookie | Bearer JWT | **YES** |
| `POST   /v1/entries`                 | Cookie | Bearer JWT | **YES** (diary write via agent) |
| `PUT    /v1/entries/{id}`            | Cookie | Bearer JWT | **YES** |
| `POST   /v1/chatentry/`              | Cookie | Bearer JWT | **YES** (diary write via direct LLM) |

**Universal contract for the bearer JWT path**:

- Header: `Authorization: Bearer <token>`
- `<token>` MUST be a JWT minted by the `momdiary-default` template against
  the configured Clerk instance.
- Missing / malformed / expired / wrong-issuer / wrong-audience / bad-signature
  → `401` with body `{"error": "not_signed_in", "message": "Please sign in to continue."}`.
- Valid JWT, but `email_verified === false`, on any **write** endpoint
  → `403` with body `{"error": "email_not_verified", "message": "Please verify your email to continue."}`.
- Valid JWT but the caller does not own the targeted `baby_id` (same rule
  as feature 006 FR-016) → `404` (never `403`, to avoid existence-probing).

---

## 3. `X-Session-ID` header on `/v1/entries` and `/v1/chatentry/` (feature 003)

Unchanged in shape. The session key is still
`(user_id, baby_id, session_id)`. `user_id` is now the internal UUID
resolved by `get_current_user` from the Clerk JWT, not the locally-issued
UUID from feature 006.

---

## 4. Logging schema delta

Every protected request's structured log line gets the following fields,
which already existed under feature 006 with different sources:

| Field | Source (before) | Source (after) |
|---|---|---|
| `user_id` | resolved from session cookie | resolved from `sub` claim → `users.clerk_user_id` |
| `clerk_user_id` | (not present) | the JWT `sub` claim |
| `email_verified` | (not present) | the JWT `email_verified` claim |
| `auth_mode` | `cookie` | `clerk_jwt` |

`password_hash`, raw JWTs, and any `Authorization` header values MUST
still be redacted (FR-014, SC-005). Existing structlog processors that
strip these fields remain in place; the JWT redactor is added as a new
processor in the `auth/clerk.py` boundary.
