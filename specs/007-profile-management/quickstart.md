# Quickstart — Profile Management

Date: 2026-05-23
Feature: [spec.md](./spec.md)
Plan: [plan.md](./plan.md)

This quickstart walks a developer (or a manual tester) through exercising the
feature end-to-end against a local dev environment. It assumes feature 006
(authentication + baby profiles) is already running locally.

## Prerequisites

- Backend running: `cd backend; pip install -e ".[dev]"; uvicorn momdiary.main:app --reload --port 8000`
- Frontend running: `cd frontend; npm install; npm run dev` (defaults to `http://localhost:5173`)
- A clean `backend/momdiary.db` is not required — existing accounts work.

## 1. Sign in as a caregiver

1. Open the app at `http://localhost:5173`.
2. If you don't have an account, sign up — pick any email + password.
3. After sign-in, if you have no babies, you'll be prompted to create one
   ("Your first baby"); create one named "Alex" with today's date as DOB.
4. Create a second baby ("Sam", DOB any past date) via the existing
   baby-switcher menu so you have two babies to test removal against.

## 2. Open the Profile screen

1. Tap **Profile** in the bottom tab bar.
2. **Expected**: the screen shows
   - Your **display name** and **sign-in email** in a card at the top.
   - A **list of two babies** ("Alex" and "Sam"), with the currently active
     baby visually distinguished (e.g., badge or accent border).
3. **Negative check**: open the app in an Incognito window and navigate
   straight to the Profile route — the app must redirect to the sign-in page
   without rendering any profile data.

## 3. Edit your own display name (US2)

1. Tap **Edit** on the caregiver card.
2. Change your display name to "Casey".
3. Tap **Save**.
4. **Expected**:
   - Inline spinner during the request; ≤ 2 s.
   - Card returns to read-only mode showing "Casey".
   - The app shell (header / greeting) on the next screen also shows "Casey"
     without a sign-out / sign-in round-trip.
5. **Negative check**: enter `   ` (whitespace) and tap Save → inline error,
   no change persisted, prior value retained on cancel.

## 4. Edit a baby (US3)

1. Tap **Edit** on the "Alex" card.
2. Change the display name to "Alex K." and bump the DOB by one day.
3. Tap **Save**.
4. **Expected**:
   - Card exits edit mode, new values shown.
   - Open the baby switcher (e.g., from the home screen): "Alex K." is the
     name shown.
   - The currently active baby remains the same as before the edit (FR-013).
5. **Negative check**: set DOB to tomorrow → inline error, save rejected.

## 5. Remove a baby (US4) — non-active

1. On the Profile screen, ensure "Alex K." is the **active** baby (use the
   switcher if needed).
2. Tap **Remove** on the "Sam" card.
3. **Expected**: a confirmation dialog appears with the baby's name and a
   plain-language warning that all of the baby's data will disappear.
4. Tap **Cancel**.
5. **Expected**: "Sam" is still in the list; no data changed.
6. Tap **Remove** again, then **Confirm**.
7. **Expected**:
   - "Sam" disappears from the Profile list, from the baby switcher, and from
     all diary surfaces.
   - "Alex K." is still active.

## 6. Remove a baby (US4) — the **active** baby with siblings

1. Re-add a baby called "Sam" from the Profile screen's "Add a baby"
   affordance (US5). It will appear in the list; "Alex K." is still active.
2. Switch the active baby to "Sam" using the baby switcher.
3. Return to Profile, tap **Remove** on "Sam", and **Confirm**.
4. **Expected** (server-side fallback per research §R1):
   - The diary surface does **not** re-lock.
   - The app shell now shows "Alex K." as the active baby within ≤ 1 s
     (no extra user action).

## 7. Remove a baby (US4) — the only remaining baby

1. With "Alex K." now the active baby and the only surviving baby on the
   account, tap **Remove** on the "Alex K." card and **Confirm**.
2. **Expected**:
   - The diary surface re-locks.
   - The app shows the "create your first baby" prompt (same prompt as
     post-sign-up).
   - Any subsequent diary endpoint call returns the standard
     baby-required error.

## 8. Add a baby from the Profile screen (US5)

1. From the empty Profile state (no babies), tap **Add a baby**.
2. Fill the form and submit.
3. **Expected**: the new baby appears in the Profile list and becomes the
   active baby (because the caregiver had zero non-deleted babies at the time).
4. From a state with at least one baby, tap **Add a baby** again, fill the
   form, and submit.
5. **Expected**: the new baby appears in the list; the previously-active baby
   remains active (FR-021).

## 9. Cross-caregiver isolation (FR-022/023)

(Best run from API tooling, not the UI.)

1. As caregiver A, note one of your `baby.id` values from `GET /v1/babies`.
2. Sign out, sign up as caregiver B.
3. As caregiver B, attempt `PATCH /v1/babies/<A's baby id>` with a new display
   name, and `DELETE /v1/babies/<A's baby id>`.
4. **Expected**: both return `404` with a not-found-style body (no leak that
   the baby exists), and caregiver A's baby is unchanged.

## 10. Automated checks

```pwsh
# Backend (from repo root, in PowerShell)
cd backend
$env:PYTHONPATH = "src"
python -m pytest -q --no-cov --ignore=tests/benchmarks

# Frontend
cd ..\frontend
npm test --silent
npm run build
```

All suites MUST pass; the new Profile tests MUST cover the scenarios above.
