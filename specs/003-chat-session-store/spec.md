# Feature Specification: Backend-Side Chat Session Store

**Feature Branch**: `003-chat-session-store`
**Created**: 2026-05-18
**Status**: Draft
**Input**: User description: "Manage context in conversation by Implementing backend service side session store."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Agent resolves references to prior turns (Priority: P1)

A caregiver opens the app, types "120 ml breast milk just now" and the agent confirms it. A minute later they type "actually, make it 90" — the agent understands "it" refers to the feed they just logged and updates it.

**Why this priority**: This is the core value of moving context to the backend. Today the agent sees only the latest single message, so the caregiver must repeat the full description on every correction. Once the backend keeps the running turns of the conversation and passes them to the agent, the assistant can resolve pronouns, follow-ups, and corrections — turning a transactional command line into an actual conversation.

**Independent Test**: Open the app and send these two messages in order against a clean backend: (1) "120 ml breast milk just now", (2) "make it 90". After (2), the feeds section shows a single feed of 90 ml at the original timestamp (an update, not a duplicate create). Repeating (2) without (1) results in a clarification request because no prior context exists.

**Acceptance Scenarios**:

1. **Given** a fresh session, **When** the caregiver sends "120 ml breast milk just now" then "actually 90", **Then** the second turn results in an `updated` envelope referencing the same entry id as the first.
2. **Given** a fresh session, **When** the caregiver sends only "actually 90" without prior context, **Then** the agent returns a `clarification_requested` outcome because there is no prior entry to reference.
3. **Given** an ongoing session with three feed turns, **When** the caregiver sends "what did I log today?", **Then** the assistant can summarize from the conversation context (this is informational only — no write is required).

---

### User Story 2 — Sessions are isolated across clients and tabs (Priority: P1)

Two tabs (or two devices) open the same MomDiary backend. Caregiver A types into tab 1, caregiver B types into tab 2. Neither sees the other's conversation; the agent does not mix their contexts.

**Why this priority**: Without isolation the session store becomes a single global bag and the agent's context grows unboundedly with cross-traffic, breaking every assumption of US1. Isolation is the minimum correctness bar for any multi-client server. Same priority as US1 because together they form the MVP.

**Independent Test**: From two separate browsers (or one regular + one private window), each starts a fresh session. Tab 1 logs a feed; tab 2 sends "delete that". Tab 2's turn results in a clarification (or rejection) — never deletes tab 1's feed.

**Acceptance Scenarios**:

1. **Given** two distinct sessions, **When** session A appends a turn, **Then** session B's subsequent request does not see session A's history.
2. **Given** a request with no session identifier, **When** the backend processes it, **Then** the backend establishes a new session and surfaces the identifier in the response so the client can echo it on the next request.
3. **Given** a request whose session identifier is unknown or expired, **When** the backend processes it, **Then** the backend treats it as a fresh session (creating a new identifier) rather than failing the request.

---

### User Story 3 — Bounded retention with observable limits (Priority: P2)

The caregiver uses the app heavily over an afternoon. After ~50 turns the oldest turns are dropped from the agent's working context, but the most recent ~25 turns stay accurate. The server does not grow without bound, and a long-idle session does not hold memory forever.

**Why this priority**: Critical for production safety but not required to demo the value of US1+US2. A small in-memory dict works for a demo; bounded retention prevents that demo from becoming a long-running memory leak.

**Independent Test**: Drive a session past the configured turn cap and verify (via a debug endpoint or log) that the stored turn count plateaus at the cap. Then leave a session idle past its TTL and verify the next request to that session id is treated as fresh.

**Acceptance Scenarios**:

1. **Given** a session at the configured max-turn count, **When** the caregiver appends another turn, **Then** the oldest turn is evicted (FIFO) and the cap holds.
2. **Given** a session whose last activity is older than the configured TTL, **When** the next request arrives, **Then** the session is treated as expired and a new session identifier is issued.
3. **Given** the configured max sessions in memory, **When** a new session would exceed the cap, **Then** the least-recently-used session is evicted.

---

### Edge Cases

