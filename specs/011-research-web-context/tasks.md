# Tasks: Context-Aware Web Research

**Input**: Design documents from `/specs/011-research-web-context/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/research-api.md](contracts/research-api.md), [contracts/session-store.md](contracts/session-store.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED — Constitution Principle II is NON-NEGOTIABLE for this repo, so contract, unit, and integration tests are first-class tasks.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story tag (US1..US6); omitted for Setup, Foundational, and Polish phases
- Every task lists the exact file path it operates on

## Path Conventions (Web app — `backend/` only for this feature)

- Backend code: `backend/src/momdiary/...`
- Backend tests: `backend/tests/{contract,unit,integration,benchmarks,evals}/...`
- Docs (feature-internal): `specs/011-research-web-context/...`
- No frontend changes (FR-018)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the one new third-party dependency and the new configuration knobs that every subsequent task reads.

- [X] T001 Add `azure-ai-projects` to `backend/pyproject.toml` (in the runtime dependency group, pinned to a version compatible with `agent-framework==1.0.0rc6` and `agent-framework-azure-ai==1.0.0rc6`) and run `pip install -e backend/` to vendor it in the active venv
- [X] T002 [P] Add research-specific settings to [backend/src/momdiary/config.py](backend/src/momdiary/config.py) per research.md Decision 10: `momdiary_research_web_search_timeout_seconds=15`, `momdiary_research_max_sources=5`, `momdiary_research_min_sources=3`, `momdiary_research_user_location_country="US"`, `momdiary_research_search_context_size="medium"`, `momdiary_research_allow_list_path=""`, `momdiary_research_guardrail_deployment=""`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the `ChatTurn` dataclass with the optional `sources` field and make the Postgres session store tolerant of the new key. Every user story that follows persists or reads a turn through this path, so it MUST land before any story work begins.

**⚠️ CRITICAL**: No user-story work in Phase 3+ can begin until this phase is complete.

- [X] T003 Extend `ChatTurn` with `sources: list[dict[str, str]] | None = None` (with module docstring noting the additive contract) in [backend/src/momdiary/agents/session_store.py](backend/src/momdiary/agents/session_store.py) per [data-model.md](specs/011-research-web-context/data-model.md) and [contracts/session-store.md](specs/011-research-web-context/contracts/session-store.md)
- [X] T004 Make `_turn_from_json` read `sources` via `d.get("sources")` and confirm `_turn_to_json` (currently `asdict`-based) emits the new field unchanged in [backend/src/momdiary/agents/pg_session_store.py](backend/src/momdiary/agents/pg_session_store.py)
- [X] T005 [P] Add `backend/tests/unit/test_pg_session_store_turn_roundtrip.py` covering: (a) write a `ChatTurn` with `sources=[{"title":"…","url":"https://…"}]` and read back equal, (b) write a `ChatTurn` with `sources=None` and read back equal
- [X] T006 [P] Add `backend/tests/unit/test_pg_session_store_backcompat.py` covering: hand-craft a JSONB row missing the `sources` key entirely, call `_load`, assert `turns[0].sources is None` (proves old rows still load)

**Checkpoint**: Foundation ready — user-story implementation can now proceed.

---

## Phase 3: User Story 1 - Web-backed answer to a single research question (Priority: P1) 🎯 MVP

**Story Goal**: Replace the placeholder so a real web search runs for every caregiver submission, and the response carries the actual sources the answer drew from, with a graceful failure-mode reply when search is unavailable.

**Independent Test**: Submit two different research questions through the existing Research-mode UI. Verify each response's `agent_message` is NOT the legacy `"(Research placeholder)"` string and that the two responses' `sources` arrays differ. Then force the search backend offline and verify the third submission returns HTTP 200 with `outcome="research_unavailable"`, empty `sources`, and the canonical unavailable copy.

### Tests for User Story 1 (write first, ensure they FAIL before implementation)

- [X] T007 [P] [US1] Contract test `backend/tests/contract/test_research_api.py` covering: happy path returns `outcome="research_answer"` with `3 ≤ len(sources) ≤ 5`, second POST with same `X-Session-ID` preserves session id, missing JWT → 401, empty `message` → 400, mocked timeout → `outcome="research_unavailable"` with empty sources, response headers include `X-Session-ID` and `X-Correlation-ID`
- [X] T008 [P] [US1] Integration test `backend/tests/integration/test_research_e2e.py` exercising the runner end-to-end with a mocked `WebSearchPort` that returns four neutral-domain citations; assert outcome=`research_answer`, assert `chat_sessions.turns` row was written with `sources` populated

### Implementation for User Story 1

- [X] T009 [P] [US1] Define `WebSearchPort` protocol and implement `FoundryWebSearchAdapter` (Pivot from research.md Decision 1 — implementation uses MAF-native `BingGroundingTool` via `AzureAIAgentClient` Agents-API surface instead of `WebSearchTool`/`FoundryChatClient`; `azure.ai.projects.models.WebSearchTool` is a Responses-API tool incompatible with MAF `AzureAIAgentClient`. Constructs `AzureAIAgentClient` with `DefaultAzureCredential`; rationale documented inline in `research_agent.py`) in [backend/src/momdiary/agents/research_agent.py](backend/src/momdiary/agents/research_agent.py)
- [X] T010 [P] [US1] Implement `clamp_sources(raw, min_n, max_n)` (3–5 clamp with dedup by host+path; no domain filter yet — domain filtering lands in US4) in [backend/src/momdiary/agents/research_policy.py](backend/src/momdiary/agents/research_policy.py)
- [X] T011 [US1] Implement `ResearchRunner.run(message, session, baby, correlation_id)` orchestration in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py): build the per-request agent, wrap `agent.run(...)` in `asyncio.wait_for(timeout=settings.momdiary_research_web_search_timeout_seconds)`, extract `url_citation` annotations, call `clamp_sources`, compose the assistant turn, persist via `session.append(...)`; on `TimeoutError` / unhandled tool error short-circuit to `outcome="research_unavailable"` with empty sources and STILL persist the failure turn (FR-022) — depends on T003, T004, T009, T010
- [X] T012 [US1] Replace [backend/src/momdiary/api/research.py](backend/src/momdiary/api/research.py): remove `_DEMO_SOURCES` and the placeholder reply; route the request through `ResearchRunner`; preserve the `ResearchRequest` / `ResearchResponse` Pydantic shapes; emit `X-Session-ID` and `X-Correlation-ID` response headers; map runner outcomes to `outcome` strings exactly as specified in [contracts/research-api.md](specs/011-research-web-context/contracts/research-api.md) — depends on T011
- [X] T013 [US1] Add `structlog` calls (one start, one end) in `ResearchRunner.run` and `api/research.py` covering FR-017 fields (`correlation_id`, `user_id`, `baby_id`, `session_id_present`, `message_length`, `age_unit`, `age_value`, `web_search_attempted`, `web_search_succeeded`, `sources_before_filter`, `sources_after_filter`, `handler_latency_ms`); assert in a unit test that the caregiver's `message` body never appears in any logged field — depends on T011, T012

**Checkpoint US1**: At this point Research mode produces real, source-cited answers and handles search outages gracefully — the MVP for this feature. US2–US6 layer on top without breaking this baseline.

---

## Phase 4: User Story 2 - Conversation context shapes follow-up answers (Priority: P1)

**Story Goal**: Multi-turn research conversations interpret follow-ups (pronouns, "what about at night?") against the prior turns in the same `X-Session-ID`.

**Independent Test**: In a single session, send a research question that establishes a topic (e.g. "is my 4-month-old's poop color normal if it's yellow-green?"), then a deliberately context-dependent follow-up ("and what about smell?"). Verify the second response's `agent_message` addresses infant stool *smell* (not generic odor), and that at least one source URL is on an infant-stool/digestion topic. Then send the same follow-up from a fresh session and verify the response is materially different.

### Tests for User Story 2

- [ ] T014 [P] [US2] Integration test `backend/tests/integration/test_research_followup.py` with a mocked `WebSearchPort` that records the search queries it receives; assert the second-turn recorded query contains tokens from the first turn (topical carry-over) and assert the first-turn-only baseline (fresh session) recorded query does NOT

### Implementation for User Story 2

- [ ] T015 [US2] In `ResearchRunner`, call `session_store.recent_view(session, token_budget=settings.momdiary_session_prompt_token_budget)` before the agent run and pass the recent turn list into the agent's chat-history input (MAF agent thread / messages list — pattern mirrors the diary agent) in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T011
- [ ] T016 [US2] Wrap the `recent_view → agent.run → session.append` sequence in `async with session.lock:` so concurrent submissions in the same session are serialized (mirrors diary runner) in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T015

**Checkpoint US2**: Follow-up turns resolve against prior context; concurrent same-session submissions are serialized.

---

## Phase 5: User Story 3 - Answers tailored to the active baby's age (Priority: P1)

**Story Goal**: Every research answer is age-appropriate. The active baby's age (computed in the right unit per FR-008) is included in BOTH the search query and the synthesis context.

**Independent Test**: Create two babies on the same account with very different ages (e.g. 2 months and 18 months). Switch the active baby and submit the same research question ("when should I worry about my baby's sleep?") twice. Verify the two `agent_message` values differ materially and each references age-appropriate norms.

### Tests for User Story 3

- [ ] T017 [P] [US3] Unit test `backend/tests/unit/test_baby_age.py` covering every boundary in the `compute_age_label` table: `dob=None`, future `dob`, `0..13d`→days, `14d..83d`→weeks, `84d..2y-1d`→months, `≥2y`→years; assert singular forms ("1 day", "1 week", "1 month", "1 year"); assert timezone-boundary case (baby turns 6 months at 11pm local)
- [ ] T018 [P] [US3] Integration test `backend/tests/integration/test_research_age.py` with a mocked `WebSearchPort` that records its query input; create two `ActiveBabyDep` overrides (2-month-old, 18-month-old), submit the same `message` for each, assert the recorded queries contain `"2 months"` vs `"18 months"` (or equivalent month/year tokens), assert FR-009 path: a baby with invalid DOB produces a request with no age token and an `agent_message` noting age tailoring was skipped

### Implementation for User Story 3

- [ ] T019 [P] [US3] Implement `AgeLabel` dataclass and `compute_age_label(dob, now, tz) -> AgeLabel` (pure function, no external calls) in [backend/src/momdiary/services/baby_age.py](backend/src/momdiary/services/baby_age.py) per [data-model.md](specs/011-research-web-context/data-model.md)
- [ ] T020 [US3] In `ResearchRunner`, call `compute_age_label(baby.date_of_birth, now, user_tz)` at request entry; append `f" for a {label.display}-old"` to the (already-redacted) search query when `unit != "none"`; inject `AgeLabel` into the synthesis prompt as a structured fact; when `unit == "none"` append a sentinel to `agent_message` ("Age-specific tailoring was skipped because the baby's date of birth is not set." — FR-009) in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T011, T019

**Checkpoint US3 — all P1 stories complete**. The product is now shippable: real web search, multi-turn context, age tailoring, and graceful failure mode. US4–US6 add quality and safety gates.

---

## Phase 6: User Story 4 - Sources are trustworthy and clickable (Priority: P2)

**Story Goal**: Returned `sources` come from a maintained allow-list of reputable parenting/health domains; spam/forum/ad-farm results are filtered out before clamping.

**Independent Test**: Submit 10 varied research questions; assert ≥ 80 % of returned URLs are on the trusted allow-list; assert no returned URL 404s or redirects to an unrelated domain (manual or scripted HEAD-check sample).

### Tests for User Story 4

- [ ] T021 [P] [US4] Unit test `backend/tests/unit/test_research_policy.py` covering: allow-listed host passes, block-listed host is filtered, subdomain matching of allow-list entries (`*.healthychildren.org`), URL dedup by host+path, the `0 after filter → no_sources_found` mapping, the `1–2 after filter → no padding` clamp behaviour

### Implementation for User Story 4

- [ ] T022 [US4] Extend [backend/src/momdiary/agents/research_policy.py](backend/src/momdiary/agents/research_policy.py) with `ALLOW_LIST` and `BLOCK_LIST` constants (initial domains per research.md Decision 3), `is_trusted_url(url) -> bool`, and `filter_and_clamp(raw, min_n, max_n, allow, block) -> list[ResearchSource]` that runs filter → dedup → order-preserving clamp; honor `settings.momdiary_research_allow_list_path` to load an override file when set — depends on T010
- [ ] T023 [US4] In `ResearchRunner`, replace the bare `clamp_sources` call with `filter_and_clamp`; when the filtered list is empty, short-circuit to `outcome="no_sources_found"` with the canonical message from [contracts/research-api.md](specs/011-research-web-context/contracts/research-api.md) and STILL persist the turn (FR-013, FR-022) in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T011, T022

**Checkpoint US4**: Source quality is policy-enforced server-side.

---

## Phase 7: User Story 5 - Caregivers see the standard medical disclaimer (Priority: P3)

**Story Goal**: Every successful research response's `agent_message` ends with the fixed not-medical-advice reminder (FR-015, SC-008).

**Independent Test**: Submit 10 varied research questions; verify every `outcome="research_answer"` response's `agent_message` ends with the canonical `RESEARCH_DISCLAIMER` string verbatim.

### Tests for User Story 5

- [ ] T024 [P] [US5] Add disclaimer assertions to `backend/tests/contract/test_research_api.py` (extend the happy-path case from T007): assert `agent_message.endswith(RESEARCH_DISCLAIMER)` for `research_answer` outcomes; assert disclaimer is NOT appended for `scope_refused`, `safety_refused`, `research_unavailable`, or `no_sources_found` outcomes

### Implementation for User Story 5

- [ ] T025 [US5] Define module-level constant `RESEARCH_DISCLAIMER` (fixed string per research.md Decision 9) and call it from `ResearchRunner.compose_final_message(model_text, outcome)` — append only when `outcome == "research_answer"` — in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T011

**Checkpoint US5**: Disclaimer guarantee enforced server-side and verified in CI.

---

## Phase 8: User Story 6 - Research stays on-topic and refuses clearly harmful requests (Priority: P2)

**Story Goal**: Off-topic prompts are scope-refused; harmful-to-baby prompts are safety-refused; both refusal paths emit `sources=[]`, do NOT call the web search, and still persist the refused turn (FR-021, FR-022, FR-023).

**Independent Test**: Submit (a) 5 off-topic prompts (finance, taxes, code, sports), (b) 5 harmful baby-related prompts from a held-out eval set, (c) 10 legitimate baby-care prompts. Verify (a) all return `scope_refused`, (b) all return `safety_refused`, (c) none are falsely refused, and the `chat_sessions` row contains the refused turn with `sources=[]`.

### Tests for User Story 6

- [ ] T026 [P] [US6] Unit test `backend/tests/unit/test_research_guardrail.py` with a mocked judge LLM returning each of `{allow, scope_refuse, safety_refuse}`; assert the runner maps each verdict to the correct `outcome` + canonical `agent_message` per [contracts/research-api.md](specs/011-research-web-context/contracts/research-api.md); assert the PII rewriter strips a sample of names/dates while preserving the medically relevant noun phrase and the appended age token
- [ ] T027 [P] [US6] Integration test `backend/tests/integration/test_research_refusal.py` covering scope refusal + safety refusal end-to-end with a mocked `WebSearchPort` that asserts it was NEVER called for either path; assert the refused turn IS appended to the session store (FR-022) with `sources=[]`

### Implementation for User Story 6

- [ ] T028 [P] [US6] Implement `redact_query(message) -> str` (LLM rewriter using the existing Azure OpenAI deployment, `max_tokens=64`, deterministic-output prompt per research.md Decision 5) and `judge(message_redacted) -> GuardrailVerdict` (LLM judge using `settings.momdiary_research_guardrail_deployment` with fallback to the diary deployment, structured-output `{verdict, reason}`, prompt per research.md Decision 6) in [backend/src/momdiary/agents/research_guardrail.py](backend/src/momdiary/agents/research_guardrail.py)
- [ ] T029 [US6] In `ResearchRunner.run`, before the web search: (1) call `redact_query`, (2) call `judge`, (3) on `scope_refuse` / `safety_refuse` short-circuit with the canonical refusal `agent_message`, `sources=[]`, and STILL persist via `session.append(...)`; pass the redacted query (not the original) into the agent for the `allow` path in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T011, T028
- [ ] T030 [US6] Extend the structured log line with `guardrail_verdict`, `guardrail_reason`, and `redacted_query_length` per FR-017 / FR-022 (never log the original `message` body); add a test in `test_research_guardrail.py` asserting the original `message` does not appear in any logged field for any verdict in [backend/src/momdiary/agents/research_runner.py](backend/src/momdiary/agents/research_runner.py) — depends on T013, T029

**Checkpoint US6**: All P1 + P2 + P3 stories complete. The full FR/SC matrix in `spec.md` is satisfied.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Micro-benchmark for `compute_age_label` and `filter_and_clamp` (both ≤ 1 ms p95 per Constitution III) in `backend/tests/benchmarks/test_research_hotpath.py`
- [ ] T032 [P] Opt-in live-model evaluation suite gated by `MOMDIARY_RUN_LIVE_EVALS=1` covering SC-002 (age tailoring), SC-003 (follow-up continuity), SC-004 (≥80 % trusted-source rate over a 50-question fixture), SC-008 (disclaimer presence), SC-009 (scope/safety on an eval set with ≥95 % scope-refuse, 100 % safety-refuse, <5 % false-positive on legitimate) in `backend/tests/evals/test_research_eval.py`
- [ ] T033 [P] If `azure-ai-projects` triggers any new MAF prerelease warnings on import or first use, document the suppression rule in [backend/docs/AGENT_FRAMEWORK_WARNINGS.md](backend/docs/AGENT_FRAMEWORK_WARNINGS.md) per Principle V
- [ ] T034 Validate [quickstart.md](specs/011-research-web-context/quickstart.md) end-to-end: run all five `curl` scenarios (happy path, follow-up, scope refusal, safety refusal, timeout) and verify Section 5's Postgres query returns the expected JSONB shape, including the refused-turn rows

---

## Dependencies & Story Completion Order

```text
Phase 1 Setup  (T001, T002)
    │
    ▼
