# Feature Specification: MomDiary Tracker UX with Chat-Driven Entry

**Feature Branch**: `002-tracker-ux-chat`
**Created**: 2026-05-17
**Status**: Draft
**Input**: User description: "Build a UX to show different types of records and hook them up with GET APIs. Add a chat interface and hook it up for adding record entries."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse today's baby-care records by type (Priority: P1)

As a caregiver, when I open the MomDiary app I see today's records grouped by type (feeds, sleeps, poops, appointments), each ordered chronologically, so I can review what happened during the current day at a glance.

**Why this priority**: This is the primary "did I track everything?" reassurance loop. Without it the caregiver cannot trust that earlier entries actually landed in the system, which makes every other feature pointless. It is also the simplest slice that can ship and immediately deliver value the moment the backend GET endpoints are wired.

**Independent Test**: With the backend's seeded entries for today, open the app: the four sections must render with all of today's items, the correct counts, and the right ordering. No write actions required.

**Acceptance Scenarios**:

1. **Given** the caregiver has logged 2 feeds, 1 sleep, and 1 poop earlier today, **When** they open the app, **Then** the Feeds section shows 2 items, the Sleeps section shows 1 item, the Poops section shows 1 item, the Appointments section shows the empty-state message, and each item displays its time-of-day in the caregiver's local timezone plus the type-specific summary (e.g., "120 ml breast milk").
2. **Given** the caregiver is viewing today, **When** they pick a different calendar date in the date selector, **Then** all four sections refresh to show that date's records and the selected date is visible in the header.
3. **Given** the backend returns an empty list for a record type on the selected date, **When** the section renders, **Then** the caregiver sees a type-specific empty state (e.g., "No feeds logged for this date") rather than a blank panel.
4. **Given** the caregiver pulls to refresh (or clicks a refresh control), **When** the refresh completes, **Then** the data on screen reflects what the backend currently returns and any newly added entries appear within 2 seconds.

---

### User Story 2 - Add a new record by chatting in plain language (Priority: P1)

As a caregiver with a baby in one arm, I want to type or speak a short sentence like "100 ml formula at 9:15am" into a chat panel and have the entry recorded in the right place, so I can capture events without filling out a form.

**Why this priority**: The chat-driven write path is the differentiating value proposition of MomDiary — every other tracker has forms. Pairing it with US1 is the minimum delightful experience: see today's records and add the next one by chatting.

**Independent Test**: Type a free-form message describing a new feed/sleep/poop/appointment. The chat shows the assistant's confirmation, and the corresponding section in US1 updates to show the new entry on refresh (or automatically).

**Acceptance Scenarios**:

1. **Given** the chat panel is open and no records exist for today, **When** the caregiver sends "120 ml breast milk just now", **Then** the assistant replies with a one-sentence confirmation ("Logged 120 ml of breast milk."), and the Feeds section shows the new entry with the current local time.
2. **Given** the assistant needs more information, **When** the caregiver sends an ambiguous message like "I fed the baby", **Then** the assistant replies with a clarifying question (e.g., "How much, and what type — breast milk, formula, solids, or water?") and no record is created until the caregiver provides the missing details in the next message.
3. **Given** the caregiver sent a message that resulted in a successful record creation, **When** they look at the chat history, **Then** they can see their original message and the assistant's confirmation, scrollable in chronological order for the current session.
4. **Given** the backend returns an error (network, auth, validation), **When** the assistant cannot fulfill the request, **Then** the caregiver sees a clear, non-technical error message in the chat (e.g., "I couldn't save that — please try again.") and the input box remains usable.
5. **Given** the caregiver dictates "the baby napped from 1pm to 2:30pm", **When** the assistant processes it, **Then** a sleep record is created with start and end times, and the Sleeps section shows it with a duration of 1h 30m.

---

### User Story 3 - Visual distinction and quick scanning across record types (Priority: P2)

As a caregiver scanning the day's log, I want each record type to have its own visual identity (icon, color, layout) so my eye can immediately find the section I care about without reading every label.

