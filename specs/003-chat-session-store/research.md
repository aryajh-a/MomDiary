# Phase 0 — Research: Backend-Side Chat Session Store

All spec-level NEEDS CLARIFICATION items were resolved at /speckit.specify time via the
**Assumptions** block of [spec.md](./spec.md). This document records the *technical*
decisions taken before Phase 1 design, with rationale and alternatives.

## Decision 1 — Storage backend: in-process Python dict

- **Decision**: A module-level `InMemorySessionStore` backed by `dict[str, ChatSession]`,
  protected by a single `asyncio.Lock` for the dict (create/evict) and a per-session
  `asyncio.Lock` for append/read serialization (FR-014).
- **Rationale**: The user explicitly requested "in memory session management". The dev /
  demo deployment runs a single `uvicorn` worker (Constitution-aligned: no shared
  infrastructure introduced). A dict gives O(1) lookup and O(K) recent-view where K is the
  configured turn cap (default 50). Bounded memory is trivially provable (≤ max_sessions ×
  max_turns × max_message_bytes ≈ 100 × 100 × 4096 ≈ 40 MB worst case, ~2.5 MB typical).
- **Alternatives considered**:
  - *SQLite-backed table* — adds an Alembic migration, write amplification on every turn,
    and pulls the persistence concern into the agent path. Reverse: the spec calls out
    SQLite as a future-feature concern; deferred.
  - *Redis* — introduces an external service and breaks the "single process, no new
    infrastructure" constraint.
  - *LRU cache library (cachetools `TTLCache`)* — almost fits, but mixing TTL eviction
    with LRU and a per-session lock complicates the contract. A bespoke 80-line class is
    clearer and easier to test.

## Decision 2 — Session identifier scheme: server-issued UUID v4 via `X-Session-ID`

- **Decision**: When `X-Session-ID` header is absent (or unknown / expired), the backend
  creates a new session and issues a fresh UUID v4. The id is returned both in the
  `X-Session-ID` response header **and** as a `session_id` field in every response body
  envelope (write, clarification, error). Clients echo it on subsequent requests via the
  header.
- **Rationale**: Cryptographic strength of UUID v4 (≥ 122 bits of randomness) satisfies
  FR-008 without auth. Header transport keeps the request/response *body* schemas backward
  compatible with feature 002's contracts (additive `session_id` field on responses is
  allowed because `_StrictModel` only forbids extras on *input*, not output — and existing
  client code that ignores unknown response fields continues to work). Echoing the id in
  the body, too, makes the contract easy to test from `curl` without inspecting headers.
- **Alternatives considered**:
  - *Cookie* — requires `credentials: 'include'` on the frontend `fetch`, conflicts with
    `allow_credentials=False` in the existing CORS config, and forces a CORS rework.
  - *Body field on request* — would require adding `session_id` to `AgentWriteRequest`
    (which has `extra="forbid"`), and would break clients that ignore unknown response
    fields. Headers are the standard transport for session ids.
  - *Client-generated id* — moves the unguessability burden to every client; a malicious
    client could forge short ids. Server issuance is cheaper and stronger.

## Decision 3 — Retention policy: FIFO turn cap + idle TTL + global LRU

- **Decision**: Three independent caps, each configurable via env:
  - Per-session FIFO turn-pair cap (default **50** pairs ≈ 100 messages). Append-with-evict-oldest.
  - Per-session idle TTL (default **86 400 seconds = 24 h**). Checked lazily on lookup;
    if `now - last_activity > TTL`, the session is treated as missing and a fresh id is issued.
  - Global resident-sessions cap (default **100**). On create, if the dict is full, the
    least-recently-used session (`last_activity` ascending) is evicted.
- **Rationale**: FIFO bounds working memory per conversation; TTL reclaims idle sessions
  (matches the typical "I closed the tab" lifecycle); LRU bounds the dict itself. Three
  independent caps are simpler to reason about than one combined policy and map 1:1 to
  the three failure modes (long conversation, abandoned conversation, abuse).
