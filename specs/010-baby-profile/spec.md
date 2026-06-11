# Feature Specification: Baby Profile Detail Screen

**Feature Branch**: `010-baby-profile`
**Created**: 2026-06-04
**Status**: Draft
**Input**: User description: "We have a profile section that lists baby names but no profile *for* a baby. Tapping a baby's name should open that baby's profile — showing name, age, born date, gender, date of birth, blood type, weight and height — with an Edit profile option. Must work with multiple babies."

## Clarifications

### Session 2026-06-04

- Q: Should this feature include real baby-photo upload? → A: No. Defer photo storage/upload. The avatar shows a placeholder (icon or initials) and the camera button is a visible but inert "coming soon" affordance.
- Q: Should the chat agent be able to log profile data from free text? → A: No. All profile fields are edited through the typed UI only in this feature. No new agent tool.

### Session 2026-06-07 — Blood type removed (HIPAA); growth history re-added

- Q: Should blood type be collected/stored/displayed? → A: **No.** Blood type is
  removed from scope for HIPAA reasons. FR-010 is withdrawn; the `blood_type`
  column/field/enum is not added anywhere.
- Q: Should weight/height keep a history with a delta (per the original mockup)?
  → A: **Yes — this reverses the 2026-06-05 "single snapshot, no history"
  reduction.** Weight/height are a tracked series (`growth_measurements`, one
  row per measurement date holding both values). The profile shows the current
  value, the **change vs the previous measurement** (↑/↓ delta), and the **last
  measured** date. **Head circumference is excluded.** `babies.weight_kg` /
  `height_cm` are kept as a cached "current" (= latest measurement). Editing
  weight/height in the Edit form logs/updates *today's* measurement.

### Session 2026-06-05 — Scope reduction

- Q: How much of the original mockup (allergies, birth weight/height, growth history with deltas) is in scope? → A: **Reduced.** v1 shows only: name, age, born date, gender, date of birth, current weight, current height, plus Edit. (Blood type was also in this reduced list but was later removed for HIPAA — see 2026-06-07.) **Out for v1:** allergies, birth weight, birth height, and any growth-measurement history / deltas / "last measured" tracking. These move to v2.
- Q: How are weight and height modelled now that there is no growth history? → A: As a **single current snapshot** — two editable fields on the baby (`weight_kg`, `height_cm`). No dated measurements, no deltas, no separate table. _(Superseded 2026-06-07: growth history + deltas are back; the `babies` fields become a cached "current" alongside a `growth_measurements` table.)_
- Q: Gender value set? → A: `girl` / `boy` / `other` (or unset). No neutral `unspecified` value.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Caregiver opens a baby's profile from the Profile list (Priority: P1)

From the Profile surface (which lists every non-deleted baby the caregiver owns), the caregiver taps a baby and lands on a dedicated **Baby Profile** screen for *that* baby. The screen shows, read-only by default: an avatar placeholder, the baby's name, derived age, born date, and the baby's details — gender, date of birth, weight, and height. Fields that have never been filled in render an explicit "not set" placeholder rather than being hidden.

**Why this priority**: This is the core of the request. Without a per-baby profile screen there is nowhere for the baby's details to live; the existing list only shows a name and date of birth.

**Independent Test**: A caregiver with at least one baby opens the Profile list, taps a baby, and sees that baby's name, derived age, born date, gender, date of birth, weight, and height (or explicit placeholders where unset) — without making any changes.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver on the Profile list, **When** they tap a baby, **Then** the app navigates to that baby's profile screen showing the baby's name, derived age, and born date.
2. **Given** a baby with stored gender, weight, and height, **When** the caregiver opens that baby's profile, **Then** every stored value is shown in the correct units (kg / cm).
3. **Given** a baby with one or more of gender / weight / height unset, **When** the caregiver opens that baby's profile, **Then** each unset field shows an explicit placeholder (e.g. "Not set").
4. **Given** a caregiver who owns multiple babies, **When** they open one baby's profile and then return and open another, **Then** each screen shows only that baby's own data with no bleed-through between babies.
5. **Given** an unauthenticated visitor or a baby the caregiver does not own, **When** the profile is requested, **Then** the app redirects to sign-in (unauthenticated) or returns a not-found-style response (not owned) and shows no baby data.

