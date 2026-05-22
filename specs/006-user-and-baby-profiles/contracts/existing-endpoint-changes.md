# Cross-cutting contract changes for feature 006

This document specifies how feature 006 modifies the contracts of endpoints
that already exist (from features 001 / 003 / 005). The new endpoints live in
`auth-and-profiles.openapi.yaml`; this file is the diff against the existing
ones.

## 1. Authentication is now required everywhere except sign-up, sign-in, and `/health`

| Endpoint | Was | Becomes |
|---|---|---|
| `POST /v1/entries` | Anonymous | Requires session cookie (401 otherwise). Reads / writes are scoped to the resolved active baby. |
| `PUT /v1/entries/{entry_id}` | Anonymous | Requires session cookie. The resolved entry MUST belong to a baby owned by the caller; otherwise 404. |
| `POST /v1/chatentry/` | Anonymous | Requires session cookie. Reads / writes are scoped to the resolved active baby. |
| `GET /v1/feeds` / `GET /v1/sleeps` / `GET /v1/poops` / `GET /v1/appointments` | Anonymous | Require session cookie. Each list endpoint MUST filter by `baby_id = <resolved active baby>` in addition to its existing date / sort filters. |
| `GET /health` | Anonymous | Unchanged. Public. |

## 2. New request header: `X-Active-Baby-Id`

Every baby-scoped endpoint accepts an optional `X-Active-Baby-Id: <baby_id>`
request header. Resolution order:

1. If the header is present and the baby is owned by the caller (and not
   soft-deleted), use it.
2. Else, if `users.active_baby_id IS NOT NULL` and that baby is owned by the
   caller (and not soft-deleted), use it.
3. Else, return `409 Conflict` with `error.code = "no_active_baby"`.

The server does **not** persist `users.active_baby_id` from this header
(persistence is only via `POST /v1/users/me/active-baby`).

## 3. Session-ID partitioning (feature 003 interop)

The existing `X-Session-ID` request/response header on `POST /v1/entries` and
`PUT /v1/entries/{entry_id}` is preserved, but the in-memory store now keys
sessions by the tuple `(user_id, baby_id, session_id)`. Clients should issue a
fresh `X-Session-ID` after a baby switch (the server will not match a prior
session-id across babies, by design).

## 4. New 401 envelope

Any authenticated endpoint, when reached without a valid session cookie,
returns:

```json
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": {
    "code": "unauthenticated",
    "message": "Authentication required."
  }
}
```

## 5. New 404 semantics for cross-tenant probes

Any read or write that targets a `baby_id` or an entry whose `baby_id` is not
owned by the caller MUST return `404 Not Found` with `error.code =
"not_found"`. The 403 status code is reserved for cases where the caller is
authenticated but a server-side policy (not ownership) forbids the action;
ownership failures specifically return 404 to avoid leaking existence
(FR-016).

## 6. New `409 Conflict` envelope for missing active baby

When a baby-scoped endpoint is hit by a caregiver who has no active baby
(e.g., they just signed up and have no baby yet):

```json
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "error": {
    "code": "no_active_baby",
    "message": "Create a baby profile before using this feature."
  }
}
```

The frontend uses this signal to route the user to the "create your first
baby" prompt (US2).

## 7. Observability fields added to existing structured logs

Every authenticated request MUST add two fields to its existing structured
log record:

- `user_id`: the caller's stable user id, or `null` for anonymous requests.
- `baby_id`: the resolved active baby id, or `null` if not applicable.

No credential material (`password_hash`, `momdiary_session` cookie value, raw
cookies) is ever logged.
