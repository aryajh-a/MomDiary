# Phase 1 — Data Model: MomDiary Tracker UX

The frontend stores no domain data. The "data model" here is the **shape of the client-side application state** and the **shape of the wire payloads** consumed from the backend. All wire shapes mirror existing Pydantic schemas in `backend/src/momdiary/models/schemas.py` and are validated by Zod on receipt.

## Wire entities (consumed)

### `FeedEntry`

| Field         | Type                | Notes                                                                |
|---------------|---------------------|----------------------------------------------------------------------|
| `id`          | integer (positive)  | Primary key.                                                          |
| `feed_type`   | enum                | One of `breast_milk`, `formula`, `solids`, `water`.                   |
| `quantity`    | number (> 0)        | Display together with `unit`.                                         |
| `unit`        | enum                | One of `ml`, `g`.                                                     |
| `occurred_at` | ISO-8601 w/ offset  | Render in browser local time.                                         |
| `created_at`  | ISO-8601 w/ offset  | Not displayed; carried for parity.                                    |
| `updated_at`  | ISO-8601 w/ offset  | Not displayed; carried for parity.                                    |

### `SleepEntry`

| Field              | Type                | Notes                                              |
|--------------------|---------------------|----------------------------------------------------|
| `id`               | integer (positive)  |                                                    |
| `start_at`         | ISO-8601 w/ offset  | Render local-time + delta.                         |
| `end_at`           | ISO-8601 w/ offset  | MUST be after `start_at` (already enforced server). |
| `duration_minutes` | integer (≥ 0)       | Server-computed; the UI MUST display it as `Xh Ym`.|
| `created_at`       | ISO-8601 w/ offset  |                                                    |
| `updated_at`       | ISO-8601 w/ offset  |                                                    |

### `PoopEntry`

| Field          | Type                | Notes                                                  |
|----------------|---------------------|--------------------------------------------------------|
| `id`           | integer (positive)  |                                                        |
| `occurred_at`  | ISO-8601 w/ offset  |                                                        |
| `consistency`  | enum                | One of `watery`, `soft`, `formed`, `hard`.             |
| `created_at`   | ISO-8601 w/ offset  |                                                        |
| `updated_at`   | ISO-8601 w/ offset  |                                                        |

### `AppointmentEntry`

| Field          | Type                       | Notes                                                                |
|----------------|----------------------------|----------------------------------------------------------------------|
| `id`           | integer (positive)         |                                                                      |
| `scheduled_at` | ISO-8601 w/ offset         | Render local-time.                                                   |
| `notes`        | list of `AppointmentNote`  | Sorted oldest-first by backend; UI displays only the **most-recent** note inline (last item). |
| `created_at`   | ISO-8601 w/ offset         |                                                                      |
| `updated_at`   | ISO-8601 w/ offset         |                                                                      |

### `AppointmentNote`

| Field      | Type               | Notes                          |
|------------|--------------------|--------------------------------|
| `id`       | integer (positive) |                                |
| `body`     | string (1..2000)   | Displayed verbatim.            |
| `added_at` | ISO-8601 w/ offset |                                |

### List wrappers

Each section endpoint returns a `*ListResponse`:

```ts
{ date: string /* YYYY-MM-DD */, items: <Entry>[] }
```

### Agent-write envelope (`POST /v1/entries`)

Response body union (status code 200 or 201):

```ts
type AgentWriteResponse =
  | { outcome: "created"; entry_type: EntryType; entry_id: number; payload: AnyEntry; agent_message: string; correlation_id: string }
  | { outcome: "updated"; entry_type: EntryType; entry_id: number; payload: AnyEntry; agent_message: string; correlation_id: string; unchanged?: boolean }
  | { outcome: "deleted"; entry_type: EntryType; entry_id: number; agent_message: string; correlation_id: string }
  | { outcome: "clarification_requested"; agent_message: string; suggested_candidates?: TargetCandidate[]; correlation_id: string }
  | { outcome: "rejected"; agent_message: string; correlation_id: string };

type EntryType = "feed" | "sleep" | "poop" | "appointment";
```

Error body (any non-2xx):

```ts
{ error: string; message: string; correlation_id: string }
```

## Client state shape

### `SelectedDate`

- Single `Date` (calendar day, no time component) held in React state via `useSelectedDate`. Default: today in `Intl.DateTimeFormat().resolvedOptions().timeZone`.
- Transitions: `setDate(next)` — fires no network call directly; instead the TanStack Query keys (`["feeds", iso(date)]`, etc.) change which causes a coordinated refetch.

### `ChatMessage`

```ts
{
  id: string;                                // local uuid
  role: "caregiver" | "assistant";
  text: string;
  ts: number;                                 // Date.now()
  correlation_id?: string;                   // assistant messages only
  error?: { code: string; message: string }; // assistant messages only, on failed turn
}
```

### `ChatSession`

```ts
{
  messages: ChatMessage[];   // FIFO-evicted at length 100 (R7 in research.md)
  inFlight: boolean;         // disables submit while a request is pending
  draft: string;             // current input value
}
```

State transitions:

| From state            | Event                    | To state                                          | Side effect                                |
|-----------------------|--------------------------|---------------------------------------------------|--------------------------------------------|
| `inFlight=false`      | user clicks **Send**     | `inFlight=true`, append caregiver msg             | POST `/v1/entries`; assign correlation id  |
| `inFlight=true`       | response 2xx, success    | `inFlight=false`, append assistant msg (success)  | Invalidate query key for affected section  |
| `inFlight=true`       | response 2xx, clarif.    | `inFlight=false`, append assistant msg (question) | No section invalidation                    |
| `inFlight=true`       | response non-2xx / throw | `inFlight=false`, append assistant msg (error)    | Preserve draft so user can retry           |

### Per-section query state (`useFeeds`, etc.)

Driven entirely by TanStack Query. Each hook:

```ts
useQuery({
  queryKey: ["feeds", iso(date)],          // canonical key from queryKeys.ts
  queryFn: () => apiClient.getFeeds(date), // returns parsed FeedListResponse
  staleTime: 30_000,
});
```

`refetch()` is exposed to power the manual refresh control (FR-008) and is invoked from the chat mutation's `onSuccess` to satisfy FR-009.

## Invariants & validation rules

1. **Local-time invariant**: every `*_at` field is converted via `new Date(s)` (which handles the offset) and then formatted with `Intl.DateTimeFormat` in the browser's tz. No client-side string concatenation of times.
2. **Empty list invariant**: if `items.length === 0`, the section MUST render the type-specific empty-state copy from `frontend/src/features/<type>/empty.ts`. Never render an empty `<ul>`.
3. **Chat ordering invariant**: `messages` is append-only during a session; index is the chronological order.
4. **Single in-flight invariant**: `ChatSession.inFlight=true` disables the submit button and the input is read-only. Prevents the back-to-back-write race described in the spec's edge cases.
5. **Error preserves draft invariant**: on error the `draft` value MUST equal the caregiver's last submission text so they can edit and retry.
6. **Section-isolation invariant**: a failed `useFeeds` MUST NOT prevent `useSleeps`, `usePoops`, `useAppointments` from rendering (FR-007).
