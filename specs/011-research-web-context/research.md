# Phase 0 — Research: Context-Aware Web Research

All technical unknowns from `plan.md` are resolved here. Each decision lists what was chosen, why, and the alternatives that were considered and rejected.

## Decision 1 — Web search capability

**Decision**: Use the **Azure Foundry Agent Service "Web Search" tool** (`WebSearchTool` from `azure.ai.projects.models`), wired into a MAF agent.

**Rationale**:

- **GA, lowest setup burden.** Microsoft's published guidance is "if you're just getting started, use Web Search" — no Bing resource to provision, no separate Foundry connection to manage, no per-resource RBAC. The tool is managed by Microsoft inside the Foundry Agent Service and is what the docs now recommend over the older `BingGroundingTool` (`docs/azure/ai-foundry/agents/how-to/tools/web-overview`).
- **Citations come back as structured annotations.** The agent run emits `annotation.type == "url_citation"` events carrying `.url` (and optionally `.start_index` / `.end_index`), which is exactly the (title, url) shape our API response needs (FR-011, FR-018). No HTML scraping.
- **Built-in geo + context-size knobs.** `user_location` (country/region/city) and `search_context_size` ∈ {`low`,`medium`,`high`} let us tune relevance and cost per request without adopting a separate search backend.
- **Domain restriction is supported when we need it.** When SC-004's 80% trusted-source target is at risk, we can later layer a `custom_search_configuration` (Bing Custom Search instance) into the same `WebSearchTool` — without changing our agent code. For now we use the unrestricted Web Search + server-side allow/block filter (Decision 3), which keeps Phase 1 free of additional Azure resources.

**Alternatives considered**:

- **`BingGroundingTool` (Grounding with Bing Search)**: GA, supports `count` / `freshness` / `market` / `set_lang`. Rejected for v1 because it requires creating a separate "Grounding with Bing Search" Azure resource, a Foundry project connection, and elevated RBAC (Contributor on the subscription/RG plus Foundry Project Manager). Higher operational cost for a marginal feature-set win on parameters we don't need yet. Keep as a future migration target if the freshness / market knobs become important.
- **`BingCustomSearchPreviewTool`**: Preview-only, requires both the Bing Custom Search resource and a configured instance with an allow-list. Rejected for v1 to avoid preview-tier coupling and Azure-side configuration that overlaps the server-side allow-list in Decision 3.
- **MCP web-search server (e.g. a community Brave/Tavily MCP)**: Rejected as it would introduce a non-Microsoft agent capability path (Principle V tension: "Third-Party Systems"), and would not give us a managed-by-Microsoft data path. Reconsider only if Foundry's web search proves cost- or quality-prohibitive.
- **Direct Bing Web Search v7 REST API (bypassing the agent tool surface)**: Rejected because it bypasses MAF entirely — the agent loses tool-call telemetry, we lose the `url_citation` annotation pipeline, and we'd reimplement what the Web Search tool already does.

**Data-boundary note**: Per Microsoft's documentation, queries sent to the Web Search tool flow outside the Azure compliance / geo boundary. This is acceptable because **FR-010** requires we never pass PII; the only payload sent is the sanitized, age-augmented query string (Decision 5).

## Decision 2 — Agent surface: MAF Hosted Agents path

**Decision**: Build a fresh MAF `Agent` per request using `FoundryChatClient` from `agent_framework_azure_ai` (or the rc6-equivalent client class — to be confirmed at the first implementation task), with the `WebSearchTool` registered as the only tool.

**Rationale**:

- **Matches existing pattern.** `backend/src/momdiary/agents/maf_runner.py` already builds a fresh diary `Agent` per request with bound tools. The research runner uses the same shape so the dispatcher, observability middleware, and auth dependencies behave identically.
- **Principle V.** Hosted-agent path means we stay on MAF primitives end-to-end (`agent_framework.Agent` + a Foundry chat client) instead of dropping down to the raw Azure SDK's `PromptAgentDefinition` flow, which would create persistent agent versions on every request (or require a separate provisioning workflow) and put us a step further from MAF's middleware/telemetry story.
- **No extra Azure resources.** Hosted Agents are ephemeral and in-process — no `project.agents.create_version(...)` cleanup to manage.

**Risk + mitigation**: The exact class name / constructor for the Foundry chat client in `agent_framework_azure_ai==1.0.0rc6` needs to be verified at the first implementation task (the GitHub samples reference `FoundryChatClient`; the existing code imports `AzureOpenAIChatClient` from the same package). If `WebSearchTool` is not directly accepted by the rc6 client, the documented fallback is to use the `azure-ai-projects` `AIProjectClient` to construct a `PromptAgentDefinition` once at process startup, then invoke it via the Responses API (`openai.responses.create(..., extra_body={"agent_reference": ...})`). This fallback is documented in `quickstart.md` and `contracts/research-api.md`; the public response shape is unchanged either way.

