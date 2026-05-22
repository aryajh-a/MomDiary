# Feature Specification: User & Baby Profiles with Authentication

**Feature Branch**: `006-user-and-baby-profiles`
**Created**: 2026-05-21
**Status**: Draft
**Input**: User description: "Add features for profile creation for users. New users should create a profile and then use login credential to login. Once logged in, user should add profile of baby and then all the functionalities happen in context of that baby"

## Clarifications

### Session 2026-05-21

- Q: Which authentication mechanism should the app use? → A: Email + password (local), Argon2id-hashed, server-issued HttpOnly session cookie.
- Q: Can a baby profile be shared by multiple caregivers? → A: No — one caregiver owns each baby in v1; sharing deferred.
- Q: What happens to existing diary rows on rollout? → A: Hard-delete on rollout (pre-production test data).
- Q: How long does an authenticated session last? → A: Rolling 30-day session, sliding renewal on each authenticated request.
- Q: Must email be verified before sign-in is allowed? → A: No — v1 enables sign-in immediately after registration; verification deferred.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — New caregiver creates account and signs in (Priority: P1)

A first-time caregiver lands on MomDiary, registers a new account (providing a display name and login credential), and is taken to a signed-in state. Returning to the app on the same or another device they sign in with their credential and reach the same signed-in state. While signed out, the diary surface is gated behind a sign-in / sign-up screen.

**Why this priority**: Without a way to register and sign in, no other personalization is possible. This is the foundation every other story builds on.

**Independent Test**: A brand-new caregiver completes the sign-up form, sees the post-signup landing screen (the "add your first baby" prompt), signs out, signs back in with the same credential, and reaches that same landing screen — all without touching any baby or diary data.

**Acceptance Scenarios**:

1. **Given** an anonymous visitor, **When** they submit valid sign-up details, **Then** an account is created and they are signed in with a fresh session.
2. **Given** a previously-registered caregiver, **When** they submit correct credentials, **Then** they reach the same signed-in state and see their existing babies/data.
3. **Given** an anonymous visitor, **When** they navigate to any diary section (feeds, sleeps, poops, appointments, chat), **Then** the app redirects them to the sign-in screen and persists no diary data.
4. **Given** a signed-in caregiver, **When** they sign out, **Then** the session is invalidated, any locally cached diary data is cleared, and subsequent API calls return an unauthenticated error.
5. **Given** sign-up details that violate a credential rule (e.g., weak password, malformed identifier, already-used identifier), **When** the caregiver submits the form, **Then** the app shows a clear inline error and no account is created.

---

### User Story 2 — Caregiver adds their first baby and logs data under that baby (Priority: P1)

Immediately after signing in, a caregiver with no baby profile is prompted to create one (display name and date of birth at minimum). The newly-created baby becomes the active baby for the session. All subsequent reads (date-scoped lists of feeds / sleeps / poops / appointments) and writes (chat-driven entries, direct-LLM dispatch, and explicit corrections) operate within the context of that active baby; data belonging to one baby is never visible to another.

**Why this priority**: A signed-in account with no baby is useless — the entire app revolves around tracking one baby. This is the first moment of real value.

**Independent Test**: A signed-in caregiver with zero babies creates one, then logs a feed via chat. The feed appears under the new baby's daily list; a freshly-created second baby (later) starts empty and never sees the first baby's feed.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver with no baby, **When** they open the app, **Then** they are prompted to create a baby profile before any diary surface is interactable.
2. **Given** a signed-in caregiver, **When** they submit a valid baby profile, **Then** the baby is created, becomes the active baby, and the diary surface unlocks.
3. **Given** a caregiver with an active baby, **When** they POST a chat entry (`/v1/entries` or `/v1/chatentry/`), **Then** the resulting feed/sleep/poop/appointment record is durably associated with that baby and only that baby.
4. **Given** a caregiver with an active baby, **When** they GET a daily list (feeds/sleeps/poops/appointments), **Then** only entries belonging to the active baby for the requested local date are returned.
5. **Given** caregivers A and B with babies a and b, **When** A and B both call the same endpoint with identical inputs, **Then** A only sees data for a and B only sees data for b; no cross-tenant data leakage occurs.

