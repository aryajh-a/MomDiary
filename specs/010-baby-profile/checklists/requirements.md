# Spec Quality Checklist: Baby Profile Detail Screen

**Feature**: `010-baby-profile` | **Spec**: [../spec.md](../spec.md)

## Content & scope

- [x] Single, clearly-bounded user-facing capability (per-baby profile view + edit).
- [x] Out-of-scope items are explicit (allergies, birth weight/height, growth history, photo, agent).
- [x] Clarifications recorded with date and resolution (scope reduction, snapshot weight/height, gender, photo, agent).
- [x] Builds on named prior features (006/007/008) without re-specifying them.

## Requirements quality

- [x] Each FR is testable and singular.
- [x] Validation rules stated (name, future DOB, positive weight/height, enums).
- [x] Authorization & isolation requirements present (FR-005/FR-007).
- [x] Nullability / backward-compat for existing baby rows stated (FR-008).
- [x] Units defined and round-trip guaranteed (FR-011 / SC-005).

## User stories & acceptance

- [x] Stories are prioritised (P1 view, P1 edit) and independently testable.
- [x] Each story has acceptance scenarios in Given/When/Then form.
- [x] Edge cases enumerated (all-unset, isolation, stale view, inert photo, precision).

## Success criteria

- [x] Measurable outcomes with latency targets (SC-001/SC-002).
- [x] Security/isolation criterion (SC-003).
- [x] Auth-gate criterion (SC-004).
- [x] Data-integrity criterion for the value round-trip (SC-005).

## Resolved questions

- [x] **Scope** (2026-06-05): reduced to name, age, born date, gender, DOB, current weight, current height + Edit. Allergies / birth weight / birth height / growth history → v2. (2026-06-07: blood type also removed for HIPAA.)
- [x] **Weight & height model** (2026-06-05): single current snapshot fields on the baby (no table, no deltas), stored in kg/cm directly.
- [x] **Gender value set** (2026-06-04): `girl` / `boy` / `other` (+ null).
- [x] **Validation layer**: Pydantic for the four new columns (plain nullable columns, no DB CHECK, no batch rebuild).
- [x] **Read path**: reuse `GET /v1/babies` list cache; no new single-baby endpoint.

## Open questions

- _(none)_
