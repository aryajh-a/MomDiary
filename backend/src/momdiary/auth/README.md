# `momdiary.auth` — feature 006

In-process authentication primitives for caregiver accounts.

| Module          | Purpose                                                                     |
|-----------------|------------------------------------------------------------------------------|
| `hasher.py`     | Argon2id `PasswordHasherService` + constant-time `dummy_verify`.             |
| `sessions.py`   | `SessionService.create / get_active / touch / revoke` (rolling 30 d).        |
| `dependencies.py` | `current_user` + `require_active_baby` FastAPI dependencies.               |
| `middleware.py` | `OriginCsrfMiddleware` (SameSite=Lax companion) + `AuthLogContextMiddleware`.|

See `specs/006-user-and-baby-profiles/{research.md, data-model.md, contracts/}`.

## Cookie

Name `momdiary_session`. Attributes: `HttpOnly; Secure; SameSite=Lax;
Path=/; Max-Age=2592000` (30 days, refreshed each request via `Set-Cookie`
on the success path).

## Error envelope

Every 4xx raised here follows:

```json
{ "error": "<code>", "message": "...", "correlation_id": "..." }
```

Codes: `unauthenticated`, `invalid_credentials`, `invalid_input`,
`no_active_baby`, `not_found`, `conflict`, `csrf_blocked`.