---

### User Story 2 — Caregiver edits a baby's profile (Priority: P1)

From a baby's profile screen the caregiver taps **Edit profile**, changes any of: name, date of birth, gender, weight, height; saves; and sees the values reflected immediately on the profile screen and on every other surface that names the baby (Profile list, baby switcher, daily lists, chat header). Name and date of birth are required; gender, weight, and height are optional and may be cleared back to unset.

**Why this priority**: A profile that can only be viewed is half a feature; the request explicitly calls for an Edit profile option, and the point is to let caregivers record this information.

**Independent Test**: A caregiver opens a baby's profile, edits gender + weight + height, saves, and sees the new values on the profile and (for name) in the baby switcher — without sign-out/sign-in.

**Acceptance Scenarios**:

1. **Given** a baby profile in view mode, **When** the caregiver taps Edit profile, changes one or more fields to valid values, and saves, **Then** the screen returns to view mode and shows the new values.
2. **Given** the Edit form, **When** the caregiver clears an optional field (gender, weight, height) and saves, **Then** that field is persisted as unset and renders its placeholder.
3. **Given** an empty or whitespace-only name, or a future date of birth, **When** the caregiver tries to save, **Then** the save is rejected with a clear inline message and prior values are retained.
4. **Given** a weight or height that is non-positive or outside a sane range, **When** the caregiver tries to save, **Then** the save is rejected with an inline message and nothing is persisted.
5. **Given** a successful name edit, **When** the caregiver navigates to the baby switcher or a daily list, **Then** the new name is shown without re-authenticating.
6. **Given** the caregiver made edits, **When** they cancel instead of saving, **Then** the prior values are restored and nothing is persisted.
7. **Given** a caregiver editing a baby that is not the currently active baby, **When** they save, **Then** the active-baby selection is unchanged.

---

### Edge Cases

- **All optional fields unset**: the profile renders identity (name/age/born date) plus "Not set" placeholders for gender, weight, and height; the screen is still fully usable.
- **Cross-caregiver isolation**: a caregiver cannot open or edit a baby they do not own; the response is not-found-style and reveals nothing.
- **Stale view across devices**: edits made on device A appear on device B's next fetch; last-write-wins is acceptable for v1.
- **Deleting the baby**: a soft-deleted baby's profile is unreachable (consistent with feature 007 removal semantics); this feature does not change removal.
- **Photo button**: the camera/photo affordance is visible but inert ("coming soon"); tapping it does not error and uploads nothing.
- **Weight/height precision**: values are entered and shown in metric (kg / cm) and stored as entered; a view → edit → save round-trip does not alter the stored value.

## Requirements *(mandatory)*

### Functional Requirements

#### Navigation & view

- **FR-001**: The Profile list MUST make each baby row open that baby's dedicated profile screen when tapped.
- **FR-002**: The baby profile screen MUST show, for the selected baby: an avatar placeholder, display name, age derived from date of birth, born date, gender, date of birth, and a growth section with current weight and height, the change vs the previous measurement (↑/↓ delta), and the last-measured date (FR-019).
- **FR-003**: Unset optional fields (gender, weight, height) MUST render an explicit placeholder rather than being omitted.
- **FR-004**: The profile screen MUST be read-only until the caregiver explicitly taps the Edit affordance.
- **FR-005**: Every read for a baby profile MUST be scoped to the authenticated caregiver; a request for a baby the caregiver does not own MUST return a not-found-style response that does not reveal the baby exists.
- **FR-006**: The profile screen MUST be gated behind a valid session; an unauthenticated request MUST be redirected to sign-in and MUST NOT receive any baby data.
- **FR-007**: With multiple owned babies, each baby's profile MUST show only that baby's data, with no cross-baby bleed-through.

#### Baby attributes

