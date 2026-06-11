# Contract — `POST /v1/research`

**Status**: Backward compatible with the existing placeholder endpoint shipped before this feature. Frontend code in `frontend/src/features/research/*` requires no changes (FR-018).

## Request

```
POST /v1/research HTTP/1.1
Authorization: Bearer <Clerk JWT>
Content-Type: application/json
X-Active-Baby-Id: <optional integer baby id>
X-Session-ID: <optional opaque session id from a prior response>
X-Correlation-ID: <optional UUID; server generates one if absent>
```

### JSON body

| Field | Type | Required | Rules |
|---|---|---|---|
| `message` | `str` | yes | 1 ≤ len ≤ 4000 chars after strip; ≤ 4096 bytes UTF-8 |
| `correlation_id` | `str` | no | UUID v4; if omitted, server generates one and echoes via response header |

Example:

```json
{
  "message": "How much night sleep should my baby get?",
  "correlation_id": "9f1c0c8e-1b3c-4d2a-8e9f-7a0b3c1d2e3f"
}
```

## Response — 200 OK (single shape for all outcomes)

| Field | Type | Notes |
|---|---|---|
| `outcome` | `Literal[...]` | one of `research_answer`, `research_unavailable`, `scope_refused`, `safety_refused`, `no_sources_found` |
| `agent_message` | `str` | always present; for `research_answer` ends with the not-medical-advice disclaimer (SC-008) |
| `sources` | `list[{title: str, url: str}]` | length 3–5 for `research_answer`; length 0 for every other outcome |
| `correlation_id` | `str` | echoed from request or server-generated |
| `session_id` | `str \| null` | new session id minted on first call; thereafter the value sent by the client in `X-Session-ID` (or freshly minted on expiry/cross-partition) |

### Outcome semantics

| `outcome` | When | `sources` | `agent_message` |
|---|---|---|---|
| `research_answer` | guardrail allowed + search succeeded + ≥1 trusted source after filtering | 3–5 trusted citations | model-synthesized answer + disclaimer |
| `no_sources_found` | guardrail allowed + search succeeded + 0 trusted sources after filtering (FR-013) | `[]` | "I couldn't find a reliable source for this. Try rephrasing, or consult your pediatrician." |
| `research_unavailable` | search timed out (FR-014) or upstream tool error | `[]` | "Research is temporarily unavailable. Please try again in a moment." |
| `scope_refused` | guardrail verdict = `scope_refuse` | `[]` | "I can only help with baby-care research questions. Please rephrase as a question about your baby's care." |
| `safety_refused` | guardrail verdict = `safety_refuse` | `[]` | "I can't help with that request. If you have concerns about your baby's safety, please contact your pediatrician or an emergency line." |

### Response headers

| Header | Always | Value |
|---|---|---|
| `X-Session-ID` | yes | Echoes the session id the client should send on the next turn |
| `X-Correlation-ID` | yes | Echoes the resolved correlation id |
| `Content-Type` | yes | `application/json` |

### Example success

```json
{
  "outcome": "research_answer",
  "agent_message": "Most pediatric guidance suggests that a 4-month-old typically needs 10–12 hours of nighttime sleep ... This is general information, not medical advice. Always consult your pediatrician for medical decisions about your baby.",
  "sources": [
    {"title": "Sleep — HealthyChildren.org (AAP)", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/"},
    {"title": "Baby sleep patterns — NHS", "url": "https://www.nhs.uk/conditions/baby/caring-for-a-newborn/helping-your-baby-to-sleep/"},
    {"title": "Infant Sleep — CDC", "url": "https://www.cdc.gov/sleep/about/infants.html"},
    {"title": "Sleep needs by age — Cleveland Clinic", "url": "https://my.clevelandclinic.org/health/articles/12148-sleep-basics"}
  ],
  "correlation_id": "9f1c0c8e-1b3c-4d2a-8e9f-7a0b3c1d2e3f",
  "session_id": "c8a4d8e2-..."
}
```

### Example scope refusal

```json
{
  "outcome": "scope_refused",
  "agent_message": "I can only help with baby-care research questions. Please rephrase as a question about your baby's care.",
  "sources": [],
  "correlation_id": "...",
  "session_id": "..."
}
```

## Error responses

| Status | When |
|---|---|
| `400` | `message` missing / empty / too long, or malformed JSON |
| `401` | Missing / invalid Clerk JWT |
| `403` | Authenticated user has no active baby and the request lacks `X-Active-Baby-Id` (existing `ActiveBabyDep` behavior) |
| `429` | (future) per-user rate limit; not enforced in v1 |

Notably, **search-side failures never produce 5xx** — they map to `outcome: "research_unavailable"` per FR-014 to keep the chat UX consistent.

## Non-goals

- This endpoint does NOT mutate diary entries (no log_feed / log_sleep / log_poop).
- This endpoint does NOT expose raw model traces, raw Bing JSON, or tool-call IDs.
- This endpoint does NOT echo the caregiver's `message` back in the response (no PII roundtrip).

## Test gates (from `tests/contract/test_research_api.py`)

1. POST with a typical message → 200, `outcome == "research_answer"`, `len(sources) in {3,4,5}`, `agent_message.endswith(RESEARCH_DISCLAIMER)`, `X-Session-ID` header present.
2. POST a second time with the same `X-Session-ID` → server preserves session id (no rotation on the happy path).
3. POST without `Authorization` → 401.
4. POST with body `{"message": ""}` → 400.
5. POST with mocked web-search timeout → 200, `outcome == "research_unavailable"`, `sources == []`, `agent_message` matches the unavailable copy verbatim.
6. POST with mocked guardrail `safety_refuse` → 200, `outcome == "safety_refused"`, `sources == []`, message matches refusal copy verbatim.
