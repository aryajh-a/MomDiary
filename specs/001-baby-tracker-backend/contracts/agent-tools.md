# Agent Tool Contracts: MomDiary Diary Agent

**Feature**: 001-baby-tracker-backend
**Date**: 2026-05-16

The single conversational endpoint (`POST/PUT /v1/entries`) delegates to one
Microsoft Agent Framework agent (the "Diary Agent") that owns the following
tools. Each tool MUST have at least one contract test that calls it with
realistic structured arguments and verifies the resulting persisted state
(Principle II).

The agent's system prompt MUST enforce:

- Choose exactly one tool per turn, unless the user describes multiple
  distinct events (FR-002).
- Never fabricate missing required fields; ask for clarification instead
  (FR-011).
- For updates and deletes, prefer an explicit `entry_id` from the
  request envelope; otherwise resolve from the message; otherwise ask
  (FR-017, FR-018).
- All timestamps emitted by tool arguments are ISO-8601 with the offset
  derived from `settings.default_timezone` (FR-012).

---

## Tool: `log_feed`

Creates a new `feeds` row.

| Argument       | Type                | Required | Notes |
| -------------- | ------------------- | -------- | ----- |
| `feed_type`    | enum                | yes      | `breast_milk`, `formula`, `solids`, `water` |
| `quantity`     | number > 0          | yes      | After normalization |
| `unit`         | enum                | yes      | `ml`, `g` (oz normalized to ml before call) |
| `occurred_at`  | ISO-8601 + offset   | yes      | Past or now ± 5 min |

Outcome: `created`.

## Tool: `update_feed`

Updates an existing `feeds` row.

| Argument        | Type                | Required | Notes |
| --------------- | ------------------- | -------- | ----- |
| `entry_id`      | integer             | yes      | Either from envelope or agent-resolved |
| `feed_type`     | enum                | no       | Omit to leave unchanged |
| `quantity`      | number > 0          | no       | |
| `unit`          | enum                | no       | |
| `occurred_at`   | ISO-8601 + offset   | no       | |

Outcome: `updated`. Idempotent (FR-015).

## Tool: `delete_feed`

Soft-deletes a `feeds` row.

| Argument   | Type    | Required |
| ---------- | ------- | -------- |
| `entry_id` | integer | yes      |

Outcome: `deleted` (sets `deleted_at`).

---

## Tool: `log_sleep`

| Argument   | Type              | Required | Notes |
| ---------- | ----------------- | -------- | ----- |
| `start_at` | ISO-8601 + offset | yes      | |
| `end_at`   | ISO-8601 + offset | yes      | Must differ from `start_at` |

Spanning-midnight sessions are valid; the entry is filed under `start_at`'s
date (FR-009).

## Tool: `update_sleep`

| Argument   | Type              | Required |
| ---------- | ----------------- | -------- |
| `entry_id` | integer           | yes      |
| `start_at` | ISO-8601 + offset | no       |
| `end_at`   | ISO-8601 + offset | no       |

## Tool: `delete_sleep`

| Argument   | Type    | Required |
| ---------- | ------- | -------- |
| `entry_id` | integer | yes      |

---

## Tool: `log_poop`

| Argument      | Type                | Required | Notes |
| ------------- | ------------------- | -------- | ----- |
| `occurred_at` | ISO-8601 + offset   | yes      | |
| `consistency` | enum                | yes      | `watery`, `soft`, `formed`, `hard` |

If the user describes consistency outside the enum, the agent MUST either
map to the closest known category with explicit confirmation in
`agent_message`, or ask for clarification.

## Tool: `update_poop` / `delete_poop`

Same shape as feed analogues.

---

## Tool: `log_appointment`

| Argument       | Type                | Required | Notes |
| -------------- | ------------------- | -------- | ----- |
| `scheduled_at` | ISO-8601 + offset   | yes      | Future timestamps allowed |
| `note`         | string              | no       | If present, creates one `appointment_notes` row in the same transaction |

Outcome: `created`. Returns the appointment with its notes array (one
element if `note` was supplied).

## Tool: `add_appointment_note`

Appends a note to an existing appointment (FR-006). Notes accumulate; the
existing notes are never overwritten.

| Argument         | Type    | Required |
| ---------------- | ------- | -------- |
| `appointment_id` | integer | yes      |
| `body`           | string  | yes      |

Outcome: `updated` (on the appointment), with the appointment's full notes
array in the response.

## Tool: `update_appointment`

| Argument        | Type              | Required |
| --------------- | ----------------- | -------- |
| `entry_id`      | integer           | yes      |
| `scheduled_at`  | ISO-8601 + offset | no       |

Note text editing is NOT exposed in v1 (per data-model.md). Adding a new
note uses `add_appointment_note`.

## Tool: `delete_appointment`

Soft-deletes the appointment. Associated notes become hidden via the
parent filter; the note rows are retained.

| Argument   | Type    | Required |
| ---------- | ------- | -------- |
| `entry_id` | integer | yes      |

---

## Tool: `ask_for_clarification`

A pseudo-tool the agent calls when it cannot satisfy FR-011 / FR-017 /
FR-018 unambiguously. It does not touch persistence.

| Argument               | Type                                    | Required |
| ---------------------- | --------------------------------------- | -------- |
| `question`             | string                                  | yes      |
| `suggested_candidates` | array of `{entry_type, entry_id, summary}` | no       |

Outcome surfaced as `clarification_requested` in the HTTP response.

---

## Cross-cutting contract rules

- Every tool call MUST be wrapped by the dispatcher that writes a
  corresponding `agent_interactions` row (FR-013) with `selected_tool`,
  `outcome`, `latency_ms`, `correlation_id`, `entry_type`, `entry_id`.
- Tools MUST validate their own arguments and raise structured errors that
  the dispatcher converts to HTTP 400; SQL CHECK constraints are the last
  line of defense, not the first.
- Tool implementations MUST be deterministic given identical arguments and
  identical SQLite state (Principle II).
