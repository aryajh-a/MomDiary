# Feature Specification: Profile Management (Caregiver & Babies)

**Feature Branch**: `007-profile-management`
**Created**: 2026-05-23
**Status**: Draft
**Input**: User description: "Allow users to view and manage profile. Profile should show users details and baby details and allow editing/removing them"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Caregiver opens the Profile screen and sees themselves and their babies (Priority: P1)

A signed-in caregiver taps the **Profile** entry in the app shell and lands on a single screen that shows two clearly-labelled sections: **Your details** (display name and the email used to sign in) and **Your babies** (a row per non-deleted baby with display name, date of birth, age derived from date of birth, and the active-baby indicator). The screen is read-only by default; entering an edit affordance is an explicit action.

**Why this priority**: Without a way to see who and what is on the account, none of the manage actions are meaningful. This is the only surface that makes the data already in the system visible to the caregiver.

**Independent Test**: A caregiver who already has at least one baby opens the Profile screen and sees their own display name + email and a list containing each of their non-deleted babies with the correct active-baby badge — without making any changes.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver with one or more non-deleted babies, **When** they open the Profile screen, **Then** the screen shows their display name, sign-in email, and a list with every non-deleted baby they own.
2. **Given** a caregiver with no non-deleted babies, **When** they open the Profile screen, **Then** the "Your babies" section shows an empty state with an "Add a baby" call to action and the rest of the screen still renders normally.
3. **Given** a caregiver with an active baby, **When** they open the Profile screen, **Then** the active baby is visually distinguished from the others in the list.
4. **Given** an unauthenticated visitor, **When** they attempt to reach the Profile screen, **Then** the app redirects them to sign-in and shows no profile data.

---

### User Story 2 — Caregiver edits their own display name (Priority: P1)

From the Profile screen the caregiver can enter an edit affordance on their own details, change their display name, save it, and see the new name reflected immediately everywhere it appears in the app shell (header, greeting strip, baby switcher menu, etc.). The sign-in email is shown as a read-only piece of identity in this feature.

**Why this priority**: Display name is the most visible piece of personalisation. Editing it is the first thing caregivers try after seeing the Profile screen, and getting it wrong (or being unable to change it) is a credibility hit.

**Independent Test**: A caregiver renames themselves on the Profile screen, navigates away to any other screen that shows their name, and observes the new name without re-signing-in.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver on the Profile screen, **When** they enter the edit affordance on "Your details", change the display name to a valid value, and save, **Then** the screen exits edit mode and shows the new display name.
2. **Given** the just-saved display name, **When** the caregiver navigates to any other screen that shows their name, **Then** that screen shows the new name within the current session (no sign-out / sign-in required).
3. **Given** an empty or whitespace-only display name, **When** the caregiver tries to save, **Then** the save action is rejected with a clear inline message and the prior value is retained.
4. **Given** a display name longer than the supported length, **When** the caregiver tries to save, **Then** the save action is rejected with a clear inline message indicating the length limit.
5. **Given** the caregiver entered edit mode and changed the name, **When** they cancel instead of saving, **Then** the prior value is restored and no change is persisted.

---

### User Story 3 — Caregiver edits a baby's profile (Priority: P1)

From the Profile screen the caregiver can open any baby row, edit the baby's display name and date of birth, save the changes, and see them reflected in every other surface that names that baby (baby switcher, daily lists, chat header, history pages). Editing a baby does not change which baby is currently active.

**Why this priority**: Babies are the unit of data scoping; their names and dates of birth feed every other view. A typo at sign-up that cannot be corrected is a daily papercut.

**Independent Test**: A caregiver renames a baby on the Profile screen, returns to the home screen, and sees the new name in the baby switcher and the home greeting; the active baby remains the same as before the edit.

**Acceptance Scenarios**:

1. **Given** a caregiver on the Profile screen, **When** they open a baby row, change the display name to a valid value, and save, **Then** the screen exits edit mode and shows the new value.
2. **Given** a caregiver on the Profile screen, **When** they open a baby row, change the date of birth to a valid past or present date, and save, **Then** the screen shows the new date and any derived age recomputes.
3. **Given** an invalid display name (empty, whitespace-only, or too long), **When** the caregiver tries to save, **Then** the save is rejected with a clear inline message and the prior values are retained.
4. **Given** a future date of birth, **When** the caregiver tries to save, **Then** the save is rejected with a clear inline message stating the date cannot be in the future.
5. **Given** a successful edit, **When** the caregiver navigates to any other surface that names this baby, **Then** the new name and date of birth are shown without requiring sign-out / sign-in.
6. **Given** a caregiver editing a baby that is not the currently active baby, **When** they save, **Then** the active baby selection is unchanged.

---

### User Story 4 — Caregiver removes a baby (Priority: P2)

From the Profile screen the caregiver can remove (soft-delete) a baby. The action is gated by an explicit confirmation step that clearly states removal hides the baby and its data from every view. After confirmation the baby disappears from the Profile list, from the baby switcher, and from every diary surface. If the removed baby was the active one, the app automatically activates the most-recently-used surviving baby; if none remain the app shows the "create your first baby" prompt as in the post-sign-up flow.

**Why this priority**: Useful for cleaning up duplicate or test profiles and for parents who stop tracking a child. Not on the critical path for first-day use, but expected as the account ages.

**Independent Test**: A caregiver with two babies removes the inactive one, confirms the destructive action, and sees that baby vanish from the Profile list and from the baby switcher while the other baby remains untouched and active.

**Acceptance Scenarios**:

1. **Given** a caregiver with two or more non-deleted babies, **When** they trigger remove on an inactive baby and confirm, **Then** that baby disappears from the Profile list, from the baby switcher, and from every diary surface.
2. **Given** a caregiver with two or more non-deleted babies, **When** they remove the currently active baby and confirm, **Then** the system automatically activates the most-recently-used surviving baby and reflects the change in the app shell.
3. **Given** a caregiver whose only remaining baby is being removed, **When** they confirm, **Then** the diary surface re-locks and the "create your first baby" prompt is shown.
4. **Given** a remove confirmation dialog open on a baby, **When** the caregiver cancels, **Then** the baby remains and no data is touched.
5. **Given** an in-flight diary write under a baby that is being removed in another tab, **When** the remove completes server-side, **Then** the in-flight write either completes against the original baby and is then hidden, or returns a not-found-style response — in no case does it persist new data the caregiver can never reach.
6. **Given** an already-removed baby, **When** any client attempts to read or write against it, **Then** the response is a not-found-style response indistinguishable from never-existed (no leak of soft-deleted state).

---

### User Story 5 — Caregiver adds another baby from the Profile screen (Priority: P3)

The Profile screen exposes an "Add a baby" affordance that reuses the existing add-baby flow. After creation the new baby appears in the Profile list and becomes the active baby if and only if the caregiver had no other non-deleted babies at the time.

**Why this priority**: Adds discoverability for a flow that already exists elsewhere; not critical because the post-sign-up prompt and the baby switcher both already expose creation today.

**Independent Test**: A caregiver with one baby uses the Profile screen's "Add a baby" affordance to create a second baby, returns to the Profile screen, and sees both babies listed with the original baby still active.

**Acceptance Scenarios**:

1. **Given** a caregiver with at least one baby, **When** they use "Add a baby" from the Profile screen and complete the form, **Then** the new baby appears in the list and the previously-active baby remains active.
2. **Given** a caregiver with zero non-deleted babies, **When** they use "Add a baby" from the Profile screen and complete the form, **Then** the new baby appears in the list and becomes active.

---

### Edge Cases

- **Concurrent edit from another device**: caregiver A edits their display name in browser X while still viewing the stale value in browser Y; browser Y's next refresh shows the new value, and a stale save in browser Y is reconciled (last write wins is acceptable for v1).
- **Network failure mid-save**: a save call fails; the form keeps the in-progress edit so the caregiver can retry, and the underlying record is not changed.
- **Removing the currently active baby**: covered explicitly in US4 scenarios 2 and 3.
- **Removing the only baby**: covered explicitly in US4 scenario 3.
- **Display-name collisions**: two of the caregiver's babies can share the same display name; this is allowed and disambiguation is left to the caregiver.
- **Date-of-birth edit changes derived age**: any "age = … months / weeks" badge that depends on date of birth recomputes the next time it is rendered; no extra refresh action is required.
- **Sign-in email shown but not editable**: the caregiver cannot change their sign-in email in this feature; an inline note explains where (if anywhere) to do that and changes are deferred.
- **Session expiry while viewing Profile**: an authenticated read on the Profile screen that fails with a session-expired response redirects the caregiver to sign-in with a recoverable banner; no profile data is shown to the unauthenticated visitor.
- **Cross-caregiver isolation**: caregiver A cannot read or modify caregiver B's babies or own profile under any Profile-screen action; an attempt returns a not-found-style response.
- **Soft-deleted baby never resurfaces**: a removed baby does not reappear in any list, switcher, or chat-history surface, even if a client requests it by its prior identifier.