---

### User Story 3 — Returning caregiver signs in and resumes where they left off (Priority: P2)

A returning caregiver signs in and is immediately placed back into the same active baby they last used (or the most-recently-created baby if no preference is recorded). They can sign out at any time from the app shell.

**Why this priority**: Saves the caregiver from re-selecting their baby on every login. Required for a smooth daily-use experience but not blocking initial adoption.

**Independent Test**: A caregiver signs in, switches active baby (US4), signs out, signs back in on the same or another browser, and lands directly on that same active baby's view without any prompt.

**Acceptance Scenarios**:

1. **Given** a returning caregiver with one or more babies, **When** they sign in, **Then** the app restores the last active baby for that user.
2. **Given** a returning caregiver whose last-active baby has been deleted, **When** they sign in, **Then** the app falls back to the most-recently-created surviving baby or to the "create a baby" prompt if none remain.
3. **Given** a signed-in caregiver, **When** they click sign out, **Then** the session is invalidated server-side, locally cached lists are cleared, and the active-baby preference is preserved for the next sign-in.

---

### User Story 4 — Caregiver with multiple babies switches between them (Priority: P2)

A caregiver who tracks more than one baby (e.g., siblings) can add additional baby profiles and switch the active baby from the app shell. All subsequent views and chat entries operate against the newly-selected active baby until they switch again.

**Why this priority**: Multi-baby support is a meaningful minority case (twins, foster, siblings) and prevents the app from feeling broken for them, but it is not blocking for single-baby caregivers.

**Independent Test**: A caregiver with babies A and B logs one feed under A, switches to B, logs one feed under B, switches back to A, and sees only A's feed in the day view.

**Acceptance Scenarios**:

1. **Given** a caregiver with two or more babies, **When** they open the baby switcher and select a different baby, **Then** that baby becomes the active baby for all subsequent reads and writes within the session.
2. **Given** an active chat session, **When** the caregiver switches the active baby, **Then** the next chat message is dispatched under the new baby's context and prior chat history is not used as evidence for entries under the new baby.
3. **Given** a baby switch in flight, **When** an in-progress chat-entry request has already been dispatched, **Then** that in-flight request still completes under the original baby (no retroactive re-targeting).

---

### User Story 5 — Caregiver edits their own and their baby's profile (Priority: P3)

A signed-in caregiver can update their own profile (display name and a small number of personal fields) and edit each of their babies' profiles (display name, date of birth, optional photo or color tag). They can also soft-delete a baby, after which that baby's data is hidden from all views but recoverable by support if needed.

**Why this priority**: Edits and soft-deletes are quality-of-life features; they don't gate the core loop but are expected by users over time.

**Independent Test**: A caregiver updates their display name, sees the new name in the shell, then renames a baby and sees the new name in the baby switcher. Soft-deleting a baby removes it from the switcher and from list endpoints without touching the underlying rows.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver, **When** they submit a valid profile edit, **Then** the new value is persisted and reflected immediately in the app shell.
2. **Given** a signed-in caregiver editing a baby, **When** they save valid changes, **Then** the change is persisted and the next read of that baby's data reflects it.
3. **Given** a signed-in caregiver, **When** they soft-delete a baby, **Then** that baby disappears from the switcher, no diary endpoint returns its data, and any active session for that baby is detached.

---

### Edge Cases