**Why this priority**: Improves usability and reduces cognitive load, but the core value of US1 + US2 still works in a plain layout. Ship as a polish pass.

**Independent Test**: Render a day with at least one of every record type. A first-time viewer can correctly point to each section within 3 seconds, identifying it by visual cue alone.

**Acceptance Scenarios**:

1. **Given** all four sections are visible, **When** the caregiver looks at the screen, **Then** each section has a distinct icon and accent color that is consistent every time the app is opened.
2. **Given** a record item is displayed, **When** the caregiver glances at it, **Then** the most important field (quantity for feeds, duration for sleeps, consistency for poops, scheduled time for appointments) is the most visually prominent piece of text in that item.

---

### Edge Cases

- The caregiver opens the app before logging anything: all four sections show empty states, the chat panel shows a friendly welcome prompt.
- The caregiver selects a future date: all four sections show empty states; the chat is still available but the assistant uses the selected date as context.
- The caregiver selects a date in the past with many entries: the lists remain scrollable within each section without breaking the overall page layout.
- The backend is unreachable on initial load: the UI shows a single, clear retry affordance rather than four separate error panels.
- The chat assistant requests clarification multiple turns in a row: each turn is shown in chronological order; the caregiver can abandon the conversation without leaving behind a partial record.
- The caregiver sends two write requests back-to-back without waiting for the first to finish: each is processed in order and the chat history reflects each request and response.
- An appointment has many notes: the appointment item shows the most recent note inline with an indicator that more notes exist (full list out of scope for v1 — see Assumptions).
- The caregiver's session has not been authenticated with Azure: the chat panel shows a clear sign-in / setup prompt instead of silently failing.

## Requirements *(mandatory)*

### Functional Requirements

#### Records browsing (US1)

- **FR-001**: The UX MUST display the caregiver's records for a selected calendar date, grouped into four distinct sections: feeds, sleeps, poops, and appointments.
- **FR-002**: The UX MUST default the selected date to "today" in the caregiver's local timezone on first load.
- **FR-003**: The UX MUST provide a date selector that lets the caregiver navigate to any past or future date and updates all four sections to reflect that date.
- **FR-004**: For each record type, the UX MUST issue exactly one GET request per date change and render the response items sorted by their occurrence time (or scheduled time for appointments) in ascending order.
- **FR-005**: Each record item MUST show, at minimum: time-of-day in the caregiver's local timezone, and the type-specific primary attribute (quantity + unit + feed type for feeds; duration and start/end for sleeps; consistency for poops; scheduled time and most-recent note preview for appointments).
- **FR-006**: When a section's GET response is empty, the UX MUST show a type-specific empty-state message.
- **FR-007**: When a section's GET request fails, the UX MUST show a localized error inside that section without preventing the other sections from rendering successfully.
- **FR-008**: The UX MUST provide a manual refresh control that re-fetches all four sections for the currently selected date.
- **FR-009**: After a successful chat-driven write (US2), the UX MUST refresh the affected section(s) within 2 seconds so the new record is visible without requiring manual interaction.

#### Chat-driven entry (US2)

- **FR-010**: The UX MUST present a persistent chat panel where the caregiver can type a free-form message and submit it.
- **FR-011**: The UX MUST send each submitted chat message to the backend's conversational entry endpoint and display the backend's response text in the chat history.
- **FR-012**: The UX MUST attach a fresh correlation identifier to each chat submission and surface it in error states so the caregiver can reference it in support requests.
- **FR-013**: The UX MUST display a clear "thinking" indicator while waiting for the backend's response and MUST disable the submit control until the previous request resolves.
- **FR-014**: When the backend indicates a record was created or updated, the UX MUST show a one-sentence confirmation in the chat and trigger a refresh of the matching section (see FR-009).
- **FR-015**: When the backend asks a clarifying question, the UX MUST display the question in the chat and keep the input box focused so the caregiver can answer immediately.
- **FR-016**: When the backend returns an error, the UX MUST display a non-technical, user-friendly message in the chat ("I couldn't save that — please try again.") and preserve the caregiver's original input so they can retry without retyping.
- **FR-017**: The chat history MUST persist for the duration of the app session (so the caregiver can scroll back and review what was logged) and MUST be cleared when the session ends or the caregiver explicitly clears it.

