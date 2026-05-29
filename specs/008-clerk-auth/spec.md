# Feature Specification: Clerk-Powered Caregiver Authentication

**Feature Branch**: `008-clerk-auth`  
**Created**: 2026-05-27  
**Status**: Draft  
**Input**: User description: "Integrate with Clerk APIs for user authentication. User's auth page should come from Clerk which should allow signup with account creation as well as using google"

## Clarifications

### Session 2026-05-27

- Q: When a caregiver deletes their account in Clerk, what happens to their MomDiary caregiver record, baby profiles, and diary entries? → A: Hard-delete immediately (cascade across caregiver, babies, and all diary entries).
- Q: At cutover, how should pre-existing local-auth caregivers and their baby data be handled? → A: No migration — existing local users, babies, and diary entries are discarded; every caregiver starts fresh through Clerk.
- Q: Should this feature add co-parent / shared-baby access, or keep single-owner? → A: Keep single-owner only; multi-caregiver sharing is explicitly out of scope and deferred to a future feature.
- Q: How are Clerk's sign-in/sign-up surfaces rendered — full redirect, embedded components, or modal? → A: Embedded Clerk components inside MomDiary routes (`/sign-in`, `/sign-up`); users never leave the MomDiary domain.
- Q: What can a freshly-signed-up email/password caregiver do before they verify their email? → A: Nothing that writes data; reads of an empty workspace are fine, but baby creation and all diary writes are blocked until the email is verified. Google sign-ups bypass this gate (Google has already verified the email).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New caregiver signs up with email + password via Clerk (Priority: P1)

A first-time caregiver visits MomDiary, clicks "Sign up", and is taken to the in-app `/sign-up` route where Clerk's prebuilt sign-up component is rendered. They create an account with email + password, verify the email, and land back inside MomDiary already signed in and able to create their first baby profile — without ever leaving the MomDiary domain.

**Why this priority**: This is the on-ramp for every new user. Without it, no one can use the product. It is also the smallest independently shippable slice — once it works, MomDiary has a functioning, externally-managed identity provider and can drop in-house password handling.

**Independent Test**: From a clean browser session, navigate to MomDiary, click "Sign up", complete the embedded Clerk sign-up form at `/sign-up`, verify the email, and confirm the user lands on the in-app baby-profile creation screen with an active authenticated session. No baby data exists yet for this user.

**Acceptance Scenarios**:

1. **Given** a visitor with no MomDiary account, **When** they click "Sign up" on the landing page, **Then** they are taken to MomDiary's `/sign-up` route where Clerk's prebuilt sign-up component renders with MomDiary branding (the browser URL bar still shows the MomDiary domain).
2. **Given** a visitor on the embedded Clerk sign-up form, **When** they submit a valid email + password and complete email verification, **Then** they return to MomDiary as a signed-in user with a new MomDiary caregiver record linked to their Clerk identity.
3. **Given** a visitor submitting a duplicate email, **When** Clerk rejects the sign-up, **Then** the user sees Clerk's standard error message and remains on the sign-up form (no MomDiary record is created).

---

### User Story 2 - Returning caregiver signs in (Priority: P1)

