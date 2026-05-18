# Quickstart — Backend Chat Session Store

Prerequisite: backend running locally per feature 001 quickstart:

```powershell
cd backend
uvicorn momdiary.main:app --reload --port 8000
```

## Turn 1 — fresh session, server issues an id

```powershell
$h = @{}
$r = Invoke-WebRequest -Method POST -Uri "http://localhost:8000/v1/entries" `
  -ContentType "application/json" `
  -Body '{"message":"120 ml breast milk just now"}' `
  -Headers $h
$sid = $r.Headers["X-Session-ID"]
"Session ID: $sid"
$r.Content
```

Expected: HTTP 201, body `{"outcome":"created", "entry_type":"feed", "entry":{...}, "session_id":"<uuid>", ...}`. Capture `$sid` for the next call.

## Turn 2 — same session, correction resolved from prior context

```powershell
$r2 = Invoke-WebRequest -Method POST -Uri "http://localhost:8000/v1/entries" `
  -ContentType "application/json" `
  -Body '{"message":"actually make it 90"}' `
  -Headers @{ "X-Session-ID" = $sid }
$r2.Content
```

Expected: HTTP 200, body `{"outcome":"updated", "entry":{"quantity":90,...}, "session_id":"<same uuid>", ...}`. The agent resolved "it" from the prior turn.

## Turn 3 — verify isolation: a different (or absent) session id triggers clarification

```powershell
$r3 = Invoke-WebRequest -Method POST -Uri "http://localhost:8000/v1/entries" `
  -ContentType "application/json" `
  -Body '{"message":"actually make it 90"}'
$newSid = $r3.Headers["X-Session-ID"]
"New Session ID: $newSid (should NOT equal $sid)"
$r3.Content
```

Expected: HTTP 200, body `{"outcome":"clarification_requested", "agent_message":"...", "session_id":"<new uuid>", ...}` — the agent has no context for "it" in this fresh session.

## TTL behavior

If you wait longer than `MOMDIARY_SESSION_TTL_SECONDS` (default 86400) before turn 2, the
backend treats `$sid` as expired and the response carries a brand-new `session_id`. Your
client must replace the stored id with the new one.

## Inspecting bounded memory

Logs (`structlog` JSON) include the following events you can grep for:

- `session.created` — new session was inserted, with truncated id and correlation id.
- `session.appended` — caregiver or assistant turn appended; includes `turn_count`.
- `session.evicted` — global LRU cap fired; oldest session dropped.
- `session.expired` — lookup found a session past TTL; new id issued.
- `session.append_failed` — store failure was swallowed; the user response was still sent.

Example one-liner from the uvicorn log:

```powershell
Get-Content backend\logs\*.log | Select-String "session\."
```

## Configuration

All caps are env-tunable (defaults shown):

```powershell
$env:MOMDIARY_SESSION_TTL_SECONDS = 86400
$env:MOMDIARY_SESSION_MAX_TURNS = 50
$env:MOMDIARY_SESSION_MAX_SESSIONS = 100
$env:MOMDIARY_SESSION_MESSAGE_MAX_BYTES = 4096
$env:MOMDIARY_SESSION_PROMPT_TOKEN_BUDGET = 12000
```

Restart `uvicorn` to pick them up.