- **FR-008**: The system MUST persist, per baby, the following optional attributes in addition to the existing name and date of birth: gender, weight, and height. All MUST be nullable so existing babies remain valid without them.
- **FR-009**: Gender MUST be constrained to a fixed set of accepted values (girl, boy, other) or unset.
- **FR-010**: _Withdrawn (2026-06-07, HIPAA)._ Blood type is not collected, stored, or displayed. This requirement number is retained (not renumbered) so other FR references stay stable.
- **FR-011**: Weight MUST be stored and displayed in kilograms and height in centimetres; a stored value MUST survive a view → edit → save round-trip unchanged.
- **FR-019** *(2026-06-07)*: The system MUST keep a dated weight/height history per baby. Saving a weight/height edit MUST record a measurement for the current date (one record per day; same-day re-saves update that day's record), snapshotting both values. The profile MUST show, per metric, the change vs the immediately previous measurement (or no delta when there is none) and the date of the latest measurement. Head circumference MUST NOT be collected.

#### Edit profile

- **FR-012**: Caregivers MUST be able to edit name, date of birth, gender, weight, and height from the baby profile screen.
- **FR-013**: The system MUST validate name (non-empty after trimming, within length limit) and date of birth (valid calendar date, not in the future) and MUST reject invalid input with an inline message without persisting.
- **FR-014**: The system MUST validate optional numeric fields (weight, height) as positive and within a sane range, and MUST allow clearing any optional field back to unset.
- **FR-015**: A successful edit MUST be reflected on the profile screen and on every other surface that names the baby within the current session, without sign-out/sign-in.
- **FR-016**: Editing a baby's profile MUST NOT change which baby is currently active.

#### Photo (deferred)

- **FR-017**: The profile screen MUST present an avatar placeholder (icon or initials) and a visible photo/camera affordance that performs no upload in this feature and produces no error when activated.

#### Observability

- **FR-018**: Every baby-profile edit MUST be logged with the caregiver identifier, the affected baby identifier, and a correlation identifier, with no credential material in any log line.

### Out of Scope

- **Allergies, birth weight, birth height** — deferred to v2.
- **Head circumference** — explicitly excluded (2026-06-07).
- **A full measurement-history list / chart / editing past measurements** — the profile shows only current + delta-vs-previous + "last measured"; the underlying `growth_measurements` series is recorded but not browsable in this feature.
- **Baby photo upload / storage / serving** — deferred; placeholder only (FR-017).
- **Chat-agent profile editing** — no agent tool in this feature; typed-UI only.
- **Editing the caregiver's own profile** — owned by feature 007; unchanged.
- **Removing a baby** — owned by feature 007; this feature does not alter removal semantics.
- **Sharing a baby across caregivers** — single-owner rule from feature 006 stands.

### Key Entities

- **Baby Profile** *(existing, from feature 006/007)*: gains three nullable attribute columns — gender, weight, height (weight/height cache the latest measurement). Name and date of birth are unchanged.
- **Growth Measurement** *(new, 2026-06-07)*: a dated weight/height record owned by a baby (`growth_measurements`). One row per measurement date; backs the profile's delta and "last measured". Head circumference is not modelled.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in caregiver can tap a baby in the Profile list and see that baby's profile screen within 1 second on a typical mobile browser.
- **SC-002**: 95% of profile edits complete (success or rejection) within 2 seconds end-to-end and are reflected in dependent surfaces (switcher, day view) on the next render within the same session.
- **SC-003**: Zero cross-caregiver or cross-baby data exposure occurs through any baby-profile read or write, verified by automated authorization tests.
- **SC-004**: An unauthenticated request to a baby profile is redirected to sign-in within 1 second and persists no data.
- **SC-005**: A weight / height value entered in metric survives a view → edit → save → view round-trip with no change, verified by automated tests.

## Assumptions

- Builds on features 006 (accounts + baby profiles), 007 (Profile surface + edit/remove UX), and 008 (Clerk auth). The Profile list, baby ownership, soft-delete, and active-baby preference already exist and are reused unchanged.
- New baby columns are additive and nullable; a single forward Alembic migration adds them, and existing rows remain valid with no backfill.
- The profile screen reads the baby from the already-loaded babies list (no new single-baby read endpoint is required); the only new server behavior is the extended `PATCH /v1/babies/{id}`.
- Metric units (kg / cm) are the display standard; imperial display is out of scope.
- Mobile-first layout inside the existing max-width app frame; the same screen renders acceptably on desktop.
- Validation reuses the existing strict-schema / future-date-rejection conventions already used by the create/update baby endpoints.