An existing caregiver returns to MomDiary, signs in at the in-app `/sign-in` route (rendered by Clerk's prebuilt sign-in component) using either email + password or "Continue with Google", and resumes access to their previously logged baby data without re-entering any caregiver or baby information.

**Why this priority**: Sign-in is the second half of the auth round-trip. Without it, returning users cannot reach their data — which makes the product unusable beyond the first session. Same priority as P1 because both are required for a usable MVP.

**Independent Test**: With an existing caregiver account already linked to a Clerk identity and at least one baby, sign out, then sign in again at `/sign-in` using each supported method (email/password and Google). Confirm the same caregiver record loads, the active baby selection is restored, and previously logged entries are visible.

**Acceptance Scenarios**:

1. **Given** an existing caregiver, **When** they choose "Sign in" and submit valid email + password on the embedded Clerk sign-in form at `/sign-in`, **Then** they are signed in with their caregiver and baby records intact.
2. **Given** an existing caregiver who originally signed up with Google, **When** they click "Continue with Google" on the embedded Clerk sign-in form, **Then** Google's consent flow runs and they return to MomDiary signed in to the same MomDiary caregiver record.
3. **Given** an unauthenticated visitor, **When** they attempt to load any protected MomDiary page or call any baby-scoped API, **Then** the request is rejected and they are redirected to `/sign-in`.

---

### User Story 3 - Caregiver signs up with Google in one click (Priority: P2)

A new caregiver chooses "Continue with Google" on the embedded Clerk sign-up form at `/sign-up`, completes Google's consent flow, and lands in MomDiary signed in — without ever choosing or remembering a MomDiary-specific password.

**Why this priority**: Reduces friction for the largest single segment of users (Google account holders) and lifts conversion. Lower priority than P1 only because P1 covers the universal path; P3 layers on top once Clerk is wired in.

**Independent Test**: From a clean browser session, navigate to MomDiary, click "Sign up", choose "Continue with Google", complete the Google consent screen, and confirm a new MomDiary caregiver record is created and linked to the Google-backed Clerk identity. No email-verification step is shown (Google already vouches for the email).

**Acceptance Scenarios**:

1. **Given** a visitor on the embedded Clerk sign-up form, **When** they click "Continue with Google" and complete Google's consent, **Then** a new MomDiary caregiver is provisioned and they are signed in.
2. **Given** a visitor who already has a MomDiary account created via email + password, **When** they later sign in with "Continue with Google" using the same email address, **Then** Clerk links the two identities and the user lands in the same MomDiary caregiver record (no duplicate account).

---

### User Story 4 - Caregiver signs out (Priority: P3)

A signed-in caregiver clicks "Sign out", their session is invalidated everywhere (browser cookie cleared, Clerk session ended), and they are returned to the public landing page.

**Why this priority**: Required for shared-device safety and basic hygiene, but not blocking for an MVP demo with a single trusted user.

**Independent Test**: While signed in, click "Sign out" and confirm: (a) any subsequent request to a protected page redirects to sign-in, (b) the browser no longer holds a valid session, (c) re-opening the app does not auto-restore the previous session.

**Acceptance Scenarios**:

1. **Given** a signed-in caregiver, **When** they click "Sign out", **Then** their browser session is cleared and they are returned to the public landing page.
2. **Given** a caregiver who just signed out, **When** they try to access a baby-scoped page directly via URL, **Then** they are redirected to `/sign-in`.

---

### Edge Cases

- **Email-verification abandoned**: User signs up with email/password, never clicks the verification email. The MomDiary caregiver record exists but MUST be in an unverified state that blocks every baby-creation and diary-write request (see FR-017). Reads MUST be safe because no babies or entries can exist yet. The caregiver row persists; if the user later returns and verifies, they continue with the same caregiver record. There MUST be no "silently allow writes" loophole.
- **Google consent denied**: User clicks "Continue with Google" but cancels on Google's screen. They MUST return to the embedded Clerk form at `/sign-up` or `/sign-in` with a clear error, with no MomDiary record created.
- **Same email, different providers**: User signs up with email/password, later signs in with Google for the same email. The system MUST treat them as the same caregiver and not create a duplicate MomDiary record.
- **Clerk session expires mid-use**: User is signed in, leaves the browser open past the session lifetime, then submits a diary entry. The request MUST fail cleanly (clear "please sign in again" message) without corrupting any in-flight data.
- **Clerk service unavailable**: If Clerk's API is unreachable during sign-in/sign-up, the user MUST see a clear retry-able error. The app MUST NOT silently allow unauthenticated access.
- **Account deletion in Clerk**: When Clerk reports that a caregiver's identity has been deleted, MomDiary MUST cascade hard-delete the caregiver record, every baby owned by that caregiver, and every diary entry (feeds, sleeps, poops, appointments, appointment notes) belonging to those babies. Any in-flight session presenting that identity MUST be rejected. The deletion MUST be irrecoverable — no soft-delete column, no archive table.
- **Multiple devices**: A caregiver signed in on phone and laptop simultaneously MUST see both sessions remain valid; signing out on one device MUST NOT necessarily sign out the other (standard Clerk per-session behavior).

## Requirements *(mandatory)*

### Functional Requirements

**Authentication surface**

- **FR-001**: System MUST delegate all caregiver sign-up, sign-in, password management, and email-verification UI to Clerk's prebuilt components, embedded inside MomDiary routes (`/sign-in`, `/sign-up`, and any sub-routes Clerk requires such as verification). MomDiary MUST NOT render its own email/password forms, and the user MUST NOT be redirected off the MomDiary domain during the auth flow.
- **FR-002**: System MUST offer two sign-up / sign-in methods on the embedded Clerk components: email + password, and "Continue with Google".
- **FR-003**: Unauthenticated visitors attempting to access any protected MomDiary page MUST be redirected to the in-app `/sign-in` route (which renders Clerk's prebuilt sign-in component); after successful sign-in, they MUST land on the page they originally requested (or a sensible default if none).
- **FR-004**: System MUST provide a visible "Sign out" control on every signed-in page that ends the Clerk session and clears the local browser session.

**Identity linkage**

- **FR-005**: On a caregiver's first successful sign-in via Clerk, the system MUST provision a MomDiary caregiver record linked one-to-one to the Clerk identity.
- **FR-006**: System MUST treat the Clerk identity as the source of truth for caregiver identity; the Clerk identifier MUST be the stable foreign key from MomDiary caregiver records to Clerk.
- **FR-007**: If a Clerk identity has more than one verified email (e.g., user added Google to an email-password account), the MomDiary caregiver record MUST remain a single row — no duplication.

**Session and request authorization**

- **FR-008**: Every MomDiary API request that touches caregiver-scoped or baby-scoped data MUST be rejected unless it carries a currently-valid Clerk session credential.
- **FR-009**: System MUST verify the Clerk session credential on every request without relying on caller-supplied identity claims (i.e., it MUST validate against Clerk, not trust an unsigned client header).
- **FR-010**: When a Clerk session is missing, expired, or revoked, the system MUST return an unambiguous "not signed in" response that the client uses to redirect to sign-in.
- **FR-011**: Existing baby-scoping (every diary table carries a non-null baby owner and rejects access from caregivers who do not own that baby) MUST be preserved unchanged; only the *caregiver identity resolution* changes.

**Cutover and data reset**

- **FR-012**: At cutover, the system MUST discard all pre-existing local-auth caregiver records, all baby profiles owned by those caregivers, and all diary entries (feeds, sleeps, poops, appointments, appointment notes) belonging to those babies. No pre-existing data MUST be reachable after cutover under any sign-in path.
- **FR-012a**: After cutover, every caregiver — including anyone who previously had a local-auth account — MUST go through the Clerk sign-up flow and create their baby profile(s) from scratch. There MUST NOT be a "claim my old account" or "restore my data" path.

**Operational and observability**

- **FR-013**: Sign-in, sign-up, sign-out, and authentication failures MUST be logged with a stable correlation identifier so operators can trace an individual user's session lifecycle without logging passwords, tokens, or other credentials.
- **FR-014**: System MUST NOT log or persist Clerk session tokens, password material, or Google access tokens in plaintext anywhere in MomDiary application logs or storage.

**Account lifecycle**

- **FR-015**: When MomDiary becomes aware that a Clerk identity has been deleted, the system MUST hard-delete the linked MomDiary caregiver record, every baby owned by that caregiver, and every diary entry belonging to those babies, with no soft-delete or archival copy retained. The cascade MUST complete promptly (within minutes of MomDiary learning of the deletion) and MUST be idempotent so that repeated deletion signals are safe.
- **FR-016**: After the cascade in FR-015 completes, any subsequent request presenting a session tied to the deleted identity MUST be rejected, and no diary data belonging to that former caregiver MUST be reachable by any caregiver, anonymous request, or administrative read path.

**Email verification gating**

- **FR-017**: A caregiver whose Clerk identity reports the primary email as unverified MUST be blocked from every write action: creating a baby profile, logging or updating feeds/sleeps/poops/appointments, and adding appointment notes. The block MUST be enforced server-side on every protected write endpoint, not only in the UI. Read endpoints MAY remain accessible (they will return an empty workspace because no babies or entries can yet exist).
- **FR-018**: Caregivers who sign up via Google (or any future social provider that supplies a verified email at sign-up) MUST NOT see the FR-017 gate — they MUST be able to create a baby and log entries immediately after first sign-in.
- **FR-019**: When a caregiver gated by FR-017 returns to the app, the UI MUST surface a clear "verify your email to continue" prompt with a way to resend the verification email; once Clerk reports the email as verified, the gate MUST lift on the very next request with no further action required.

### Key Entities

- **Caregiver (MomDiary)**: Represents a single human caregiver inside MomDiary. Holds a stable internal caregiver identifier (used by every diary table as the owner key, indirectly via baby ownership), the Clerk identity reference, the primary email known at the time of provisioning, and timestamps. Owns one or more babies; deletion behavior on identity loss is governed by FR-007 and the "account deletion in Clerk" edge case.
- **Clerk Identity (external)**: The Clerk-managed user record. Owns email addresses, password (if set), linked social providers (Google), email-verification state, and active sessions. MomDiary references it by its stable Clerk identifier but does not store its credential material.
- **Baby (existing)**: Unchanged by this feature in shape or ownership semantics. Continues to belong to a single Caregiver. All diary entries continue to be scoped by baby owner, which is in turn scoped by caregiver.
- **Session (Clerk)**: The Clerk-managed authentication session, presented to MomDiary on each request. MomDiary does not mint or store sessions itself once this feature ships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A brand-new visitor can go from landing page to a signed-in MomDiary state with one verified baby created in under 3 minutes using email + password.
- **SC-002**: A brand-new visitor can go from landing page to a signed-in MomDiary state via "Continue with Google" in under 60 seconds (no email-verification step required because Google has already verified the address).
- **SC-003**: 100% of MomDiary API requests that touch caregiver-scoped or baby-scoped data are rejected when no valid Clerk session is presented, verified by an automated test sweep across every such endpoint.
- **SC-004**: After cutover, the database contains zero pre-existing local-auth caregivers, babies, or diary entries — verified by an automated post-migration check that counts rows in `users`, `babies`, and every diary table at zero (or at counts created only by post-cutover Clerk sign-ups).
- **SC-005**: Zero password material, Clerk session tokens, or Google access tokens appear in any MomDiary application log line, verified by an automated log-scan in CI.
- **SC-006**: 95% of returning users complete sign-in (from clicking "Sign in" to landing on a baby page) in under 10 seconds.

## Assumptions

- **Clerk is the chosen identity provider.** No comparative evaluation of alternatives is in scope; the feature description names Clerk explicitly.
- **Google is the only social provider in scope** for the first release. Other social providers (Apple, Microsoft, Facebook, etc.) can be added later without re-architecting because they are a Clerk configuration toggle.
- **Clerk-hosted UI is rendered via embedded prebuilt components, not redirect.** MomDiary mounts Clerk's prebuilt sign-in/sign-up components at its own routes (`/sign-in`, `/sign-up`) so users never leave the MomDiary domain during authentication. Clerk's Account Portal / hosted pages are explicitly not used.
- **Existing local password authentication is retired at cutover.** The previously-shipped email + Argon2id-hashed password + HttpOnly session cookie path (feature 006) is replaced by Clerk; it is not maintained in parallel. All pre-existing local-auth caregivers, baby profiles, and diary entries are discarded at cutover (see FR-012 / FR-012a) — there is no migration path.
- **Existing baby data and `baby_id` scoping on every diary table are preserved unchanged.** Only the caregiver-identity layer is replaced.
- **Caregiver-to-baby ownership remains single-owner.** Multi-caregiver-per-baby (e.g., two parents sharing) is out of scope for this feature, consistent with the existing single-owner baby model.
- **Principle IV (Entra ID for Azure access) is not violated.** Clerk handles end-user authentication; Azure resource access from the backend continues to use DefaultAzureCredential and Entra ID. The two identity systems do not overlap.
- **No new agent or tool is introduced.** This feature changes authentication only; the diary agent, its tools, and the chat session store are unaffected in shape.
- **The product is still pre-broad-launch.** Existing caregivers, if any, are a small known set whose emails can be reconciled with Clerk identities on first sign-in by email match.
- **Chat session keying remains `(caregiver_id, baby_id, session_id)`.** The caregiver identifier resolved from Clerk replaces the previously-locally-issued caregiver identifier; the partitioning shape is unchanged.

## Dependencies

- A configured Clerk application (test + prod environments) with email/password and Google OAuth enabled.
- A Google OAuth client registered with Clerk for the social-sign-in path.
- An updated MomDiary frontend that renders Clerk's prebuilt sign-in/sign-up components at in-app routes (`/sign-in`, `/sign-up`), routes unauthenticated users to those routes, and reads the resulting session.
- An updated MomDiary backend that validates Clerk sessions on every protected endpoint.