- **Concurrent requests on the same session**: two browser tabs sharing the same session id both submit a turn at the same instant. The backend must serialize updates so the agent always sees a self-consistent history (no torn writes, no lost turns).
- **Session id forged or replayed**: an attacker guesses a session id. Because there is no auth in v1 the worst case is reading another caregiver's chat. Mitigation: session ids must be unguessable (cryptographic UUIDs) and the threat is documented as a v1 limitation.
- **Backend restart**: with in-memory storage, all sessions are lost on restart. The next client request is treated as a new session — clients must tolerate the id changing.
- **Agent tool calls succeed but conversation persistence fails**: the write to the entries table succeeded but appending the assistant turn to the session store threw. The user-visible response MUST still report the successful create/update; the missing context only degrades the next turn (which falls back to clarification).
- **Very long single message**: a 50 KB caregiver message would balloon the prompt. The session store must enforce a per-message size cap and reject or truncate beyond it.
- **Conversation context exceeds the model's token window**: even with the turn cap, total tokens may exceed the underlying chat model's limit. The store must apply a token-aware trimming policy on read (drop oldest turns until the prompt fits) — independent of the FIFO cap, which is a memory bound.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend MUST maintain a per-session, ordered history of conversational turns (caregiver message + assistant response) that survives across HTTP requests within the same process.
- **FR-002**: The backend MUST accept an optional session identifier from the client on `POST /v1/entries` (the existing chat-write endpoint) and create a new session when none is supplied.
- **FR-003**: The backend MUST return the session identifier in every chat response so the client can echo it on subsequent requests.
- **FR-004**: The agent runner MUST receive the session's recent turns as part of its prompt context on every chat invocation, so the model can resolve references to prior turns.
- **FR-005**: The backend MUST persist exactly one caregiver-turn + one assistant-turn pair per request: append on success (any non-error outcome), and append the error response on error so the client and agent agree on what happened.
- **FR-006**: Sessions MUST be isolated: a request bearing session A's identifier MUST NOT see any turn from session B.
- **FR-007**: An unknown or expired session identifier MUST be treated as a fresh session (server issues a new identifier) and MUST NOT fail the request.
- **FR-008**: Session identifiers MUST be cryptographically unguessable (e.g., UUID v4) to mitigate the v1 lack of auth.
- **FR-009**: Each session MUST cap its retained turn count at a configurable maximum (default 50 turn-pairs ≈ 100 messages); oldest turns evicted FIFO when the cap is exceeded.
- **FR-010**: Each session MUST expire after a configurable idle TTL (default 24 hours); the next request after expiry is treated as a fresh session per FR-007.
- **FR-011**: The total number of resident sessions MUST be capped at a configurable maximum (default 100); when the cap is exceeded the least-recently-used session is evicted.
- **FR-012**: Per-message caregiver input MUST be capped at a configurable maximum size (default 4 KB); oversize input is rejected with a validation error envelope that includes the existing correlation id.
- **FR-013**: Reads of session history for prompt construction MUST apply a token-aware trim so the constructed prompt never exceeds the configured prompt-token budget, even when the turn count is under the FIFO cap.
- **FR-014**: Concurrent requests on the same session MUST be serialized so that the appended history is always internally consistent (no interleaved partial writes).
- **FR-015**: Existing entry-write behavior (the `created` / `updated` / `deleted` / `clarification_requested` / `rejected` outcomes) MUST be preserved byte-for-byte; the session store is an additive concern.
- **FR-016**: A failure to persist a turn into the session store MUST NOT fail the chat response; it MUST be logged with the correlation id at WARN-level so the next turn's degraded context is observable.
- **FR-017**: All session-store operations MUST emit structured logs (`session.created`, `session.appended`, `session.evicted`, `session.expired`) tagged with the session id (truncated) and correlation id so operators can trace conversational behavior end-to-end.
- **FR-018**: Read-only list endpoints (`GET /v1/feeds`, `/v1/sleeps`, `/v1/poops`, `/v1/appointments`) MUST be untouched — sessions apply only to the agent-chat write path.

### Key Entities *(include if feature involves data)*

- **ChatSession**: An identified, ordered sequence of turns belonging to a single client thread. Attributes: session id, created-at timestamp, last-activity timestamp, ordered list of turns, eviction metadata (LRU pointer). No reference to a user (there are no users in v1).
- **ChatTurn**: One round-trip in a session. Attributes: role (`caregiver` | `assistant`), text (the caregiver message or the assistant's `agent_message`), outcome (one of the existing five outcomes; absent for caregiver turns), affected entry id (when outcome is created/updated/deleted; absent otherwise), correlation id (matches the HTTP response's correlation id for traceability), timestamp.
- **SessionStore**: The aggregate that manages all `ChatSession`s in the process. Responsibilities: lookup by id, create, append turn, evict per FIFO/LRU/TTL policy, and produce a token-bounded view of recent turns for the agent runner.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caregiver can complete a "log, then correct" exchange (two messages: a create followed by a correction without restating the entry type or attribute) and the second message results in an `updated` outcome — not a `created` outcome and not a clarification — at least 90% of the time across the existing scripted scenarios.
- **SC-002**: 100% of chat responses include a session identifier, and 100% of client requests that echo that identifier are routed to the same session for at least one TTL window.
- **SC-003**: Two concurrent sessions exchanging ten turns each show zero cross-talk: every assistant response references only its own session's prior turns, verified by an automated isolation test.
- **SC-004**: A session driven past the configured turn cap holds steady at the cap (memory growth ≤ 1% beyond the cap) for at least 1000 subsequent turns.
- **SC-005**: An idle session is reclaimed within 5% of the configured TTL window; the next request to that id is treated as a fresh session.
- **SC-006**: A burst of 100 sequential requests to a single session sustains a p95 added latency of less than 50 ms compared to the same workload with the session store disabled (measured against the existing dev SQLite + a stubbed agent).

## Assumptions

- **No multi-tenant auth**: v1 has no caregiver identity (per feature 002 §R6), so sessions are tied to the opaque session id alone. A leaked session id reveals the conversation but no PII beyond that. This is consistent with the existing v1 security posture and is the same trust boundary as the existing CORS allow-list.
- **In-memory storage for v1**: The session store lives in the FastAPI process. Sessions are lost on restart; clients tolerate a new session id appearing in the next response. A SQLite-backed implementation is a future-feature concern and is out of scope here.
- **Single-process deployment**: The dev/demo deployment runs one uvicorn worker. Multi-worker / multi-host deployment would require a shared store (Redis, SQLite, etc.) and is out of scope for v1.
- **Existing chat-write endpoint shape is preserved**: The `POST /v1/entries` request/response schemas defined in feature 002's contracts remain backward compatible; the session id rides alongside as an optional header or response field, not a body field.
- **Token budgets are model-aware but conservative**: The prompt-token budget defaults to a value comfortably under the deployed Azure OpenAI model's context window (e.g., 12 K tokens for a 16 K-window model) to leave room for tool definitions and the model's own response.
- **Backend logging conventions are reused**: structured logging via the existing `structlog` setup; correlation id is the existing `X-Correlation-ID` header; no new log shipping infrastructure is introduced.
- **Frontend changes are minimal**: the frontend will echo whatever session id the backend issues; the existing FIFO 100-message React state for rendering the chat transcript remains a UI affordance and is independent of the backend store. (Frontend wiring lands in a follow-on planning iteration.)
