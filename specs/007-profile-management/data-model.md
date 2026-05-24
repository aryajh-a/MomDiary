# Phase 1 — Data Model: Profile Management

Date: 2026-05-23
Feature: [spec.md](./spec.md)
Plan: [plan.md](./plan.md)

This feature **introduces no new entities** and **no new columns**. It is a
view/edit/remove surface layered on entities already defined in feature 006
([006-user-and-baby-profiles/data-model.md](../006-user-and-baby-profiles/data-model.md)).
This file summarises the entities the new UI touches and the only behavior
change at the storage boundary (atomic active-baby fallback inside
`BabyService.soft_delete`).

## Entities consumed (all pre-existing)

### `User` (a.k.a. Caregiver Account / Profile)

| Field              | Type    | Editable in this feature?     | Notes |
|--------------------|---------|-------------------------------|-------|
| `id`               | int PK  | No                            | Stable caregiver identifier. |
| `email`            | str     | **No — read-only display**   | Shown on Profile screen; email change is out of scope (spec FR-008). |
| `display_name`     | str     | **Yes** (FR-005)              | Validation reused from feature 006: non-empty after trim, length-limited (existing `UserUpdate` Pydantic schema). |
| `password_hash`    | str     | No                            | Never read or shown by this feature. |
| `active_baby_id`   | int? FK | **Indirectly** (FR-017)       | Mutated server-side as a side effect of remove-baby when the removed baby was the active one. |
| `created_at`       | str     | No                            | |
| `updated_at`       | str     | (auto-updated on save)        | |

### `Baby` (a.k.a. Baby Profile)

| Field              | Type        | Editable in this feature? | Notes |
|--------------------|-------------|---------------------------|-------|
| `id`               | int PK      | No                        | Stable baby identifier. |
| `owner_user_id`    | int FK→User | No                        | Single-owner invariant from feature 006 FR-019 preserved. |
| `display_name`     | str         | **Yes** (FR-009/010)      | Validation reused: non-empty after trim, length-limited (existing `BabyUpdate` Pydantic schema). |
| `date_of_birth`    | ISO date str| **Yes** (FR-009/011)      | Validation reused: not in the future. |
| `color_tag`        | str?        | Optional — out of scope for v1 forms (may be edited via API but no UI control in this feature). |
| `created_at`       | str         | No                        | Used by R1 (fallback chooses **most-recently-created**). |
| `updated_at`       | str         | (auto on save)            | |
| `deleted_at`       | str?        | **Set on remove**         | Soft-delete marker (FR-014/016). Becomes non-null on remove; never re-cleared by this feature. |

### Relationships (unchanged)

- `User 1 — N Baby` via `Baby.owner_user_id` (single owner per baby — feature 006 FR-019).
- `User.active_baby_id → Baby.id` (nullable). After this feature's
  server-side edit, this pointer is auto-rotated by `BabyService.soft_delete`
  when the active baby is removed.

## Storage-boundary behavior change (only change introduced)

`BabyService.soft_delete(baby, *, owner)` MUST atomically:

1. Set `baby.deleted_at = now_iso()`, `baby.updated_at = now_iso()`.
2. If `owner.active_baby_id == baby.id`:
   - Query the owner's surviving (non-`deleted_at`) babies excluding `baby.id`.
   - If any survive: set `owner.active_baby_id` to the one with the **largest
     `created_at`** (most-recently-created surviving baby).
   - Else: set `owner.active_baby_id = NULL`.
   - Update `owner.updated_at = now_iso()`.
3. Flush (caller commits).

Selection rule rationale: matches feature 006 FR-011 sign-in fallback so the
behavior is identical at delete time and at next sign-in.

## State transitions

### Baby

```text
              create
   (∅) ──────────────────►  active (deleted_at = NULL)
                                │
                                │ remove (this feature)
                                ▼
                            deleted (deleted_at = <ts>)   ── terminal in v1
```

Once `deleted_at` is set, the baby never re-surfaces through any read
endpoint (`GET /v1/babies`, diary list endpoints, chat session store).
Operator-side recovery is out of scope for this feature (FR-019).

### User.active_baby_id

```text
   NULL  ──create-first-baby──►  baby_a
   baby_a ──switch──►            baby_b
   baby_b ──remove(baby_b)──►    baby_a (server-side fallback, R1)
   baby_a ──remove(baby_a, last)──► NULL (diary surface re-locks, FR-018)
```

## Migration

**None.** No DDL change, no Alembic revision. The schema as shipped by
feature 006 is sufficient.

## Authorisation invariants exercised

Every Profile-surface read and write MUST satisfy (already enforced by
`CurrentUserDep` + `BabyService.get_owned`):

- The acting principal is the authenticated caregiver (session cookie valid).
- For any baby-scoped operation: `baby.owner_user_id == caregiver.id` AND
  `baby.deleted_at IS NULL`.
- Cross-tenant attempts return a not-found-style response (FR-023) —
  indistinguishable from never-existed.

## Audit / observability

Per FR-024, each Profile-surface action is logged via the existing
structured-log middleware with: `correlation_id`, `user_id`, `baby_id`
(when applicable), action name, and outcome. No new log fields, no new
sink.
