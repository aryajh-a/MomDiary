# Phase 1 — Data Model: Backend-Side Chat Session Store

All entities are in-memory Python dataclasses (no SQL schema). Persistence is by reference
inside the `InMemorySessionStore`; no serialization format is committed in v1.

## Entity: `ChatTurn`

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | `Literal["caregiver", "assistant"]` | yes | Producer of the turn. |
| `text` | `str` | yes | The caregiver's raw message, or the assistant's `agent_message`. Trimmed to `MOMDIARY_SESSION_MESSAGE_MAX_BYTES`. |
| `outcome` | `Literal["created","updated","deleted","clarification_requested","rejected"] \| None` | only on assistant turns | Mirrors the dispatcher's `AgentRunResult.outcome`. `None` for caregiver turns. |
| `entry_type` | `Literal["feed","sleep","poop","appointment"] \| None` | when applicable | Only set for write outcomes. |
| `entry_id` | `int \| None` | when applicable | Only set for write outcomes. |
| `correlation_id` | `str` | yes | Matches the HTTP response's correlation id for end-to-end traceability. |
| `created_at` | `datetime` (UTC, tz-aware) | yes | Wall-clock at insertion. |

**Invariants**:
- A caregiver turn is always immediately followed (within the same dispatcher call) by
  an assistant turn with the same `correlation_id`.
- `outcome`, `entry_type`, `entry_id` are jointly null on caregiver turns and jointly
  consistent on assistant turns (e.g., `outcome="created"` ⇒ `entry_id is not None`).

## Entity: `ChatSession`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | `str` (UUID v4) | yes | Server-issued, opaque, unguessable. |
| `created_at` | `datetime` (UTC) | yes | Set on first `get_or_create`. |
| `last_activity_at` | `datetime` (UTC) | yes | Updated on every `append`, `recent_view`, and successful lookup. Drives TTL + LRU. |
| `turns` | `collections.deque[ChatTurn]` | yes | `maxlen = MOMDIARY_SESSION_MAX_TURNS * 2`. `deque.append` evicts oldest FIFO automatically once the cap is reached. |
| `lock` | `asyncio.Lock` | yes | Per-session serialization (FR-014). |

**Invariants**:
- `len(turns) ≤ MOMDIARY_SESSION_MAX_TURNS * 2`.
- `last_activity_at ≥ created_at`.
- Turn pairs are ordered: indices `2k` are caregiver, `2k+1` are assistant — except after
  FIFO eviction may begin with an assistant turn if a caregiver-only stub was already
  truncated. The token-aware view tolerates either ordering.

## Aggregate: `SessionStore` (protocol) + `InMemorySessionStore`

```python
class SessionStore(Protocol):
    async def get_or_create(self, session_id: str | None) -> ChatSession: ...
    async def append(self, session: ChatSession, turn: ChatTurn) -> None: ...
    async def recent_view(self, session: ChatSession, token_budget: int) -> list[ChatTurn]: ...
    async def evict_expired(self, now: datetime | None = None) -> int: ...
```

**Behavior contracts** (all enforced by the in-memory backend, mirrored in tests):

1. `get_or_create(None)` always issues a fresh UUID v4 and inserts a `ChatSession`.
2. `get_or_create(id)` with `id` unknown OR with `last_activity_at` older than the
   configured TTL returns a **new** session with a new id (FR-007, FR-010). The caller
   uses the returned `ChatSession.id` for the response envelope.
3. `get_or_create` enforces the global cap `MOMDIARY_SESSION_MAX_SESSIONS`. When full,
   the LRU session (smallest `last_activity_at`) is evicted before insertion. A
   `session.evicted` log record is emitted.
4. `append(session, turn)` updates `last_activity_at` and pushes to the bounded `deque`
   (FIFO eviction on overflow). It also enforces `len(turn.text.encode("utf-8")) ≤
   MOMDIARY_SESSION_MESSAGE_MAX_BYTES`; oversize text raises `SessionMessageTooLargeError`
   which the API translates to a 400 validation envelope (FR-012).
5. `recent_view(session, token_budget)` returns the largest suffix of `session.turns`
   whose token-estimate sum is ≤ `token_budget`. It never returns more than the full
   `turns` list. It also updates `last_activity_at`.
6. `evict_expired(now)` walks the dict and removes sessions where
   `now - last_activity_at > TTL`. Called lazily from `get_or_create` (amortized) and
   exposed for the unit test that uses `freezegun` to fast-forward.

**Concurrency contract**:
- `get_or_create` and the LRU/expired walk acquire the store-level lock.
- `append` and `recent_view` acquire `session.lock` (not the store-level lock — the
  session is already known to the caller).
- The dispatcher wraps `recent_view → agent.run → append(caregiver) + append(assistant)`
  inside `async with session.lock:` so the agent always sees a self-consistent history.

**Prompt-injection contract (FR-004 — history MUST reach the agent)**:
- `MAFAgentRunner.run` MUST receive the `recent_view` result via an explicit `history`
  keyword argument; it MUST NOT silently default to `[]` when the caller forgets to pass
  it. The runner asserts `history is not None` (an empty list is allowed; `None` is a
  programming error).
- The runner MUST render `history` into the `full_message` string passed to
  `bundle.agent.run(...)` via a dedicated `_render_history(history) -> str` helper.
  The helper's output is included in `full_message` under a `"Conversation so far:\n"`
  preamble whenever `history` is non-empty.
- A unit test MUST capture the exact `full_message` the runner sends to the agent and
  assert the rendered history block matches the expected oldest→newest text.
- See [plan.md "Agent Invocation Flow"](./plan.md#agent-invocation-flow-history-inclusion--fr-004)
  for the canonical sequence and rendered format.

## Errors

| Error | Raised by | HTTP mapping |
|---|---|---|
| `SessionMessageTooLargeError(ValueError)` | `append` | 400 `{ "error": "validation_error", "message": "caregiver message exceeds N bytes", "correlation_id": ... }` (FR-012) |
| _store-internal failures_ | `append`, `recent_view` | swallowed + logged WARN; request succeeds with degraded context (FR-016) |

## Configuration entities

The five new settings (see [research.md §7](./research.md#decision-7--configuration-namespace))
attach to `momdiary.config.Settings` as plain `int` fields with defaults; no separate
config entity is introduced.

## Out of scope

- Per-caregiver identity (no users in v1).
- Cross-process or cross-host session sharing.
- Persistence across restarts.
- Frontend state shape — the frontend continues to render its FIFO 100-message React
  state; it only needs to learn to echo `X-Session-ID`.
