# Contracts: Baby Profile Detail Screen

**Feature**: `010-baby-profile` | **Spec**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md)

Conventions inherited from the codebase:

- Strict Pydantic models (`extra="forbid"`, `str_strip_whitespace=True`).
- Errors use the existing envelope `{ "error", "message", "correlation_id" }`.
- Baby-scoped routes go through `CurrentUserDep` and resolve the baby via
  `BabyService.get_owned(user_id, baby_id)`; a miss → `404 not_found`
  (indistinguishable from never-existed — FR-005).
- Writes require `Depends(require_verified_email)` (same gate as existing baby writes).
- Units are **kg / cm on the wire and in storage** — no conversion.

This feature adds **no new endpoints**. It extends two existing shapes.

## A. Extended baby projection — `BabyPublic`

Returned by the existing `GET /v1/babies` (list) and the existing
`PATCH /v1/babies/{id}` response. Gains the profile fields plus a growth summary.

```jsonc
{
  "id": 7,
  "owner_user_id": 1,
  "display_name": "Mia Johnson",
  "date_of_birth": "2025-01-20",
  "color_tag": null,
  "gender": "girl",            // "girl" | "boy" | "other" | null
  "weight_kg": 7.2,            // cached current (latest measurement), or null
  "height_cm": 62.0,           // cached current (latest measurement), or null
  "last_measured_at": "2025-05-10", // ISO date of the latest measurement, or null
  "weight_kg_delta": 0.3,      // latest − previous measurement, or null
  "height_cm_delta": 1.5,      // latest − previous measurement, or null
  "created_at": "...",
  "updated_at": "..."
}
```

The profile screen reads the selected baby (including the growth summary)
straight from the `GET /v1/babies` list cache (already loaded by the Profile
surface) — **no single-baby GET is added**. The delta fields are null when there
is no prior measurement to diff against.

## B. Extended `PATCH /v1/babies/{baby_id}` — `BabyUpdate`

Existing endpoint; body gains the three new optional fields. All fields
optional; the caller PATCHes whichever subset changed. Sending an explicit
`null` clears an optional field (FR-014).

```jsonc
// BabyUpdate (extended)
{
  "display_name": "Mia Johnson",   // existing
  "date_of_birth": "2025-01-20",   // existing, not in future
  "color_tag": null,               // existing
  "gender": "girl",                // new — "girl"|"boy"|"other" or null
  "weight_kg": 7.2,                // new — > 0 or null
  "height_cm": 62.0                // new — > 0 or null
}
```

- **200** → extended `BabyPublic`.
- **422 validation_error** on: future `date_of_birth`, bad `gender` enum,
  non-positive or out-of-range `weight_kg` / `height_cm`.
  Inline-friendly `message`.
- **404 not_found** when the baby is not owned / does not exist.
- `User.active_baby_id` is never changed by this call (FR-016).
- **Growth side effect**: when `weight_kg` or `height_cm` changes, the call
  upserts a `growth_measurements` row for *today* (one row per day) and the
  response's `last_measured_at` / `*_delta` reflect it. A name/DOB/gender-only
  edit logs no measurement.

## C. Frontend type/zod additions (`frontend/src/shared/types.ts`)

- Extend `babySchema` with `gender`, `weight_kg`, `height_cm`,
  `last_measured_at`, `weight_kg_delta`, `height_cm_delta` (all `.nullable()`).
- Extend `babyUpdateSchema` with `gender`, `weight_kg`, `height_cm` (all
  `.optional()`, `.nullable()` where clearable). The delta/last-measured fields
  are read-only projection — not in the update body.
- Enum: `genderSchema = z.enum(["girl","boy","other"])`.

No new client methods are required beyond the existing `listBabies` /
`updateBaby`.

## D. Authorization matrix

| Route                       | Auth      | Owner check | Verified-email gate |
|-----------------------------|-----------|-------------|---------------------|
| `GET /v1/babies` (existing) | required  | scoped to caller | no (read)      |
| `PATCH /v1/babies/{id}`     | required  | yes (404)   | yes                 |
