# Phase 0 — Research: Profile Management

Date: 2026-05-23
Feature: [spec.md](./spec.md)
Plan: [plan.md](./plan.md)

The feature spec contains **no `[NEEDS CLARIFICATION]` markers**, so Phase 0 is
short: it captures the small set of design decisions that govern the
implementation and the alternatives considered.

---

## R1. Server-side vs client-side active-baby fallback on remove

**Decision**: Do the fallback **server-side**, inside `BabyService.soft_delete`.
When the deleted baby was the owner's active baby, pick the **most-recently-created
surviving non-deleted baby** owned by the same user and set it as the new
`active_baby_id`. If there is none, leave `active_baby_id = NULL` (matches
feature 006 FR-011 fallback behavior for sign-in).

**Rationale**:

- Single atomic transaction (delete + reassign) avoids a half-state window
  where the UI sees "no active baby" for a few hundred ms.
- Matches feature 006 FR-011 ("fall back to the most-recently-created surviving
  baby") — same selection rule reused at delete time gives one mental model.
- No extra round-trip from the client; satisfies spec SC-005 (≤ 1 s).
- Keeps the rule testable as a pure service-layer unit test.

**Alternatives considered**:

- *Client-side fallback after delete*: would require list → pick → POST
  active-baby, three sequential requests. Rejected: visible flicker, harder
  test surface (relies on client retries), and duplicates the FR-011 rule on
  the client.
- *True "most-recently-used" via per-baby usage timestamp*: requires a new
  column and per-write update. Rejected as out of proportion to the value for
  v1; "most-recently-created" is the documented FR-011 fallback and the spec
  US4 acceptance criteria do not require true LRU.

---

## R2. Reuse of existing endpoints (no new HTTP surface)

**Decision**: Consume only the existing feature-006 endpoints. **Do not** add
any new route under `/v1/users/*` or `/v1/babies/*` for this feature.

| Need                              | Endpoint                          | Method | Already exists? |
|-----------------------------------|-----------------------------------|--------|-----------------|
| List own babies                   | `/v1/babies`                      | GET    | Yes (006)       |
| Show own caregiver record         | `/v1/auth/me`                     | GET    | Yes (006)       |
| Edit own display name             | `/v1/users/me`                    | PATCH  | Yes (006)       |
| Edit baby display name / DOB      | `/v1/babies/{id}`                 | PATCH  | Yes (006)       |
| Remove (soft-delete) a baby       | `/v1/babies/{id}`                 | DELETE | Yes (006)       |
| Add a baby (re-entry point only)  | `/v1/babies`                      | POST   | Yes (006)       |
| Set active baby (manual switch)   | `/v1/users/me/active-baby`        | POST   | Yes (006)       |

**Rationale**: The spec's functional requirements all decompose into operations
already covered by feature 006. Inventing new routes would duplicate guard
logic (`CurrentUserDep`, owner check in `BabyService.get_owned`) for no new
behavior. Keeps Principle IV (modular architecture) honest.

**Alternatives considered**:

- *New "profile bundle" endpoint that returns caregiver + babies in one call.*
  Rejected: two round-trips (`/v1/auth/me` + `/v1/babies`) are already cached
  by TanStack Query; merging them is premature optimisation and would create
  a duplicate authoritative source for fields that today have one.

---

## R3. Frontend state & cache strategy

**Decision**: Use TanStack Query v5 with the existing `apiClient`:

- Query keys: `["auth", "me"]` and `["babies"]` (both already exist elsewhere
  in the app).
- Mutations: `updateMe`, `updateBaby`, `deleteBaby` invalidate the relevant
  query keys on success. `deleteBaby` additionally invalidates `["auth", "me"]`
  to pick up the new `active_baby_id` chosen server-side (per R1).
- No optimistic updates for v1: the round-trip is fast enough, and the
  shell-name update is driven by the refetched `auth.me` so the rendered
  source of truth never lies.

**Rationale**: Consistent with how `BabySwitcher` and `FirstBabyPrompt`
already use TanStack Query in this codebase; new feature inherits the same
discipline.

**Alternatives considered**:

- *Local optimistic update for caregiver display name*: marginal UX gain; risks
  a 500 ms stale render if the network is slow but server validation accepted.
  Rejected for v1 in favour of "the refetch is the source of truth".

---

## R4. Remove-baby confirmation UX

**Decision**: Modal dialog that:

1. Names the baby being removed (display name).
2. States, in plain language, that the baby and all its data will disappear
   from every view.
3. Requires a deliberate "Remove" button press (no Enter-key auto-submit).
4. Disables the Remove button while the request is in flight.

**Rationale**: FR-015 requires explicit confirmation that "clearly explains
the consequences". A modal with no auto-submit is the lightest pattern that
clears the bar and matches the destructive-action conventions used in the
existing app.

**Alternatives considered**:

- *Type-the-name-to-confirm pattern.* Rejected as friction-heavy for a v1
  consumer app; reserved for irreversible operations (account self-delete
  belongs to a future feature).
- *Inline slide-to-confirm.* Rejected as harder to make accessible.

---

## R5. Validation reuse

**Decision**: Reuse the validation rules already enforced by `BabyCreate` /
`BabyUpdate` (Pydantic) and `UserUpdate`. The frontend forms perform the same
checks client-side for instant feedback (non-empty display name; date of birth
not in future; length limits), but the server is the source of truth.

**Rationale**: Avoids drift between client and server. No new schemas
introduced; spec FR-006/010/011 are already encoded server-side.

**Alternatives considered**:

- *Add zod schemas for these requests on the client.* The existing client
  already has zod schemas for the response types; request validation can
  remain a thin React-side function for now. May revisit when forms grow.

---

## R6. Tests-first plan (Principle II)

| Tier            | Target                                                 | New / Extend |
|-----------------|--------------------------------------------------------|--------------|
| Unit (backend)  | `BabyService.soft_delete` fallback-activation rule     | New cases    |
| Integration (backend) | `DELETE /v1/babies/{id}` returns 200 and `/v1/auth/me` then reports the fallback as `active_baby_id` | New          |
| Integration (backend) | `DELETE /v1/babies/{id}` on the user's **only** baby leaves `active_baby_id = NULL` and subsequent diary reads 4xx until a new baby is created | New          |
| Authorization (backend) | `PATCH /v1/babies/{id}` and `DELETE /v1/babies/{id}` against a baby owned by another user return not-found-style | Extend       |
| Frontend unit   | `useProfileQueries` mutation invalidation                | New          |
| Frontend integration | ProfilePage renders caregiver + babies; edit caregiver display name reflects in shell; edit baby reflects in switcher; remove with cancel preserves state; remove with confirm hides baby and (when active) activates fallback in shell | New          |

All tests authored failing first, then made to pass — per constitution Principle II.

---

## R7. Mobile-app considerations (forward look only)

**Decision**: No mobile-specific code in this feature. The new `ProfilePage`
uses the same Tailwind utility set and `max-w-md` shell as the rest of the
app; a future React Native / Capacitor wrapper can reuse this surface
unchanged. No native APIs are touched.