## Requirements *(mandatory)*

### Functional Requirements

#### View

- **FR-001**: System MUST expose a single Profile surface that, for a signed-in caregiver, shows the caregiver's display name, the caregiver's sign-in email (read-only), and a list of every non-deleted baby they own.
- **FR-002**: System MUST visually identify the currently active baby in the Profile list.
- **FR-003**: System MUST scope every read on the Profile surface to the authenticated caregiver; under no circumstance MUST a caregiver see another caregiver's profile data or babies.
- **FR-004**: System MUST gate the Profile surface behind a valid session; an unauthenticated request MUST be redirected to sign-in and MUST NOT receive profile data.

#### Edit — caregiver

- **FR-005**: Users MUST be able to update their own display name from the Profile surface.
- **FR-006**: System MUST validate the caregiver display name (non-empty after trimming whitespace, within a supported length limit) and MUST reject invalid values with an inline error without persisting.
- **FR-007**: System MUST reflect a successful caregiver display-name update in every surface that shows the caregiver name within the current session, without requiring sign-out / sign-in.
- **FR-008**: The caregiver's sign-in email MUST be shown read-only in this feature; changing the sign-in identifier is out of scope (see Out of Scope).

#### Edit — baby

- **FR-009**: Users MUST be able to update each of their non-deleted babies' display name and date of birth from the Profile surface.
- **FR-010**: System MUST validate baby display name (non-empty after trimming, within a supported length limit) and reject invalid values with an inline error without persisting.
- **FR-011**: System MUST validate baby date of birth (a valid calendar date that is not in the future) and reject invalid values with an inline error without persisting.
- **FR-012**: System MUST reflect a successful baby edit in every surface that shows that baby within the current session, without requiring sign-out / sign-in.
- **FR-013**: Editing a baby MUST NOT change which baby is currently active.

#### Remove — baby

- **FR-014**: Users MUST be able to remove (soft-delete) any of their babies from the Profile surface.
- **FR-015**: A remove action MUST be gated by an explicit confirmation step that clearly explains the consequences (the baby and all its diary data will disappear from every view).
- **FR-016**: Once removed, a baby and its diary rows MUST no longer be returned by any list, day-view, switcher, or chat-history endpoint; this MUST be indistinguishable from the baby never having existed, from the caregiver's point of view.
- **FR-017**: If the removed baby was the currently active baby, System MUST automatically activate the most-recently-used surviving non-deleted baby owned by that caregiver, if any.
- **FR-018**: If the removed baby was the caregiver's last surviving non-deleted baby, System MUST re-lock the diary surface and prompt the caregiver to create a baby (same flow as the post-sign-up first-baby prompt).
- **FR-019**: Removed babies MUST remain in storage for support-side recovery; the recovery path itself is operator-only and is not exposed in this feature's UI.

#### Add — baby (re-use)

- **FR-020**: The Profile surface MUST expose an entry point to the existing add-baby flow; on success the new baby MUST appear in the Profile list within the same session.
- **FR-021**: Adding a baby MUST become active automatically if and only if the caregiver had zero non-deleted babies at the time of the create.

#### Authorisation & data isolation

- **FR-022**: Every write originated from the Profile surface (edit caregiver, edit baby, remove baby, add baby) MUST be authorised against the authenticated caregiver and MUST refuse to act on a baby the caregiver does not own.
- **FR-023**: A caregiver attempting to edit or remove a baby they do not own MUST receive a not-found-style response (does not reveal the baby exists) and a security-audit event MUST be recorded.