- **Alternatives considered**:
  - *Background sweeper task* — adds a long-running coroutine in the lifespan and a new
    failure mode (sweep crash kills retention). Lazy eviction on read+write is sufficient
    for in-process storage.
  - *Token-based cap only* — easier to overflow if turns are short, harder to reason
    about resident memory.

## Decision 4 — Token-aware trimming on read

- **Decision**: When constructing the agent prompt, walk the session's turns oldest→
  newest and drop from the front until the accumulated token estimate is ≤
  `MOMDIARY_SESSION_PROMPT_TOKEN_BUDGET` (default **12000**, leaving headroom under the
  16 K window of `gpt-4.1`). Token estimate uses a cheap heuristic
  (`len(text) / 4 + 4`) — accurate to ~10% for English text, no new dependency.
- **Rationale**: Avoid pulling in `tiktoken` (a multi-megabyte native dep) for a 10%
  improvement in estimate accuracy. The conservative budget (12 K of 16 K) absorbs the
  heuristic error and the room needed for the system prompt + tool schemas + model
  response.
- **Alternatives considered**:
  - *`tiktoken`* — exact counts, but heavyweight install and an upgrade liability whenever
    Azure rolls a new tokenizer.
  - *No trim, rely on cap only* — could still overflow if 50 pairs × 4 KB each = 200 KB
    of caregiver text ≈ 50 K tokens, well over the 16 K window.

## Decision 5 — Concurrency: per-session `asyncio.Lock`

- **Decision**: Each `ChatSession` carries an `asyncio.Lock`. The dispatcher acquires
  it for the duration of `append + agent.run + append` (atomic from the model's
  perspective). The store-level lock is held only during `dict` mutation.
- **Rationale**: Holding the per-session lock around the model call ensures the agent
  never sees a partially-applied history (FR-014), at the cost of serializing concurrent
  turns from the same session id — which is the desired behavior, since two simultaneous
  caregiver messages on the same tab cannot both be "in the past" of the other.
- **Alternatives considered**:
  - *Optimistic concurrency with retries* — overcomplicated for the expected workload
    (one caregiver typing on one tab).
  - *No locking* — racy; two near-simultaneous turns could read identical history and
    produce duplicate writes.

## Decision 6 — Logging surface

- **Decision**: Use the existing `structlog` logger with four event names:
  `session.created`, `session.appended`, `session.evicted`, `session.expired`. All carry
  `correlation_id` + a truncated session id (`session_id[:8]`) to keep raw ids out of
  centralized logs.
- **Rationale**: Matches Constitution-mandated structured logging without inventing a
  new logging pattern. Truncation mitigates the v1 "session id is a bearer token"
  exposure for log aggregators.
- **Alternatives considered**:
  - *Log raw session ids* — equivalent to logging bearer tokens; rejected.

## Decision 7 — Configuration namespace

- **Decision**: Five new `MOMDIARY_SESSION_*` env vars added to `config.Settings`:
  - `MOMDIARY_SESSION_TTL_SECONDS` (int, default 86400)
  - `MOMDIARY_SESSION_MAX_TURNS` (int, default 50; counts turn-*pairs*)
  - `MOMDIARY_SESSION_MAX_SESSIONS` (int, default 100)
  - `MOMDIARY_SESSION_MESSAGE_MAX_BYTES` (int, default 4096)
  - `MOMDIARY_SESSION_PROMPT_TOKEN_BUDGET` (int, default 12000)
- **Rationale**: Single prefix keeps `.env` greppable; defaults match the spec.
- **Alternatives**: nested config object — unnecessary for 5 flat ints.

## Decision 8 — Failure isolation: store errors must not fail the request

- **Decision**: Both `append` calls (caregiver-pre, assistant-post) are wrapped in
  `try/except Exception` inside the dispatcher; on failure, a `WARN` log
  (`session.append_failed`) is emitted with the correlation id and the request still
  completes with its normal outcome (FR-016).
- **Rationale**: The session store is a context optimization, not a critical path.
  Losing a turn degrades the *next* turn (which may fall back to clarification) but must
  never lose a caregiver-visible side effect.

## Open Questions

None remain. All clarification candidates were either resolved by the spec's Assumptions
or by the decisions above.