**Alternatives considered**:

- **Prompt Agents (persistent `create_version` per agent)**: Rejected as the default path — adds a Foundry-side artifact lifecycle to manage. Kept only as the fallback above.
- **Reuse the existing diary agent with a new tool**: Rejected — diary agent is bound to mutate tools (`log_feed` etc.) and a single, large system prompt. Mixing a web-search capability into it would conflict with the planned skill-split (feature 010) and pollute the diary prompt with research-mode concerns.

## Decision 3 — Source quality policy: server-side post-filter

**Decision**: Apply a **server-side allow-list + block-list** to the citations returned by the agent, then clamp to 3–5 results (target 4) per FR-011a. The lists live in `backend/src/momdiary/agents/research_policy.py` as constants with an environment override for the path (so ops can swap files without a code change).

**Rationale**:

- **Keeps Phase 1 free of additional Azure infra** (no Bing Custom Search resource). FR-012 only requires the policy to exist and be reviewable — it does not require Microsoft to enforce it.
- **Cheap to evolve.** Edits to the allow-list are a one-PR, one-restart change. A Bing Custom Search instance change is a portal-side configuration that can drift from code.
- **Composable.** When/if we later migrate to `custom_search_configuration`, the same allow-list file becomes the source of truth for the Bing instance, so no policy is lost.

**Initial allow-list domains** (illustrative — final list owned by the implementation PR):

- `healthychildren.org`, `aap.org` — American Academy of Pediatrics
- `nhs.uk`, `nice.org.uk` — UK NHS
- `cdc.gov`, `nih.gov`, `medlineplus.gov` — US gov health
- `who.int` — World Health Organization
- `mayoclinic.org`, `clevelandclinic.org`, `seattlechildrens.org`, `chop.edu`, `stanfordchildrens.org` — major children's hospitals
- `lalecheleague.org`, `kellymom.com` — established lactation references
- `zerotothree.org` — child-development non-profit

**Initial block-list patterns** (illustrative): generic-domain forums (`*.reddit.com`, `*.quora.com`), question/answer farms, ad-heavy parenting blogs that frequently surface in Bing for parenting queries but aren't peer-reviewed.

**Clamp rule** (FR-011a):

- Filter raw citations to those whose URL host matches the allow-list and does NOT match the block-list.
- If ≥ 3 filtered citations exist, take the first 3–5 (target 4) preserving the model's order.
- If 1–2 filtered citations exist, return them (no padding).
- If 0 filtered citations exist, return an empty `sources` array and a "no relevant sources found" `agent_message` (FR-013).

**Alternatives considered**:

- **Bing Custom Search instance** (Microsoft-enforced allow-list): Defer to v2 (see Decision 1).
- **No allow-list, rely on model judgment**: Rejected — Bing surfaces low-quality parenting content frequently for medical queries, and SC-004 demands ≥ 80% from a trusted set. Model-only filtering is not auditable.
- **LLM "trustedness" reranker**: Rejected for v1 as added latency for marginal benefit when a hand-maintained domain list already covers the medical-grade sources caregivers expect.

## Decision 4 — Persistence of research turns in the existing session store

**Decision**: Extend the existing `ChatTurn` dataclass with an optional `sources: list[dict] | None = None` field (where each dict is `{"title": str, "url": str}`). The Postgres-backed session store already serializes turns via `dataclasses.asdict`, so the new field is written to the existing `chat_sessions.turns` JSONB column automatically. The deserializer (`_turn_from_json`) gets one tolerant line that reads `d.get("sources")` so older rows with no `sources` key continue to round-trip.

**Rationale**:

- **No new tables, no Alembic migration.** Matches FR-006 and the Postgres-baseline established by feature 009.
- **Backward compatible.** Old diary turns serialized before this change still load cleanly; the field is `None` for those rows. New research turns set the field; new diary turns continue to leave it `None`.
- **Storage footprint is negligible.** 3–5 `{title, url}` pairs ≈ a few hundred bytes per turn. The deque cap (`max_turns * 2 = 100`) bounds the worst-case JSONB growth.
- **Available for future UI history replay** without changing the wire format again.

**Concurrency**: The existing `ChatSession.lock` (asyncio.Lock per session id) is held across `recent_view → agent.run → append`, identical to the diary flow. Single-caregiver chat surface means cross-process contention on the same session id is effectively impossible (last-writer-wins documented in `pg_session_store.py`).

**Alternatives considered**:

