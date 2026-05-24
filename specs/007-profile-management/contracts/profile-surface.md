# Phase 1 — Contracts: Profile Surface

Date: 2026-05-23
Feature: [spec.md](../spec.md)
Plan: [plan.md](../plan.md)

The Profile surface introduces **no new HTTP endpoints**. Every behavior is
expressed through endpoints already defined by feature 006. This document is
the authoritative list of those endpoints **as consumed by this feature**,
plus the **single behavior change** to one of them (atomic active-baby
fallback inside the soft-delete service path — see [research.md §R1](../research.md#r1-server-side-vs-client-side-active-baby-fallback-on-remove)).

All endpoints below require a valid session cookie. Unauthenticated calls
return `401` (existing behavior). All responses include the standard
correlation-id header.

---

## 1. `GET /v1/auth/me`

Read the authenticated caregiver record.

- **Used by**: ProfilePage initial render (Your details card).
- **Response 200**: `{ "user": { "id": int, "email": str, "display_name": str, "active_baby_id": int | null } }`
- **Behavior change in this feature**: none.

## 2. `PATCH /v1/users/me`

Update the caregiver's editable profile fields.

- **Used by**: CaregiverCard edit-and-save (US2).
- **Request**: `{ "display_name": str }`
- **Validation**: `display_name` is non-empty after trim, length-limited (existing rules; see `momdiary.schemas.users.UserUpdate`).
- **Response 200**: same shape as `GET /v1/auth/me`.
- **Errors**: `422` validation failure → returned as inline error in the form. `401` if session expired → redirect to sign-in.
- **Behavior change in this feature**: none.

## 3. `GET /v1/babies`

List the caregiver's non-deleted babies.

- **Used by**: ProfilePage initial render (Your babies list).
- **Response 200**: `{ "items": [ { "id": int, "owner_user_id": int, "display_name": str, "date_of_birth": "YYYY-MM-DD", "color_tag": str | null, "created_at": str, "updated_at": str } ] }`
- **Filtering**: soft-deleted babies are excluded (existing behavior).
- **Behavior change in this feature**: none.

## 4. `POST /v1/babies`

Create a new baby (reused entry point — US5).

- **Used by**: ProfilePage "Add a baby" affordance.
- **Request**: `{ "display_name": str, "date_of_birth": "YYYY-MM-DD", "color_tag": str | null }`
- **Validation**: existing `BabyCreate` rules.
- **Response 201**: single baby object (same shape as a list item).
- **Side effect (existing)**: if caregiver had no `active_baby_id`, the new baby becomes active (existing behavior preserved — FR-021).
- **Behavior change in this feature**: none.

## 5. `PATCH /v1/babies/{id}`

Update a baby's editable fields.

- **Used by**: BabyCard edit-and-save (US3).
- **Request (partial)**: `{ "display_name"?: str, "date_of_birth"?: "YYYY-MM-DD", "color_tag"?: str | null }`
  - This feature's UI only sends `display_name` and/or `date_of_birth`.
- **Validation**: existing `BabyUpdate` rules — non-empty trimmed display name; valid calendar date not in the future.
- **Authorisation**: requires `baby.owner_user_id == caregiver.id` and `baby.deleted_at IS NULL`; otherwise `404` (no leak — FR-023).
- **Response 200**: single baby object.
- **Errors**: `404` cross-tenant / not-found; `422` validation failure.
- **Behavior change in this feature**: none. Editing a baby does **not** change `User.active_baby_id` (FR-013).

## 6. `DELETE /v1/babies/{id}`

Soft-delete a baby. **This is the one endpoint whose internal behavior changes** (HTTP contract unchanged).

- **Used by**: RemoveBabyDialog confirmed remove (US4).
- **Request body**: none.
- **Authorisation**: requires `baby.owner_user_id == caregiver.id` and `baby.deleted_at IS NULL`; otherwise `404` (FR-023).
- **Response 200**: `{ "ok": true }`.
- **Existing behavior preserved**:
  - Sets `baby.deleted_at = <utcnow-iso>`.
  - The deleted baby and its diary rows stop being returned by any list, day-view, switcher, or chat-history endpoint (FR-016).
- **New behavior (this feature)**:
  - **If the deleted baby was the caregiver's active baby** AND the caregiver has at least one other non-deleted baby, set `User.active_baby_id` to the surviving baby with the largest `created_at` (most-recently-created — matches feature 006 FR-011 fallback). All within the same DB transaction.
  - **If no surviving baby exists**, set `User.active_baby_id = NULL` (existing behavior).
  - **If the deleted baby was not the active baby**, do not touch `User.active_baby_id`.
- **Client follow-up**: after a `200`, the frontend re-fetches `GET /v1/auth/me` and `GET /v1/babies` (TanStack Query invalidation) so the app shell reflects the new active baby (or the re-locked diary state).

## 7. `POST /v1/users/me/active-baby`

Set the active baby (manual switch).

- **Used by**: not invoked by the Profile surface in v1 (the active-baby fallback after remove is handled server-side per §6 above). Listed here for completeness because it is referenced by the same screen via the existing `BabySwitcher`.
- **Behavior change in this feature**: none.

---

## Contract tests (per constitution Principle II)

The following contract-level checks MUST exist (new or extended) before
implementation merges:

| # | Endpoint                | Test                                                                                   |
|---|-------------------------|----------------------------------------------------------------------------------------|
| C1 | `PATCH /v1/users/me`    | Valid `display_name` → 200 with updated value.                                         |
| C2 | `PATCH /v1/users/me`    | Empty / whitespace `display_name` → 422.                                              |
| C3 | `PATCH /v1/babies/{id}` | Valid edit by owner → 200 with updated value; `User.active_baby_id` unchanged.        |
| C4 | `PATCH /v1/babies/{id}` | Future `date_of_birth` → 422.                                                          |
| C5 | `PATCH /v1/babies/{id}` | Caller is not the owner → 404 (not-found-style; no leak).                              |
| C6 | `DELETE /v1/babies/{id}` | Delete a non-active baby → 200; `User.active_baby_id` unchanged.                      |
| C7 | `DELETE /v1/babies/{id}` | Delete the active baby with siblings → 200; `User.active_baby_id` becomes the most-recently-created surviving baby. |
| C8 | `DELETE /v1/babies/{id}` | Delete the user's only baby → 200; `User.active_baby_id` becomes `NULL`.              |
| C9 | `DELETE /v1/babies/{id}` | Caller is not the owner → 404 (not-found-style; no leak).                              |
| C10 | All Profile endpoints  | Unauthenticated call → 401; no profile data in body.                                   |

C1, C3–C5, C9, C10 already exist from feature 006 and need only confirmation /
light extension. C2, C6, C7, C8 are new acceptance criteria for this feature.
