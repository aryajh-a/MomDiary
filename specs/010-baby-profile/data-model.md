# Data Model: Baby Profile Detail Screen

**Feature**: `010-baby-profile` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)

This feature adds three nullable columns to the existing `babies` table **plus
one new table** (`growth_measurements`) for weight/height history. No existing
column is altered or dropped, so every existing baby row remains valid.


> **2026-06-07 — Growth history re-added.** The 2026-06-05 "single snapshot, no
> history" reduction is **reversed**: weight/height are a tracked series in
> `growth_measurements`, and the profile shows the change (delta) vs the previous
> measurement plus a "last measured" date. Head circumference is **not** modelled.
> `babies.weight_kg` / `babies.height_cm` are retained as a cached "current"
> value (= the latest measurement) for cheap list reads.

Weight and height are stored directly in their display units (kg/cm) — **no
base-unit conversion**, so a view → edit → save round-trip is lossless.

## `babies` — new columns (all nullable)

Extends `momdiary.models.orm.Baby` (existing columns unchanged).

| Column        | Type      | Null | Rule (enforced in Pydantic)                  | Notes |
|---------------|-----------|------|----------------------------------------------|-------|
| `gender`      | `String`  | yes  | `girl` / `boy` / `other`, or null            | FR-009 |
| `weight_kg`   | `Float`   | yes  | `> 0` (sane upper bound, e.g. ≤ 50), or null | cached current (latest measurement), kg (FR-011) |
| `height_cm`   | `Float`   | yes  | `> 0` (sane upper bound, e.g. ≤ 200), or null| cached current (latest measurement), cm |

> No `photo_url` column — photo is deferred (FR-017). No allergies / birth
> weight / birth height columns — deferred to v2.

## `growth_measurements` — new table

One row per measurement event (date + weight + height together). The history of
record; `babies.weight_kg`/`height_cm` cache its latest row. Scoped to a baby
(ownership is enforced via the parent baby, exactly like the diary tables).

| Column        | Type      | Null | Notes |
|---------------|-----------|------|-------|
| `id`          | `Integer` | no   | PK |
| `baby_id`     | `Integer` | no   | FK → `babies.id` (`ondelete=RESTRICT`) |
| `weight_kg`   | `Float`   | yes  | kg, `> 0` (Pydantic) |
| `height_cm`   | `Float`   | yes  | cm, `> 0` (Pydantic) |
| `measured_at` | `Text`    | no   | ISO date (`YYYY-MM-DD`), in the caregiver's timezone |
| `deleted_at`  | `Text`    | yes  | soft-delete (consistent with other tables) |
| `created_at` / `updated_at` | `Text` | no | ISO timestamps |

Index `ix_growth_baby_measured` on `(baby_id, measured_at, deleted_at)` backs
the "latest two measurements" query that computes the delta.

**Write path**: a weight/height edit via `PATCH /v1/babies/{id}` upserts the
measurement for *today* (one row per day) snapshotting the baby's current
weight/height, and refreshes the cached `babies` columns. **Delta** = latest −
previous measurement, per metric (null when there is no prior one).

**Validation layer (decision)**: the enum / range rules on these three columns
are enforced in the **request schemas (Pydantic v2)**, **not** as DB `CHECK`
constraints — the API already rejects bad input with `422` before it reaches
the DB. The migration adds these columns as plain nullable typed columns (no
`ck_babies_*` entries).

**No conversion / no drift**: because `weight_kg` and `height_cm` are stored in
the same units they are displayed and edited in, a view → edit → save
round-trip is lossless by construction (FR-011 / SC-005).

## Relationships

```
User (1) ──owns──> (N) Baby (1) ──has──> (N) GrowthMeasurement
                      └── gender, weight_kg, height_cm  (new nullable cols;
                          weight/height cache the latest measurement)
```

Diary tables (`feeds`, `sleeps`, `poops`, `appointments`) are untouched.

## Migrations

Two new Alembic revisions:

1. `0006_baby_profile_fields.py` (down-revision `0005`): `add_column` ×3 on
   `babies` (`gender`, `weight_kg`, `height_cm`) — plain nullable, **no CHECK
   constraints**.
2. `0007_growth_measurements.py` (down-revision `0006`): `create_table`
   `growth_measurements` + the `(baby_id, measured_at, deleted_at)` index.

No data backfill — new columns default to NULL; the new table starts empty.

## API projection shape (for contracts)

- `BabyPublic` (and therefore the existing `GET /v1/babies` list response)
  gains: `gender`, `weight_kg`, `height_cm` (all nullable) **plus**
  `last_measured_at`, `weight_kg_delta`, `height_cm_delta` (growth summary).
- `BabyUpdate` gains `gender`, `weight_kg`, `height_cm`, all optional, each
  clearable to `null`.
- **No new endpoint** — the profile reads the baby (incl. the growth summary)
  from the existing list response; the only write path is
  `PATCH /v1/babies/{id}`, which also logs the measurement.