#### Cross-cutting

- **FR-018**: All times shown in the UX MUST be rendered in the caregiver's local timezone using a human-friendly format (e.g., "9:15 AM"), not the raw ISO string returned by the backend.
- **FR-019**: The UX MUST handle authentication to the backend using the project's existing Azure Entra ID flow; on auth failure it MUST present a single sign-in affordance rather than a generic error.
- **FR-020**: The UX MUST be usable on a typical mobile-sized viewport (portrait orientation) without horizontal scrolling, since the primary device is a phone held one-handed.
- **FR-021**: The UX MUST distinguish between record types using both color and a non-color cue (icon or label) so the layout remains accessible to users with color-vision differences.

### Key Entities *(include if feature involves data)*

- **Record Type Section**: A logical grouping on screen for one record type (feeds, sleeps, poops, appointments). Each section has a header with the type name and item count, a list of record items for the selected date, an empty state, and a per-section error state.
- **Record Item**: A single entry rendered in a section. Visible attributes vary by type but always include time-of-day and the type's primary attribute. Backed by an entry in the backend store (existing).
- **Chat Message**: A turn in the conversation. Has a role (caregiver or assistant), a text body, a timestamp, and an optional correlation identifier for assistant-side messages.
- **Chat Session**: An ordered list of chat messages plus the current input draft. Lives only for the lifetime of the app session.
- **Selected Date**: The calendar date currently driving the four section queries. Defaults to today in the caregiver's local timezone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caregiver can find any one of today's logged records (feed, sleep, poop, or appointment) within 5 seconds of opening the app, on a phone-sized viewport, without scrolling past more than one screen height.
- **SC-002**: A caregiver can record a new entry via the chat panel and see it appear in its correct section in under 10 seconds end-to-end (typing + send + assistant reply + section refresh) for at least 90% of common short-message inputs.
- **SC-003**: When the caregiver navigates between dates, all four sections finish updating within 2 seconds for a typical day's volume of records.
- **SC-004**: First-time users correctly identify the four record-type sections by visual cue alone in usability testing at a rate of at least 90%.
- **SC-005**: Chat-driven entries succeed (record created on first or clarification-completing message) on at least 85% of attempts during a 1-week shadow trial, measured by successful tool invocations from the backend audit log.
- **SC-006**: When the backend is unreachable, 100% of users in usability testing recognize the error state and discover the retry affordance without prompting.

## Assumptions

- The MomDiary backend from feature `001-baby-tracker-backend` is the only data source. The UX consumes its existing `GET /v1/feeds`, `GET /v1/sleeps`, `GET /v1/poops`, `GET /v1/appointments` (filtered by date) and `POST /v1/entries` (conversational write) endpoints. No new backend endpoints are introduced.
- Authentication is handled by the existing Azure Entra ID flow used by the backend; the UX surfaces sign-in but does not implement a new identity system.
- The chat history is **session-scoped** (in-memory). Persisting chat history across sessions is out of scope for v1.
- Editing or deleting existing records from the UX (vs. the chat) is **out of scope** for v1; only browsing (US1) and chat-driven creation (US2) are in scope. Edit/delete remain available through the backend's existing PUT endpoint, but no dedicated UI is provided in this feature.
- Appointment notes display is limited to a single most-recent-note preview per appointment item; a full notes drawer is out of scope for v1.
- The primary form factor is a phone-sized portrait viewport, single-user (the caregiver). Multi-user / multi-baby scenarios are out of scope.
- Internet connectivity is assumed; offline drafting / queueing of chat messages is out of scope for v1.
- Voice input is **not** a v1 requirement; users may dictate via their device's OS-level speech-to-text into the chat input, but the UX does not implement a dedicated microphone control.
- The selected date persists only for the current app session; on a fresh launch the app resets to today.