- **Last baby deleted while signed in**: caregiver soft-deletes their only baby — the diary surface re-locks and re-prompts for baby creation.
- **Concurrent sessions**: same caregiver signed in on two devices — both see the same active baby, edits propagate within a reasonable refresh window.
- **Session expiry mid-action**: caregiver's session expires while composing a chat entry; the entry is not persisted and the caregiver is redirected to sign-in with a recoverable banner.
- **Identifier collision on sign-up**: caregiver attempts to register with an identifier already in use — registration fails with a clear, non-enumerating message.
- **Forgotten credential**: caregiver cannot remember their credential — a recovery path exists but is out of scope for this feature's first slice (see Assumptions).
- **Baby switcher race**: caregiver switches babies while a chat request is still in flight — request completes against the original baby; UI clearly attributes the resulting entry to the correct baby.
- **Pre-existing data on rollout**: all existing owner-less diary rows are hard-deleted by the rollout migration (per FR-018).
- **Two caregivers wanting to share one baby**: out of scope in v1 — they share a single caregiver account in the interim (per FR-019).
- **Caregiver attempts to use a baby they do not own**: API returns a not-found-style response (does not reveal the baby exists) and writes an authorization audit event.
- **Chat session continuity across baby switches**: the in-memory chat session store (feature 003) is partitioned by baby so prior turns of one baby never leak into another's clarification prompts.

## Requirements *(mandatory)*

### Functional Requirements

#### Account & authentication

- **FR-001**: System MUST support new-user registration that captures, at minimum, a unique email-address caregiver identifier and a password.
- **FR-002**: System MUST authenticate users via email + password. Passwords MUST be stored only as Argon2id hashes (never in plaintext or reversible form) and MUST be verified server-side. On successful authentication the server MUST issue an HttpOnly, Secure session cookie scoped to the app.
- **FR-003**: System MUST issue a session credential on successful authentication and MUST invalidate it on explicit sign-out. Sessions MUST have a rolling 30-day idle expiry: each authenticated request slides the expiry forward to 30 days from "now", and a session that goes 30 days without any authenticated request MUST be rejected and treated as signed-out on next use.
- **FR-004**: System MUST gate every diary endpoint and the chat surface behind a valid session; anonymous access MUST be limited to sign-up, sign-in, password/credential recovery (if applicable), and the public health endpoint.
- **FR-005**: System MUST reject sign-up submissions that fail credential-strength rules and MUST present those rules to the caregiver before submission.
- **FR-006**: System MUST never enumerate which identifiers are already registered; sign-up and sign-in failures MUST return a uniform "credential rejected" style of response.
- **FR-007**: System MUST persist relevant security events (sign-up, sign-in, sign-in failure, sign-out, password change if applicable) with caregiver-correlation metadata for support and audit.

#### Baby profiles

- **FR-008**: System MUST require an authenticated caregiver to create at least one baby profile before any diary endpoint becomes operable for that caregiver.
- **FR-009**: System MUST allow a caregiver to create one or more baby profiles, each with at minimum a display name and date of birth.
- **FR-010**: System MUST track an "active baby" per caregiver per session and MUST allow the caregiver to switch it explicitly from the UI.
- **FR-011**: System MUST remember the caregiver's last-active baby across sign-outs and restore it on next sign-in; on a missing/deleted last-active baby it MUST fall back to the most-recently-created surviving baby, or to the "create a baby" prompt if none remain.
- **FR-012**: Users MUST be able to edit each of their baby profiles' display name and date of birth.
- **FR-013**: Users MUST be able to soft-delete a baby profile; soft-deleted babies and their data MUST disappear from every read endpoint and the switcher but MUST remain in storage for support-side recovery.

#### Data scoping (multi-tenant isolation)

- **FR-014**: Every feed / sleep / poop / appointment row MUST be durably attributed to exactly one baby, and that baby MUST be owned by the authenticated caregiver at the time of the write.
- **FR-015**: Every read endpoint (date-scoped lists, chat history surfaces, etc.) MUST filter to the active baby of the authenticated caregiver; under no circumstance MUST a caregiver see another caregiver's or another baby's data.
- **FR-016**: Every write endpoint (`POST`/`PUT /v1/entries`, `POST /v1/chatentry/`, future entry-management endpoints) MUST validate that the resolved or hinted target row (where present) belongs to the active baby; a mismatch MUST return a not-found-style response.
- **FR-017**: The chat session store (feature 003) MUST be partitioned by baby; turns from baby A MUST NOT influence clarification or update-resolution for baby B even within the same caregiver's session.