#### Observability

- **FR-024**: Every Profile-surface action (view, edit caregiver, edit baby, remove baby, add baby) MUST be logged with the caregiver identifier, the affected baby identifier where applicable, and a correlation identifier, with no credential material in any log line.

### Out of Scope

The following are deliberately not part of this feature; they will be revisited in follow-up features:

- **Caregiver account self-deletion.** A "close my account" affordance is out of scope here for security and recovery reasons; a future feature will define identity-verification, data-export, and irreversibility semantics.
- **Sign-in email change.** Changing the email that identifies the account interacts with credential recovery and verification; deferred.
- **Password / credential change.** Belongs to a dedicated security-settings feature.
- **Restoring a soft-deleted baby.** Recovery exists operator-side per FR-019 but no in-app affordance is offered here.
- **Sharing a baby across caregivers.** Single-owner per baby remains the rule (per feature 006 FR-019).
- **Profile photo / avatar upload.** Display name and an optional non-image colour tag are sufficient for v1.

### Key Entities

- **Caregiver Profile** *(existing, from feature 006)*: the editable display name + read-only sign-in email surface; this feature adds the view + edit UX on top of the existing record.
- **Baby Profile** *(existing, from feature 006)*: the editable display name + date of birth (and optional colour tag) surface, plus the soft-delete flag; this feature adds the view + edit + remove UX on top of the existing record.
- **Active-Baby Preference** *(existing, from feature 006)*: per-caregiver pointer to the currently active baby; this feature reads from and (only on remove of the active baby) writes to it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in caregiver can open the Profile screen and see their own details and their babies within 1 second of tapping the Profile entry point on a typical mobile browser.
- **SC-002**: 95% of caregiver-display-name edits complete (success or rejection) within 2 seconds end-to-end on the development deployment, and the new value is visible in the app shell within the same second.
- **SC-003**: 95% of baby-display-name and baby-date-of-birth edits complete (success or rejection) within 2 seconds end-to-end and are reflected in dependent surfaces (switcher, day view) on the next render within the same session.
- **SC-004**: 100% of baby-removal actions require an explicit confirmation step before any data becomes hidden, verified by UX and automated tests.
- **SC-005**: After removing the currently active baby, the app activates a surviving baby (or shows the "create your first baby" prompt) within 1 second on at least 95% of attempts.
- **SC-006**: Zero cross-caregiver data exposure occurs through any Profile-surface action, verified by automated authorisation tests covering view, edit (caregiver), edit (baby), remove, and add.
- **SC-007**: An unauthenticated request to the Profile surface is redirected to sign-in within 1 second and persists no caregiver or baby data.

## Assumptions

- This feature builds on top of feature 006 (User & Baby Profiles with Authentication). It assumes the caregiver account, baby profile, soft-delete flag, active-baby preference, and the corresponding read / update / delete endpoints (`GET /v1/babies`, `PATCH /v1/babies/{id}`, `DELETE /v1/babies/{id}`, `PATCH /v1/users/me`, `POST /v1/users/me/active-baby`) already exist; this feature adds the Profile UI surface and the user-facing flows that consume them.
- "Manage profile" is interpreted as: **view** own details + babies, **edit** caregiver display name, **edit** baby display name + date of birth, **remove** baby (soft-delete), **add** baby (entry point only — re-uses the existing add-baby flow). Caregiver account self-deletion, sign-in email change, and password change are not part of "manage" in v1 (see Out of Scope).
- "Remove" a baby is implemented as soft-delete (consistent with feature 006 FR-013); the caregiver experiences it as "gone from every view", and operator-side recovery is the safety net.
- The bottom tab bar's existing Profile entry point is the canonical way to reach the Profile screen.
- The existing data-isolation guarantees from feature 006 (every diary table scoped by `baby_id`; every endpoint authorised by `(user_id, baby_id)`) carry over unchanged; this feature does not introduce a new tenant boundary.
- Validation rules (display-name length limits, future-date rejection on date of birth, etc.) reuse whatever the existing create endpoints already enforce; no new validation regime is introduced.
- Mobile-first layout is the default target; the same screen renders acceptably on a desktop browser inside the existing max-width-md app frame.
