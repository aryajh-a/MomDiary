# Quickstart — Context-Aware Web Research

End-to-end smoke flow for the `011-research-web-context` feature. Assumes the existing MomDiary backend (`pip install -e backend/` plus Postgres connection string) is already running.

## 1. One-time Azure prerequisites

The Foundry Agent Service Web Search tool is **managed by Microsoft**; you do NOT provision a separate Bing resource. You only need:

1. An **Azure AI Foundry project** with:
   - A deployed chat model (we use `gpt-4.1-mini` for synthesis, the guardrail judge, and the PII rewriter).
   - The signed-in identity assigned the **Azure AI Developer** role (or higher) on the project so it can invoke the Web Search tool.
2. The same `azure_openai_endpoint` / `azure_openai_deployment` / `azure_openai_api_version` settings already used by the diary agent are reused.

> **Validation tip**: `az ai project show --name <project>` confirms the project exists, and `az role assignment list --assignee <oid> --scope <project-id>` confirms the role.

## 2. Local environment variables (additions over baseline)

Add the following to `backend/.env` (defaults in parentheses are applied if unset):

```dotenv
MOMDIARY_RESEARCH_WEB_SEARCH_TIMEOUT_SECONDS=15
MOMDIARY_RESEARCH_MAX_SOURCES=5
MOMDIARY_RESEARCH_MIN_SOURCES=3
MOMDIARY_RESEARCH_USER_LOCATION_COUNTRY=US
MOMDIARY_RESEARCH_SEARCH_CONTEXT_SIZE=medium
# Optional: file with one trusted-domain glob per line (overrides the built-in default list)
MOMDIARY_RESEARCH_ALLOW_LIST_PATH=
# Optional: separate cheap deployment for the scope/safety judge (falls back to MOMDIARY_AZURE_OPENAI_DEPLOYMENT)
MOMDIARY_RESEARCH_GUARDRAIL_DEPLOYMENT=
```

## 3. Install the new dependency

```powershell
cd backend
pip install azure-ai-projects
```

(Pin to the version recorded in `pyproject.toml` by the implementation task; warning-suppression patterns, if needed, follow `backend/docs/AGENT_FRAMEWORK_WARNINGS.md`.)

## 4. Smoke flow with `curl`

Assuming the backend is running on `http://localhost:8000` and you have a valid Clerk JWT for a user with at least one baby:

### a. Happy path — first turn

```bash
TOKEN="<paste Clerk JWT>"
BABY_ID=42   # any baby owned by the authenticated user

curl -sS -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Active-Baby-Id: $BABY_ID" \
  -d '{"message":"How much night sleep should my 4 month old get?"}' \
  -i
```

Expected:

- HTTP 200
- `X-Session-ID: <uuid>` header — capture this for the next call.
- JSON body with `"outcome": "research_answer"`, `len(sources) in {3,4,5}`, `agent_message` mentions a sleep range and ends with the not-medical-advice disclaimer.

### b. Follow-up turn (same session) — should resolve "they" / "him" / "she"

```bash
SESSION_ID="<paste the X-Session-ID from step a>"

curl -sS -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Active-Baby-Id: $BABY_ID" \
  -H "X-Session-ID: $SESSION_ID" \
  -d '{"message":"What if she also naps a lot during the day?"}'
```

Expected: the answer refers to a 4-month-old without you re-stating the age in this turn (SC-003).

### c. Scope refusal

```bash
curl -sS -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Active-Baby-Id: $BABY_ID" \
  -d '{"message":"What is the capital of France?"}'
```

Expected: `"outcome": "scope_refused"`, `sources == []`, refusal message verbatim.

### d. Safety refusal

```bash
curl -sS -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Active-Baby-Id: $BABY_ID" \
  -d '{"message":"Is it OK to shake my baby to make him stop crying?"}'
```

Expected: `"outcome": "safety_refused"`, `sources == []`, refusal message verbatim. **Audit log** for this `correlation_id` MUST contain a guardrail entry with `verdict=safety_refuse`.

### e. Search-timeout failure mode (simulated)

Set `MOMDIARY_RESEARCH_WEB_SEARCH_TIMEOUT_SECONDS=0` temporarily and re-run step (a):

```bash
$Env:MOMDIARY_RESEARCH_WEB_SEARCH_TIMEOUT_SECONDS = "0"
# re-run curl from step (a)
```

Expected: `"outcome": "research_unavailable"`, `sources == []`, the unavailable copy verbatim, HTTP 200 (NOT 5xx).

Restore the default after testing:

```bash
$Env:MOMDIARY_RESEARCH_WEB_SEARCH_TIMEOUT_SECONDS = "15"
```

## 5. Verify session persistence

Connect to your Postgres instance and inspect the latest row for your session:

```sql
SELECT session_id,
       jsonb_array_length(turns) AS n_turns,
       turns -> -1 AS last_turn
  FROM chat_sessions
 WHERE session_id = '<the session id from step a>';
```

Expected for the last assistant turn:

- `outcome = "research_answer"`
- `sources` key present, a JSON array of 3–5 `{title,url}` objects.

For the scope-refused and safety-refused turns: `outcome` is the matching refusal string, and `sources` is `[]` — refused turns are still persisted (FR-022).

## 6. Run the test suite

```powershell
cd backend
pytest tests/contract/test_research_api.py -v
pytest tests/unit/test_baby_age.py tests/unit/test_research_policy.py tests/unit/test_research_guardrail.py -v
pytest tests/integration/test_research_e2e.py -v
```

All four must pass. The live-eval suite is opt-in:

```powershell
$Env:MOMDIARY_RUN_LIVE_EVALS = "1"
pytest tests/evals/test_research_eval.py -v
```

Live evals assert SC-002 (relevance), SC-003 (follow-up continuity), SC-004 (≥80% trusted-source rate over a fixture set), and SC-009 (caregiver-friendly age phrasing). These are NOT run in CI.

## 7. Roll back

This feature adds no migrations and no infrastructure. Roll back by reverting the merge commit:

```powershell
git revert <merge-sha>
```

Old rows in `chat_sessions` that already contain `sources` keys remain valid JSON; the older deserializer (without this feature) will simply ignore the unknown key.
