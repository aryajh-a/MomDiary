# Feature Specification: Baby Tracker Agentic Backend

**Feature Branch**: `001-baby-tracker-backend`
**Created**: 2026-05-16
**Status**: Draft
**Input**: User description: "Build an agentic system backend (MomDiary) using FastAPI, which allows users to add feed information (type, quantity, time), sleep information (start-time, endtime), poop information (time, consistency), doctor appointments (date and time) with ability to take notes for each appointment. It should expose single POST/PUT API to add these information through Agent and it's tools. It should add another set of GET APIs to get these details on date basis."

## Clarifications

### Session 2026-05-16

- Q: Caregiver/auth model for v1 → A: Single-user, no auth; persist nullable `caregiver_id` for future multi-user.
- Q: PUT contract for unified write endpoint → A: Hybrid — `entry_id` optional; agent resolves from message when absent.
- Q: Deletion of entries → A: Soft-delete via the agent; entry marked inactive and hidden from GETs.
- Q: Time-zone source of truth → A: Server-side single `default_timezone` setting; clients do not pass TZ.
- Q: Data retention → A: Indefinite; no automatic deletion of active or soft-deleted entries in v1.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Log a daily care event by chatting with the agent (Priority: P1)

A parent opens the MomDiary client and types or speaks a natural-language
message such as "Baby just had 120 ml of formula at 2:15 pm" or "Nap from 1
to 2:30". The backend's single conversational endpoint forwards the message
to the agent, which selects the right tool (feed / sleep / poop /
appointment), extracts structured fields, and persists the entry. The
parent gets back a confirmation describing exactly what was recorded.

**Why this priority**: This is the core value of the product. Without
reliable agent-driven capture across all four event types, the rest of the
system has nothing to read back. It is the smallest slice that
demonstrates the agentic experience end-to-end.

**Independent Test**: Send a series of natural-language messages — one per
event type — to the single POST endpoint and confirm each results in a
correctly-typed, correctly-fielded record retrievable via the date-based
GET endpoints.

**Acceptance Scenarios**:

1. **Given** an empty day, **When** the parent sends "Fed 90 ml of breast
   milk at 8:05 am", **Then** a feed entry is stored with type = breast
   milk, quantity = 90 ml, time = today 08:05, and the response confirms
   the saved values.
2. **Given** an empty day, **When** the parent sends "Slept from 1pm to
   2:45pm", **Then** a sleep entry is stored with the matching start and
   end times and a duration derivable from them.
3. **Given** an empty day, **When** the parent sends "Poop at 9am, runny",
   **Then** a poop entry is stored with time = today 09:00 and consistency
   classified into a known category.
4. **Given** an empty day, **When** the parent sends "Pediatrician
   appointment on May 20 at 4pm, ask about vaccine schedule", **Then** a
   doctor-appointment entry is stored with the date/time and a note
   containing "ask about vaccine schedule".

---

### User Story 2 - Review everything that happened on a given day (Priority: P1)

A parent wants to see the day at a glance — all feeds, all sleeps, all
poops, and any appointments for a specific date — through simple
date-scoped REST endpoints (no agent in the loop).

**Why this priority**: Recording without recall is useless. The GET-by-date
APIs are what enable downstream UIs, daily summaries, and handoffs to
caregivers, and they make user story 1 verifiable.

**Independent Test**: After seeding entries (directly or via story 1),
call each GET-by-date endpoint and confirm the response contains exactly
the entries whose timestamp falls within that date, ordered chronologically.

**Acceptance Scenarios**:

1. **Given** three feed entries logged today and two logged yesterday,
   **When** the client requests today's feeds, **Then** only the three
   today entries are returned, ordered earliest-first.
2. **Given** a sleep session that starts at 23:30 and ends at 01:15 the
   next day, **When** the client requests sleeps for the start date,
   **Then** the session is included (assigned to its start date) with the
   full start and end timestamps intact.
3. **Given** no entries of a given type on the requested date, **When**
   the client requests that type for the date, **Then** the response is a
   successful empty collection rather than an error.
4. **Given** a doctor appointment scheduled for a future date with
   attached notes, **When** the client requests appointments for that
   date, **Then** the entry and all its notes are returned.

---

### User Story 3 - Correct or extend an existing entry via the agent (Priority: P2)

