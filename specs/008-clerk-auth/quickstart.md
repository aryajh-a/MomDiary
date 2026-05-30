# Quickstart: Clerk-Powered Caregiver Authentication

**Feature**: 008-clerk-auth
**Audience**: Developer validating the feature end-to-end on a clean
workstation. Tests assume the feature has been implemented per
[plan.md](./plan.md).

This quickstart is the manual validation script. The automated equivalents
live under `backend/tests/integration/` and `frontend/src/tests/`.

---

## 1. Prerequisites

- A Clerk application (test environment) with:
  - **Email + password** auth enabled.
  - **Google** social provider enabled (a Google OAuth client registered
    with Clerk's redirect URI).
  - A JWT template named `momdiary-default` whose claims include:
    ```json
    {
      "email": "{{user.primary_email_address}}",
      "email_verified": "{{user.email_verified}}"
    }
    ```
  - A webhook endpoint configured to point at
    `http://localhost:8000/v1/webhooks/clerk` with at minimum
    `user.deleted` and `user.updated` events subscribed. Copy the
    webhook signing secret.
- Backend `.env` (at `backend/.env`) populated with:
  ```ini
  CLERK_SECRET_KEY=sk_test_...
  CLERK_JWT_ISSUER=https://<your-instance>.clerk.accounts.dev
  CLERK_JWT_AUDIENCE=<your-frontend-api-host>
  CLERK_WEBHOOK_SECRET=whsec_...
  ```
- Frontend `.env` (at `frontend/.env.local`):
  ```ini
  VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
  ```
- A clean SQLite DB: delete `backend/momdiary.db` if it exists.

---

## 2. One-time setup

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
pip install -e .
alembic upgrade head        # runs migration 008 (drops legacy auth, truncates data)
uvicorn momdiary.main:app --reload --port 8000
```

In a second terminal:

```powershell
# Frontend
cd frontend
npm install                  # picks up @clerk/clerk-react
npm run dev
```

Browse to `http://localhost:5173`.

---

## 3. Scenario walkthroughs

### S1 — New caregiver signs up with email + password (FR-001, FR-002, FR-005, FR-017)

1. From the landing page, click **Sign up**.
2. Confirm the URL bar shows `http://localhost:5173/sign-up` (still on the
   MomDiary domain — Clarification Q4).
3. The Clerk `<SignUp />` component renders. Enter an email + password and
   submit.
4. Open the email inbox; click the verification link. Return to the app.
5. Confirm you land on the in-app home/baby-profile creation screen.
6. Open the database:
   ```powershell
   sqlite3 backend/momdiary.db "SELECT id, email, clerk_user_id, email_verified_at FROM users;"
   ```
   Exactly one row exists; `clerk_user_id` is populated; `email_verified_at`
   is non-null.
7. **Negative gate test (FR-017)**: Repeat steps 1–3 with a fresh email but
   do NOT complete the verification step. Attempt to create a baby. The
   request MUST be rejected with `403 email_not_verified`. The Verify-Email
   banner MUST appear.

### S2 — Returning caregiver signs in with email + password (FR-001, FR-002, FR-009)

1. Click **Sign out** (visible in the signed-in chrome).
2. Click **Sign in**. Confirm URL is `/sign-in` and `<SignIn />` is shown.
3. Enter your existing credentials. Confirm you land back on home with your
   previously-logged data visible.
4. Open DevTools → Network. Inspect any `/v1/*` request: it MUST carry an
   `Authorization: Bearer eyJ...` header and NO session cookie.

### S3 — Sign up with Google in one click (FR-002, FR-018)

1. Click **Sign up** with a different browser profile.
2. Click **Continue with Google** on the embedded form.
3. Complete Google's consent screen.
4. Land in MomDiary. NO email-verification step is shown (FR-018).
5. Immediately create a baby — it MUST succeed (no FR-017 gate).
6. `SELECT email_verified_at FROM users WHERE email = '<google-email>';` is
   non-null.

### S4 — Account deletion cascade (FR-015, FR-016)

1. As a signed-in caregiver, create a baby and log one feed.
2. In the Clerk dashboard, find the user and click **Delete user**.
3. Clerk sends a `user.deleted` webhook to
   `POST /v1/webhooks/clerk`. Tail the backend logs and confirm the
   handler runs without errors.
4. Within seconds, confirm:
   ```powershell
   sqlite3 backend/momdiary.db "SELECT COUNT(*) FROM users;"           # → 0 (or just other test users)
   sqlite3 backend/momdiary.db "SELECT COUNT(*) FROM babies;"          # → 0 for that user
   sqlite3 backend/momdiary.db "SELECT COUNT(*) FROM feeds;"           # → 0 for that user
   ```
5. Re-deliver the same webhook (Clerk dashboard → Webhooks → Redeliver).
   The handler MUST return `200` and make no changes (idempotency).
6. Hold onto a JWT from before the deletion (DevTools). Replay any
   `/v1/feeds` request with it: the response MUST be `401 not_signed_in`
   because the `users` row is gone (FR-016).

### S5 — Cutover data discard (FR-012, SC-004)

If you started this quickstart against an existing database that had
feature-006 data:

1. Before running `alembic upgrade head`, count rows:
   ```powershell
   sqlite3 backend/momdiary.db "SELECT COUNT(*) FROM users;"
   sqlite3 backend/momdiary.db "SELECT COUNT(*) FROM feeds;"
   ```
   Note the numbers.
2. Run the migration.
3. Recount. All counts MUST be zero. The `user_sessions` table MUST no
   longer exist (`SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions';` returns no row).

### S6 — Bearer-less request rejection (FR-008, SC-003)

```powershell
curl.exe -i http://localhost:8000/v1/feeds
```

MUST return `401` with body
`{"error":"not_signed_in","message":"Please sign in to continue."}`.

Same call with a tampered JWT (flip one byte in the signature): MUST also
return `401`.

### S7 — Session-expiry mid-use (Edge Case)

1. While signed in, in DevTools, set the system clock forward by 2 hours
   (or wait out the JWT's `exp`).
2. Try to log a feed.
3. The request MUST fail with `401`. The frontend MUST surface "Please
   sign in again" and redirect to `/sign-in`.

---

## 4. Performance smoke check

```powershell
cd backend
pytest tests/benchmarks/test_jwt_verify_perf.py --benchmark-only
```

JWT verification (cached JWKS) MUST be ≤ 5 ms p95 on dev hardware.

---

## 5. Log-scan check (SC-005)

```powershell
# After running scenarios S1–S7, scan the backend log file for forbidden material.
Select-String -Path backend\logs\*.log -Pattern "eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\." -CaseSensitive
Select-String -Path backend\logs\*.log -Pattern "password" -CaseSensitive
```

Both MUST return zero matches.
