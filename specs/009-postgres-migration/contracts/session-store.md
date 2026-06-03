# Contract: `SessionStore` Protocol

**Feature**: 009-postgres-migration  
**Source of truth**: [backend/src/momdiary/agents/session_store.py](backend/src/momdiary/agents/session_store.py) — unchanged.

This contract is **reused as-is from feature 003**. The new
`PgSessionStore` implementation MUST satisfy it identically to the
existing `InMemorySessionStore`. The parity contract test
([tests/contract/test_pg_session_store.py](backend/tests/contract/test_pg_session_store.py), new)
runs the same scenarios against both implementations and asserts equal
behaviour.

## Public surface (Python `Protocol`, async)

```python
class SessionStore(Protocol):
    async def get_or_create(
        self,
        session_id: str | None,
        *,
        correlation_id: str | None = None,
        user_id: str,
        baby_id: int,
    ) -> ChatSession: ...

    async def append(self, session: ChatSession, turn: ChatTurn) -> None: ...

    def recent_view(
        self, session: ChatSession, token_budget: int
    ) -> list[ChatTurn]: ...

    async def evict_expired(self, now: datetime | None = None) -> int: ...

    async def purge_user(self, user_id: str) -> int: ...
```

## Behavioural invariants (both implementations)

| ID    | Invariant                                                                                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ |
| SS-01 | `get_or_create(None, ...)` creates a fresh session with a new opaque `session_id` and returns it; subsequent calls with that id resolve to the same session. |
| SS-02 | `get_or_create("missing", ...)` for an unknown id creates a fresh session **bound to the supplied id** (idempotent client retries).  |
| SS-03 | `append` is order-preserving: the N-th appended turn occupies index N-1 of `session.turns`.                                          |
| SS-04 | Turn count never exceeds `MOMDIARY_SESSION_MAX_TURNS`; excess turns are dropped FIFO (oldest first).                                 |
| SS-05 | Any single message exceeding `MOMDIARY_SESSION_MESSAGE_MAX_BYTES` is truncated (existing helper); contract preserved.                |
| SS-06 | `recent_view` returns the most-recent suffix of `session.turns` whose serialized token estimate fits in `token_budget`.              |
| SS-07 | `evict_expired(now)` removes sessions with `updated_at < now - MOMDIARY_SESSION_TTL_SECONDS` and returns the number removed.         |
| SS-08 | `purge_user(user_id)` removes every session owned by `user_id` and returns the count.                                                |
| SS-09 | All write methods are safe to call concurrently from multiple workers for *different* `session_id` values without data loss or deadlock. |
| SS-10 | `append` for the same `session_id` from two workers is last-write-wins on `turns`; no row is deleted; `updated_at` is monotonic.     |

## Implementation differences (allowed, non-observable)

| Aspect            | `InMemorySessionStore`                  | `PgSessionStore`                                                                |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------------------- |
| Persistence       | Process dict; lost on restart           | Postgres `chat_sessions` table; survives restart and is shared across workers   |
| Concurrency model | `asyncio.Lock` per session              | Postgres MVCC; upsert via `INSERT ... ON CONFLICT (session_id) DO UPDATE`       |
| TTL execution     | In-process `evict_expired` call         | Same method signature; uses `DELETE ... WHERE updated_at < ...` under advisory lock |
| Bound on size     | LRU eviction at `MAX_SESSIONS`          | No global cap (rows expire via TTL); LRU not required because storage is durable |

These differences are deliberately invisible at the Protocol boundary.
The parity test does not exercise them; it only asserts SS-01 … SS-10.