Phase 2 Foundational  (T003 → T004; T005 [P]; T006 [P])
    │
    ▼  CHECKPOINT — all P1 stories now unblocked in parallel*
    │
    ├──► Phase 3 US1 (T007 [P], T008 [P]; T009 [P], T010 [P]; T011 → T012 → T013)
    │        │
    │        ▼  CHECKPOINT US1 — MVP shippable
    │        │
    │        ├──► Phase 4 US2 (T014 [P]; T015 → T016)         (extends T011)
    │        │        │
    │        │        ▼  CHECKPOINT US2
    │        │
    │        └──► Phase 5 US3 (T017 [P], T018 [P]; T019 [P]; T020)  (extends T011)
    │                 │
    │                 ▼  CHECKPOINT US3 — all P1 done; product launchable
    │
    ├──► Phase 6 US4 (T021 [P]; T022 → T023)                  (extends T010, T011)
    │        │
    │        ▼  CHECKPOINT US4
    │
    ├──► Phase 7 US5 (T024 [P]; T025)                         (extends T011)
    │        │
    │        ▼  CHECKPOINT US5
    │
    └──► Phase 8 US6 (T026 [P], T027 [P]; T028 [P]; T029 → T030)  (extends T011, T013)
             │
             ▼  CHECKPOINT US6 — all FR/SC satisfied
             │
             ▼
        Phase 9 Polish (T031 [P], T032 [P], T033 [P]; T034)