- **Separate `research_turns` table**: Rejected — duplicates the session-store concept, requires a new Alembic revision, and breaks the FR-006 reuse contract.
- **Persist only `(question, answer)` and re-derive sources on read**: Rejected — sources are a property of the original synthesis (Bing's index changes), so re-deriving on read produces a different answer and violates the audit-trail value of persisting them.

## Decision 5 — PII redaction strategy

**Decision**: A **tiny dedicated LLM rewrite step** runs the caregiver's message through `gpt-4.1-mini` (the same deployment used for the diary agent, no new model deployment) with a tightly-scoped instruction: "Return the medically-relevant search query; strip names, full dates of birth, addresses, contact info; preserve the age phrase appended at the end." The rewritten query (≤ 200 chars) is what is forwarded to `WebSearchTool`.

**Rationale**:

- **Free-text resists regex.** A regex-only redaction would either miss casual disclosures ("she — Olivia — has had reflux") or over-redact medically-relevant nouns. The LLM rewrite is consistent and easy to unit-test against a held-out adversarial set.
- **Same deployment, low latency.** The redaction step uses the existing `azure_openai_deployment` (gpt-4.1-mini) with `max_tokens=64`, adding ~150–300 ms — well within the SC-006 p50 < 10 s budget.
- **Audit log.** The rewritten query is logged (FR-017) under structured key `web_search_query`; the *original* message body is NOT logged (FR-017 PII rule). This lets operators verify the redaction step empirically without exposing PII.

**Hard rule for the redaction prompt**: if the model is uncertain, it MUST return only the medically-relevant noun phrase + the appended age token, never the original message verbatim. The unit test (`test_research_guardrail.py`) exercises the bypass-attempt cases.

**Alternatives considered**:

- **Microsoft Presidio (PII detection library)**: Rejected for v1 as a heavyweight dependency for a single redaction step that only needs to handle short caregiver-typed messages.
- **Regex-only**: Rejected (see "Free-text resists regex" above).

## Decision 6 — Parenting-scope + baby-safety guardrail

**Decision**: A **lightweight LLM judge** runs against the (already-redacted) query before the web search executes. It uses `gpt-4.1-mini` with a structured-output prompt returning exactly one of `{ "verdict": "allow" | "scope_refuse" | "safety_refuse", "reason": "<short string for logs>" }`. The judge's prompt enumerates explicit refuse-categories for safety (shaking, dangerous sleep practices framed as endorsements, adult-dose medication for infants, etc.) and explicit allow-categories for borderline-but-legitimate baby-care questions (allergen introduction, vaccine schedules, sleep training methods, formula vs. breastmilk, parental mental health as it affects parenting).

**Rationale**:

- **Cheap and fast.** Single `gpt-4.1-mini` call with `max_tokens=32` and structured-output mode adds ~200 ms.
- **Auditable per FR-022.** The verdict and reason go into the structured log alongside `correlation_id`, `user_id`, `baby_id`.
- **Stops PII / harmful queries from ever reaching Bing**, satisfying FR-021 and the data-boundary concern in Decision 1.
- **Refused turns still persist** (per the edge case added in clarifications) — the runner appends a `ChatTurn` with the refusal text and `sources=[]` even on a refusal path, preserving session continuity.

**Alternatives considered**:

- **Azure AI Content Safety service**: Heavier dependency, primary use case is moderation of generated content (we already get that for free from the Azure OpenAI safety filters on the synthesis call), not domain-scoping. Reconsider only if the LLM judge proves unreliable at scale.
- **Hardcoded keyword list**: Rejected — too easy to bypass with synonyms and too prone to false positives on legitimate medical vocabulary.
- **Skipping the guardrail and trusting the model's safety filters**: Rejected — Azure OpenAI's built-in filters guard against generated harmful content but do not refuse off-topic or harmful *queries* before search. The reputational risk in a baby-care product is concrete (US6).

## Decision 7 — Baby age computation

**Decision**: A pure helper `services/baby_age.py::compute_age_label(dob: date, now: datetime, tz: ZoneInfo) -> AgeLabel` returns a typed record with `value: int`, `unit: Literal["days","weeks","months","years"]`, and `display: str` (e.g. `"4 months"`). Boundary table per FR-008:

- `dob` invalid / future / `None` → `unit = "none"`, `display = ""`, and the caller skips age tailoring (FR-009).
- Otherwise, with `delta = now.date() - dob` (in the caregiver's resolved timezone):
  - `delta.days < 14` → `("days", delta.days)`
  - `delta.days < 7 * 12` → `("weeks", delta.days // 7)`
  - `delta.days < 365 * 2` → `("months", roughly delta.days * 12 // 365)` (calendar-aware via `dateutil.relativedelta` if available, else the integer approximation)
  - else → `("years", relativedelta(now, dob).years)`

The display string is appended to the (already-redacted) search query as a free-floating noun phrase (e.g. `"… for a 4-month-old"`) AND injected into the synthesis prompt as a structured fact so the answer's *content* — not just the search query — is tuned to the age.

**Rationale**:

- **Pure function = trivial unit tests.** Boundary table covers every unit transition.
- **No new dependency** if we use the stdlib `date` arithmetic; `dateutil` is already transitively available via SQLAlchemy.
- **Timezone awareness for the boundary day.** A baby who turns 6 months at 11pm local time MUST show as 6 months, not still 5 months due to UTC drift — using the existing per-request timezone (set by the auth middleware) avoids this class of bug.

**Alternatives considered**:

- **Always pass "months" regardless of age**: Rejected — "0 months" for a 3-week-old is unhelpful (FR-008).
- **Compute the unit inside the agent prompt**: Rejected — non-deterministic, untestable, and the model is unreliable at integer date arithmetic.

## Decision 8 — Timeout & failure-mode response

**Decision**: Wrap the agent run in `asyncio.wait_for(agent.run(...), timeout=15.0)` (per the clarification answer for FR-014). On `TimeoutError`, on any unhandled exception from the agent, or on an explicit "tool error" outcome, the runner produces a fixed `agent_message` ("Research is temporarily unavailable. Please try again in a moment.") + `sources=[]` and returns HTTP 200 (FR-014). The refused / failed turn IS still appended to the session store (FR-022) so the next caregiver follow-up has correct conversational context.

**Rationale**: Preserves the existing frontend contract (any 5xx would break the chat UX), keeps the failure path indistinguishable in shape from a normal response, and gives the caregiver a clear next-step.

**Alternatives considered**:

- **Returning 503 on search failure**: Rejected — breaks the FR-018 "no UI changes required" contract and the existing UI would show a generic network-error toast instead of the friendly in-bubble message.
- **Retrying inside the 15 s window**: Rejected for v1 — the 15 s window is already generous (per clarification); adding a retry would push worst-case latency above the implied SC-006 + FR-014 budget.

## Decision 9 — Disclaimer composition

**Decision**: A module-level constant `RESEARCH_DISCLAIMER` (fixed string, e.g. `"This is general information, not medical advice. Always consult your pediatrician for medical decisions about your baby."`) is appended to the agent's synthesized message verbatim on every successful research response (SC-008 trivially verifiable). Refusal responses (scope / safety / unavailable) do NOT append it — they have their own dedicated message strings.

**Rationale**: Always-include policy (clarification Q3 = A) → constant string → automated assertion is straightforward.

## Decision 10 — Configuration & dependencies

**Decision**: Add the following settings to `momdiary.config.Settings`:

| Key | Default | Purpose |
|---|---|---|
| `momdiary_research_web_search_timeout_seconds` | `15` | FR-014 |
| `momdiary_research_max_sources` | `5` | FR-011a upper bound |
| `momdiary_research_min_sources` | `3` | FR-011a lower bound for the "≥3" rule |
| `momdiary_research_user_location_country` | `"US"` | `WebSearchTool.user_location.country` default |
| `momdiary_research_search_context_size` | `"medium"` | `WebSearchTool.search_context_size` |
| `momdiary_research_allow_list_path` | `""` (use built-in) | Optional override file path |
| `momdiary_research_guardrail_deployment` | `""` (falls back to `azure_openai_deployment`) | Allows ops to point the judge at a cheaper deployment without code change |

Add one new dependency to `backend/pyproject.toml`: `azure-ai-projects` (Azure SDK that exposes `WebSearchTool` and related models). No version pin chosen here — the implementation task selects a version compatible with the rc6 MAF pin and records it in `AGENT_FRAMEWORK_WARNINGS.md` if any prerelease warning suppressions are required (Principle V).

**Rationale**: Centralizing tunables in `Settings` matches the existing pattern (Principles I & IV). All defaults are sensible for the v1 launch; nothing forces ops to set anything to ship the feature.

## Open items resolved by this phase

- ✅ Which Azure/MAF web-search capability → Decision 1 (Web Search tool).
- ✅ How to wire it into MAF without breaking the existing per-request agent pattern → Decision 2.
- ✅ How to enforce "trusted sources" without adding Azure infra → Decision 3.
- ✅ Where research turns live → Decision 4 (existing `chat_sessions` JSONB, additive `sources` field).
- ✅ PII handling → Decision 5.
- ✅ Scope / safety policy implementation → Decision 6.
- ✅ Age computation contract → Decision 7.
- ✅ Failure-mode UX contract → Decision 8.
- ✅ Disclaimer contract → Decision 9.
- ✅ Settings + new dependency → Decision 10.

No `NEEDS CLARIFICATION` markers remain.
