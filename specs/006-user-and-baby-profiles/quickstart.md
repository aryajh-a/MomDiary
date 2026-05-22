# Quickstart: User & Baby Profiles with Authentication

**Feature**: 006-user-and-baby-profiles
**Audience**: Developers running MomDiary locally to validate the feature end-to-end.

## Prerequisites

- Python 3.12, Node 20+, all existing project prerequisites (Azure OpenAI env vars for `/v1/entries` and `/v1/chatentry/` to work, but not needed for the pure auth/baby-profile loop).
- A clean `backend/momdiary.db` is acceptable. **Note**: this feature's migration **hard-deletes** all existing `feeds`/`sleeps`/`poops`/`appointments` rows on first run (per FR-018).

## 1. Apply the migration

```powershell
cd "d:\Azure AI\MomDiary\backend"
$env:PYTHONPATH = "src"
alembic upgrade head
```

Expected output: a single revision is applied. After completion, `momdiary.db` contains the new `users`, `user_sessions`, `babies` tables, an `active_baby_id` column on `users`, and a `baby_id NOT NULL` column on every diary table. All previously-existing diary rows are deleted.

## 2. Start the backend

```powershell
cd "d:\Azure AI\MomDiary\backend"
$env:PYTHONPATH = "src"
uvicorn momdiary.api.main:app --reload
```

## 3. Register and sign in (curl)

```powershell
# Register — sets the momdiary_session cookie in cookies.txt.
curl -X POST http://localhost:8000/v1/auth/register `
     -H "Content-Type: application/json" `
     -c cookies.txt `
     -d '{"email":"alice@example.com","password":"correct-horse-battery-staple","display_name":"Alice"}'

# Inspect the current session.
curl http://localhost:8000/v1/auth/me -b cookies.txt
```

Expected: `201` from register, `200` from `/me` with `active_baby_id: null`.

## 4. Create the first baby

```powershell
curl -X POST http://localhost:8000/v1/babies `
     -H "Content-Type: application/json" `
     -b cookies.txt `
     -d '{"display_name":"Bobby","date_of_birth":"2026-04-01","color_tag":"indigo"}'
```

Expected: `201` with a baby payload. Because this is the caregiver's first baby, the server also sets `users.active_baby_id` to this baby; subsequent `/v1/auth/me` returns the new id.

## 5. Log the first entry (chat path)

```powershell
$active = (curl http://localhost:8000/v1/auth/me -b cookies.txt | ConvertFrom-Json).active_baby_id
curl -X POST http://localhost:8000/v1/entries `
     -H "Content-Type: application/json" `
     -H "X-Active-Baby-Id: $active" `
     -b cookies.txt `
     -d '{"message":"Bobby had 120ml formula at 8am"}'
```

Expected: `200` / `201` with `outcome: "created"`. Inspect the `feeds` table — the new row carries `baby_id = $active`.

## 6. Validate multi-tenant isolation

```powershell
# Sign up a second caregiver with their own baby.
curl -X POST http://localhost:8000/v1/auth/register `
     -H "Content-Type: application/json" `
     -c cookies2.txt `
     -d '{"email":"carol@example.com","password":"another-strong-passphrase","display_name":"Carol"}'

curl -X POST http://localhost:8000/v1/babies `
     -H "Content-Type: application/json" `
     -b cookies2.txt `
     -d '{"display_name":"Cara","date_of_birth":"2026-05-10"}'

# Carol's feed list MUST NOT include Bobby's feeds.
curl "http://localhost:8000/v1/feeds?date=2026-05-21" -b cookies2.txt
```

Expected: empty list. Try to read Alice's baby from Carol's cookie — must return `404`, never the actual baby.

## 7. Sign out and confirm gating

```powershell
curl -X POST http://localhost:8000/v1/auth/logout -b cookies.txt -c cookies.txt

# Subsequent authenticated calls must return 401.
curl http://localhost:8000/v1/auth/me -b cookies.txt
curl http://localhost:8000/v1/entries -X POST -b cookies.txt `
     -H "Content-Type: application/json" -d '{"message":"x"}'
```

Expected: `401` with `error.code = "unauthenticated"` on both.

## 8. Frontend smoke

```powershell
cd "d:\Azure AI\MomDiary\frontend"
npm run dev
```

Browse to `http://localhost:5173/`:
1. App redirects to `/login`.
2. Sign up; you land on a "create your first baby" prompt.
3. After creating a baby, the diary surface unlocks; the baby switcher shows your baby.
4. Open the chat panel; log an entry; it appears in today's feed list.
5. Sign out from the shell; the app re-locks to `/login`.

## 9. Reset

```powershell
cd "d:\Azure AI\MomDiary\backend"
$env:PYTHONPATH = "src"
alembic downgrade -1  # removes the new schema; existing diary rows already deleted
```

If you want to wipe entirely, delete `momdiary.db` and re-run `alembic upgrade head`.