```

*US2, US3, US4, US5, US6 all depend only on US1's `ResearchRunner` scaffold (T011) and the foundational `ChatTurn` extension (T003/T004). Once US1 lands, US2–US6 can proceed in parallel branches if you have multiple implementers.

## Parallel Execution Examples

**Phase 2 fan-out (after T004 completes)**:

```text
T005 [P]  unit test — pg_session_store round-trip
T006 [P]  unit test — pg_session_store backcompat
```

**Phase 3 / US1 tests-first wave**:

```text
T007 [P]  contract test — /v1/research shape
T008 [P]  integration test — runner end-to-end (mocked search)
```

**Phase 3 / US1 implementation wave (after tests are failing)**:

```text
T009 [P]  research_agent.py (Foundry adapter)
T010 [P]  research_policy.py (clamp only)
# then T011 (runner) → T012 (api) → T013 (logging) sequentially
```

**Phase 5 / US3 fan-out**:

```text
T017 [P]  unit test — baby_age boundary table
T018 [P]  integration test — age token in query
T019 [P]  baby_age.py implementation
# then T020 (runner integration) sequentially
```

**Phase 8 / US6 fan-out**:

```text
T026 [P]  unit test — guardrail mocked LLM
T027 [P]  integration test — refusal paths
T028 [P]  research_guardrail.py implementation
# then T029 → T030 sequentially
```

**Phase 9 polish fan-out**:

```text
T031 [P]  benchmarks
T032 [P]  live evals (opt-in)
T033 [P]  warnings doc
# then T034 (quickstart validation) once everything else is green
```

## Implementation Strategy (incremental delivery)

1. **Complete Phase 1 + Phase 2** — adds one dependency, two settings, and one additive field on `ChatTurn`. Zero behavior change to the running app. Safe to merge on its own.
2. **Complete Phase 3 (US1)** — ship the MVP: real web-search-backed answers + graceful failure. At this point the placeholder endpoint is replaced and the frontend's Research mode "just works" with real content (no UI changes per FR-018).
3. **Add Phase 4 (US2) and Phase 5 (US3) in parallel** — both extend the US1 runner without changing the API contract. Each can land independently.
4. **Add Phases 6–8 (US4 → US5 → US6) in any order** — they cover quality (source trust), polish (disclaimer), and safety (scope/safety guardrail). Each is independently testable and atomically reversible.
5. **Phase 9 Polish** — benchmarks, opt-in live evals, and the quickstart smoke validation close the loop on Constitution III performance budgets and SC-002..009 evaluation criteria.

## Suggested MVP Scope

Phases 1 + 2 + 3 (T001 through T013). Delivers FR-001, FR-002, FR-003, FR-006, FR-011, FR-011a (clamp without filter), FR-013 (zero-source clamp), FR-014, FR-017, FR-018, FR-019, FR-020 — i.e. real web-search-backed research with graceful failure. The remaining FRs land cleanly in US2–US6.

## Format validation

Every task above:

- starts with `- [ ]` ✓
- has a sequential `T###` ID ✓
- carries `[P]` only when it touches a file no incomplete task touches ✓
- carries a `[US#]` label iff it is inside a user-story phase (Setup, Foundational, and Polish phases carry no story label) ✓
- includes the exact absolute-from-repo file path it modifies ✓
