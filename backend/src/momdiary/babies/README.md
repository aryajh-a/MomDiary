# `momdiary.babies` — feature 006

CRUD service for caregiver-owned baby profiles. All reads/writes are
scoped to `owner_user_id`. Cross-tenant access surfaces as `404 not_found`
(FR-016) — handled by `momdiary.auth.dependencies.require_active_baby`.

See `specs/006-user-and-baby-profiles/data-model.md#babies`.