#### Migration & sharing

- **FR-018**: Existing diary rows present at rollout MUST be hard-deleted as part of the upgrade migration (acceptable because the data is pre-production test data). The migration MUST then add the new baby-owner FK column as `NOT NULL` so the schema can no longer hold owner-less rows.
- **FR-019**: Each baby profile MUST be owned by exactly one caregiver in v1; sharing a baby across multiple caregiver accounts is out of scope for this feature. The data model SHOULD be chosen so that a future many-to-many membership can be introduced without breaking existing rows.

#### Profile editing

- **FR-020**: Users MUST be able to view and update their own caregiver display name.
- **FR-021**: User-profile changes MUST be reflected in the app shell within the same session without requiring re-sign-in.

#### Observability

- **FR-022**: Every authenticated request MUST log the caregiver's stable identifier and the active baby's stable identifier alongside the existing correlation ID, redacting all credential material.

### Key Entities

- **Caregiver Account**: The authentication anchor for a single human caregiver. Holds the unique identifier, credential material (storage-level only — never returned), session-issuance metadata, security audit fingerprints, and the last-active-baby preference. One per real-world caregiver.
- **Caregiver Profile**: The non-credential, caregiver-visible profile fields (display name and similar). Attached one-to-one to a Caregiver Account. Editable by its owner.
- **Baby Profile**: The unit of data scoping. Holds display name, date of birth, and any optional decoration fields (e.g., color tag). Each Baby Profile is owned by exactly one Caregiver Account in v1 (per FR-019). Soft-deletable.
- **Ownership / Membership**: The relationship from a Caregiver Account to a Baby Profile. In v1 this is a single owner reference on the Baby Profile. Carries the soft-delete state.
- **Active-Baby Preference**: The per-Caregiver record of the most-recently-selected Baby Profile. Used to restore context on sign-in.

(All existing diary entities — Feed, Sleep, Poop, Appointment, Appointment Note — gain a required reference to a Baby Profile per FR-014.)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A brand-new caregiver can complete sign-up, create their first baby, and log their first diary entry in under 3 minutes on a typical mobile browser.
- **SC-002**: 95% of sign-in attempts complete (success or rejection) within 2 seconds end-to-end on the development deployment.
- **SC-003**: Zero cross-caregiver and zero cross-baby data leakage occurs in any read or write endpoint, verified by automated authorization tests covering all multi-tenant boundaries.
- **SC-004**: 95% of caregivers who switch the active baby see the dependent surfaces (date lists, chat history) reflect the new baby within 500 milliseconds of the switch confirmation.
- **SC-005**: Returning caregivers land directly in the correct baby context on at least 95% of sign-ins, measured against the last-active-baby preference at the previous sign-out.
- **SC-006**: A signed-out user attempting to reach any diary or chat surface receives the sign-in prompt within 1 second and produces no server-side persistence.

## Assumptions

- The deployment is single-tenant per region; cross-region data residency is out of scope for this feature.
- Caregivers access MomDiary primarily through a modern web browser on a personal device.
- Credential recovery (forgot-password / magic-link reset) UX is acknowledged as required but its detailed flow is deferred to a follow-up feature; this spec only assumes it exists at the operator level (e.g., support-driven reset) at first rollout.
- Email verification on sign-up is out of scope for v1: a freshly-registered caregiver can sign in immediately and email is treated as a unique identifier only, not as a verified recovery channel.
- The existing feature-003 in-memory chat session store will be extended (not replaced) to key sessions by `(caregiver, baby)` rather than caregiver alone.
- All existing diary endpoints (`/v1/entries`, `/v1/chatentry/`, `/v1/feeds`, `/v1/sleeps`, `/v1/poops`, `/v1/appointments`) will keep their URLs; the change is purely the addition of authorization + baby scoping.
- Multi-factor authentication is not in scope for this feature's first slice.
- Email is the user-facing caregiver identifier (per FR-001 / FR-002 resolution).
- Audit / security-event storage reuses the existing structured-log pipeline; no new datastore is introduced for it.