A parent realizes an earlier entry was wrong ("That feed was actually 120
ml, not 100") or wants to add a note to an existing doctor appointment.
They send a corrective message to the same single endpoint; the agent
identifies the target entry and updates it via the PUT path of the unified
write API.

**Why this priority**: Real caregiving notes are messy and get corrected.
Supporting edits keeps the dataset trustworthy, but the product is still
useful without it for v1.

**Independent Test**: Create an entry (story 1), then send a corrective
natural-language message referencing it, and confirm the GET-by-date
response reflects the updated values while no duplicate entry is created.

**Acceptance Scenarios**:

1. **Given** a feed entry of 100 ml at 08:05 today, **When** the parent
   sends "Actually the 8 am feed was 120 ml", **Then** the existing entry
   is updated to 120 ml and no new entry is created.
2. **Given** a doctor appointment with one note, **When** the parent sends
   "Add a note to tomorrow's appointment: bring vaccination card", **Then**
   the appointment retains its original note and gains the new one.
3. **Given** the agent cannot confidently identify which entry to update,
   **When** the corrective message is received, **Then** the response asks
   the user to disambiguate and no record is modified.

---

### Edge Cases

- Ambiguous or missing time ("baby ate a bit ago"): the agent MUST ask for
  a specific time or reject the entry rather than guess silently.
- Sleep entries where end time is earlier than start time (overnight
  sleep): treated as spanning midnight; the entry is filed under the
  start date.
- Poop consistency that does not match any known category: the agent MUST
  map to the closest known category or ask for clarification; freeform
  strings outside the vocabulary are rejected.
- Duplicate submissions of the same event within a short window (e.g.,
  identical feed within 60 seconds): the system flags a likely duplicate
  and asks the user to confirm before creating a second entry.
- Date-based GETs for far-past or far-future dates with no data return an
  empty list, not an error.
- Time-zone handling: all timestamps are interpreted in the user's
  configured time zone; persisted values include the offset so the
  original local time can always be reconstructed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a single conversational write
  endpoint (POST for new entries, PUT for updates to an existing entry by
  identifier) that accepts a natural-language message and routes it
  through the agent to the appropriate domain tool.
- **FR-002**: The agent MUST expose four tools to itself: log/update feed,
  log/update sleep, log/update poop, and log/update doctor appointment
  (with notes). The agent MUST choose exactly one tool per user turn,
  unless the user clearly describes multiple events in one message, in
  which case each event is recorded by a separate tool call.
- **FR-003**: A feed entry MUST capture: feed type (from a known set such
  as breast milk, formula, solids, water; new types are rejected unless
  explicitly added), quantity with a unit (ml or g; oz accepted but
  normalized to ml), and a timestamp.
- **FR-004**: A sleep entry MUST capture a start timestamp and an end
  timestamp; the system MUST derive duration on read and reject entries
  whose end equals start.
- **FR-005**: A poop entry MUST capture a timestamp and a consistency
  value drawn from a predefined vocabulary (e.g., watery, soft, formed,
  hard); free-text consistency is not stored.
- **FR-006**: A doctor appointment entry MUST capture a date-time and MUST
  support zero or more text notes per appointment; notes are appended,
  not overwritten, when the parent adds more later.
- **FR-007**: The system MUST persist all entries durably such that
  records logged in one session are readable in any subsequent session.
- **FR-008**: The system MUST expose date-scoped read endpoints — at
  minimum one per event type (feeds, sleeps, poops, appointments) — that
  accept a date and return all entries belonging to that date, ordered
  by timestamp ascending. Soft-deleted entries (see FR-018) MUST be
  excluded from these responses.
- **FR-009**: For sleep entries that span midnight, the entry MUST be
  returned by the GET-by-date call for its start date and MUST include
  the full start and end timestamps so a client can render it on either
  day.
- **FR-010**: Every write MUST return a confirmation payload containing
  the canonical stored values (after normalization) and the entry's
  identifier, so a client or follow-up agent turn can reference it.
- **FR-011**: The agent MUST refuse to fabricate missing required fields;
  if a required field cannot be determined from the user message and
  reasonable defaults (e.g., "now" for an unspecified time on a logging
  intent), it MUST ask for clarification in its response and MUST NOT
  persist the entry.
- **FR-012**: All timestamps in requests and responses MUST be ISO-8601
  with an explicit time-zone offset. The system MUST hold a single
  server-side `default_timezone` configuration value (an IANA zone such
  as `America/Los_Angeles`); clients MUST NOT pass a time zone on
  requests. The agent MUST convert relative or informal times (e.g.,
  "2 pm", "an hour ago") into ISO-8601 using `default_timezone`, and
  GET-by-date endpoints MUST interpret the requested date in
  `default_timezone`.
- **FR-013**: The system MUST emit a structured log record per agent
  invocation including a correlation id, the chosen tool, the resulting
  entry id (if any), and outcome (created, updated, clarification
  requested, rejected).
- **FR-014**: Input validation MUST reject negative quantities, zero-length
  sleep windows, and timestamps more than a reasonable bound into the
  future for past-event types (feeds/sleeps/poops) while allowing future
  timestamps for appointments.
- **FR-015**: The write endpoint MUST be idempotent for updates: re-sending
  the same PUT for the same entry id with the same payload MUST not
  create duplicates or change the stored values.
- **FR-016**: The system MUST operate as a single-user product in v1 with
  no authentication: there is one implicit caregiver context, and every
  entry implicitly belongs to it. Every stored entity MUST nevertheless
  carry a nullable `caregiver_id` field so that a future multi-user
  release can populate it without a schema migration. Reads and writes
  in v1 MUST ignore `caregiver_id` (treating null as "the v1 owner").
- **FR-017**: For the unified write endpoint, the request payload MUST
  accept an OPTIONAL `entry_id` (with its `entry_type`). When `entry_id`
  is supplied, the server MUST treat the call as a deterministic update
  of that record and MUST NOT let the agent retarget a different entry.
  When `entry_id` is absent and the user message describes an update
  (e.g., "the 8 am feed was actually 120 ml"), the agent MUST resolve
  the target entry from the message; if it cannot resolve unambiguously,
  it MUST ask the user to disambiguate and MUST NOT modify any record
  (consistent with FR-011 and User Story 3, scenario 3).
- **FR-018**: The system MUST support deletion of any entry via the same
  unified agentic write endpoint by recognising a "delete" intent (e.g.,
  "remove the 8 am feed"). Deletion MUST be performed as a soft delete:
  the row is marked inactive (e.g., `deleted_at` timestamp set) and
  retained for audit, but is excluded from all GET responses (FR-008)
  and from agent-driven update target resolution (FR-017). Target
  resolution for delete follows the same rules as FR-017: explicit
  `entry_id` when provided, agent inference otherwise, clarification
  required when ambiguous, and no record is altered until the target is
  unambiguous.
- **FR-019**: The system MUST retain all entries indefinitely in v1.
  Neither active entries nor soft-deleted entries (FR-018) MUST be
  automatically purged by the system, and no time-based retention
  policy is in force; cleanup, if ever needed, is a future-version
  concern.

### Key Entities *(include if feature involves data)*

- **FeedEntry**: A single feeding event. Attributes: id, nullable
  `caregiver_id` (v1: always null), type (enumerated), quantity, unit,
  timestamp, nullable `deleted_at` (soft-delete marker),
  created/updated audit fields.
- **SleepEntry**: A single sleep session. Attributes: id, nullable
  `caregiver_id` (v1: always null), start timestamp, end timestamp,
  derived duration, nullable `deleted_at`, created/updated audit fields.
- **PoopEntry**: A single diaper event. Attributes: id, nullable
  `caregiver_id` (v1: always null), timestamp, consistency (enumerated),
  nullable `deleted_at`, created/updated audit fields.
- **DoctorAppointment**: A scheduled or past appointment. Attributes: id,
  nullable `caregiver_id` (v1: always null), date-time, zero-or-more
  associated AppointmentNotes, nullable `deleted_at`, created/updated
  audit fields.
- **AppointmentNote**: A text note attached to a DoctorAppointment.
  Attributes: id, parent appointment id, text body, timestamp added.
- **AgentInteraction** (operational, not user-visible): Correlation id,
  inbound user message, selected tool, resulting entry id, outcome, and
  timestamp — used for observability and debugging of agent decisions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the four event types, at least 95% of clearly
  worded natural-language messages in a curated test set result in the
  correct entry being created on the first attempt (no clarification
  loop, no wrong tool chosen).
- **SC-002**: A parent can log a single event from a typed message to a
  confirmed stored record in under 5 seconds end-to-end at p95, excluding
  upstream model inference time, which is reported separately.
- **SC-003**: A date-scoped GET request for any event type returns in
  under 500 ms at p95 for a day containing up to 50 entries.
- **SC-004**: Ambiguous inputs (missing required field, unknown
  consistency, etc.) result in a clarification response rather than an
  incorrect entry in 100% of curated ambiguous-input tests; zero silent
  fabrications are tolerated.
- **SC-005**: After a full day of mixed entries (≥ 20 events across all
  four types), the date-scoped GETs together return every entry exactly
  once, with no duplicates, no drops, and chronological ordering within
  each type.
- **SC-006**: Re-issuing the same PUT update twice produces identical
  stored state and identical response payloads (idempotency verified by
  automated test).

## Assumptions

- The product targets a single household / single baby in v1, with no
  authentication; the nullable `caregiver_id` column is a forward-
  compatibility hook only and is not exercised by v1 endpoints.
  Multi-baby support remains out of scope for v1.
- A web/mobile client exists separately and is responsible for
  authentication-to-backend (if any) and for rendering. This spec covers
  only the backend HTTP and agent surface.
- The user's time zone is held as a single server-side `default_timezone`
  setting (an IANA zone) configured during setup; clients do not pass a
  time zone on requests. The parent may update this setting if they
  travel. Cross-time-zone travel handling beyond updating the setting
  is out of scope for v1.
- The set of feed types and poop consistencies is a fixed enumeration
  curated by the product team; extending it requires a code/data change
  rather than user input.
- The agent runs on the Microsoft Agent Framework (prerelease channel)
  per the project constitution; specific model choice is deferred to the
  implementation plan.
- Persistence uses a durable store appropriate for structured
  time-series-by-date access; exact storage technology is deferred to
  the implementation plan.
- All four event types share comparable write/read traffic patterns; no
  one type is expected to dominate by an order of magnitude in v1.
