# Contract — `chat_sessions.turns` JSONB shape (backward-compatible extension)

**Storage**: Azure Postgres Flexible Server, table `chat_sessions` (introduced in feature 009).
**Column**: `turns JSONB NOT NULL`, holds a JSON array of `ChatTurn` objects.

## Existing per-turn shape (before this feature)

```jsonc
{
  "role": "user" | "assistant",
  "text": "string",
  "correlation_id": "uuid",
  "created_at": "2026-06-05T10:00:00+00:00",
  "outcome": "log_feed_success" | null,
  "entry_type": "feed" | "sleep" | "poop" | null,
  "entry_id": 123 | null
}
```

## Extended per-turn shape (this feature)

```jsonc
{
  "role": "assistant",
  "text": "Most pediatric guidance suggests ... not medical advice. Consult your pediatrician.",
  "correlation_id": "uuid",
  "created_at": "2026-06-05T10:00:01+00:00",
  "outcome": "research_answer",
  "entry_type": null,
  "entry_id": null,

  // NEW (additive, optional, may be absent on older rows)
  "sources": [
    {"title": "Sleep — HealthyChildren.org (AAP)", "url": "https://..."},
    {"title": "Baby sleep patterns — NHS",         "url": "https://..."}
  ]
}
```

## Compatibility rules

1. **Add-only.** No existing keys are renamed, removed, or have their types changed.
2. **Optional.** `sources` is absent on:
   - All caregiver (`role == "user"`) turns.
   - All assistant turns whose `outcome` is a diary outcome (not a research outcome).
   - All assistant research turns produced by older code paths (none exist yet, but the reader is tolerant either way).
3. **Default on read.** `_turn_from_json` reads `sources` via `d.get("sources")`, mapping a missing key to `None`. `None` and `[]` are semantically distinct: `None` ⇒ "not applicable to this turn" (e.g. a diary turn); `[]` ⇒ "research turn ran but found no sources or was refused" (FR-013, FR-022).
4. **Bounded size.** `sources` length is 0 ≤ n ≤ 5 (enforced at write time by `research_policy.filter_and_clamp`). Each item is ≤ ~300 bytes (`{title ≤ 200 chars, url ≤ 2048 chars}`), so the JSONB worst-case growth per turn is < 2 KB. Given `momdiary_session_max_turns=50` pairs, the JSONB column stays comfortably under any practical limit.
5. **Read fan-out.** No new index is required; all reads continue to be by `(session_id, user_id, baby_id)` primary key.

## Forbidden in `sources`

- HTML / Markdown in `title` (titles are plain text taken from Bing's `url_citation` annotation).
- Non-HTTPS URLs (FR-009 implication; validated by Pydantic `HttpUrl` + explicit scheme check).
- Duplicate URLs (deduplicated by host+path before clamping).

## Migration

**None.** No Alembic revision is generated for this feature. The schema in `2026XXXX_009_chat_sessions.py` is sufficient as-is.

## Test gates

- `tests/unit/test_pg_session_store_turn_roundtrip.py` (NEW): writes a `ChatTurn` with `sources=[...]`, reads it back, asserts equality; writes a `ChatTurn` with `sources=None`, asserts the dict written to JSONB omits the key OR has `sources: null` (either is acceptable — only the read-side default matters).
- `tests/unit/test_pg_session_store_backcompat.py` (NEW): inserts a hand-crafted JSONB row missing the `sources` key entirely, calls `_load`, asserts `turns[0].sources is None`.
