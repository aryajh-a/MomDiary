# Feature Specification: Context-Aware Web Research

**Feature Branch**: `011-research-web-context`
**Created**: 2026-06-05
**Status**: Draft
**Input**: User description: "Enhance research api to search user's query on web with context of conversation and baby's age"

## Clarifications

### Session 2026-06-05

- Q: What per-request timeout caps the external web search call before the system returns the graceful “research unavailable” response (FR-014)? → A: 15 seconds
- Q: How many source citations should a successful research response return in the `sources` array? → A: 3–5 sources (target 4)
- Q: How is a question identified as “health-related” for the in-text disclaimer (FR-015 / SC-008)? → A: Always include it on every research response
- Q: How are previous research turns persisted across requests in the shared chat session store? → A: Persist question + answer text + sources array per turn (sources stored but not auto-injected into next turn’s synthesis prompt)
- Q: How should the system handle off-topic or potentially harmful requests sent through Research mode? → A: Parenting-scope check + safety refusal for clearly harmful baby-care requests

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Web-backed answer to a single research question (Priority: P1)

A caregiver opens the chat panel, switches to **Research** mode, and asks a free-text question (e.g. "is it normal for babies to spit up after every feed?"). Today the `/v1/research` endpoint returns a hard-coded placeholder reply with three generic links and ignores the question text. After this feature, the same submission triggers a real web search, the caregiver receives an answer that synthesizes information from the top web results, and the "Sources" section lists the actual pages the answer drew from (title + URL), not the static demo list.

**Why this priority**: This is the headline value of the feature. Without it, Research mode is non-functional — caregivers cannot get information back from the web at all. Every other story builds on the assumption that real search results are flowing.

**Independent Test**: From the existing frontend Research mode, send a question that has no plausible static answer (e.g. a current-events parenting topic). Verify the agent reply text references information from the live web (not the placeholder string starting with "(Research placeholder)") and that the `sources` array contains at least one URL whose page actually discusses the question. Verify no two consecutive different questions return identical source lists.

**Acceptance Scenarios**:

1. **Given** the caregiver is authenticated with an active baby selected, **When** they submit "what are common reasons for a 6-month-old to refuse the bottle?" in Research mode, **Then** the response `agent_message` summarizes information drawn from web results and `sources` lists the URLs that information came from.
2. **Given** a question whose top results clearly differ from another question's results, **When** the caregiver submits each question, **Then** the two responses return different `sources` lists (the endpoint is no longer returning the static three-link placeholder).
3. **Given** the live web search backend is temporarily unavailable, **When** the caregiver submits a research question, **Then** the response contains a clear user-facing message that web search is currently unavailable (not the old placeholder reply, and not a 500 error in the UI), and `sources` is empty.

---

### User Story 2 - Conversation context shapes follow-up answers (Priority: P1)

Research mode is a back-and-forth conversation, not a one-shot lookup. When the caregiver sends a follow-up like "what about at night?" after asking about bottle refusal, the research agent MUST interpret the follow-up in the context of the prior turns in the same chat session — re-running search and synthesis with the resolved intent ("nighttime bottle refusal in a 6-month-old") rather than treating "what about at night?" as a standalone query. The session is the same one already tracked by the existing `X-Session-ID` header that the frontend round-trips on every research submission.

**Why this priority**: Without follow-up handling, Research mode behaves like a search box, not an assistant — caregivers would have to re-type all the context every turn. Same priority as US1 because together they define what "research conversation" means.

**Independent Test**: In a single chat session, send a first research question that establishes a topic (e.g. "is my 4-month-old's poop color normal if it's yellow-green?"), then a deliberately context-dependent follow-up ("and what about smell?"). Capture both responses. The second response's `agent_message` MUST address smell **in the context of infant stool color/consistency**, not generic information about smell, and at least one source in the second response MUST be relevant to infant stool — confirming the search query was rewritten using prior turns. Send the same follow-up question with no prior turns (new session) and verify the response is materially different (generic or asks for clarification).

**Acceptance Scenarios**:

1. **Given** a research session with one prior exchange about infant stool color, **When** the caregiver sends "and what about smell?", **Then** the agent's reply discusses infant stool smell (not generic odor topics) and at least one source URL is about infant stool/digestion.
2. **Given** the same follow-up "and what about smell?" with no prior session turns, **When** the caregiver submits it, **Then** the agent either asks for clarification about what topic the caregiver means OR returns a clearly generic answer — and the response is not identical to the contextualized response from Scenario 1.
3. **Given** a chat session has exceeded the conversation-history limit the existing session store enforces, **When** the caregiver sends a follow-up, **Then** the agent uses whatever recent turns the store still retains (no error, no crash) and the response remains coherent for those retained turns.

---

### User Story 3 - Answers are tailored to the active baby's age (Priority: P1)

The system already knows which baby is "active" for the request (via the existing active-baby selection that drives every other endpoint) and the baby's date of birth. Every research answer MUST be tailored to that baby's current age — e.g. for "what foods can I introduce?" the answer for a 5-month-old MUST focus on readiness signs and first purees, while the same question for a 10-month-old MUST focus on finger foods and allergen exposure. Age MUST be included in the web search query the system issues AND in the context used to synthesize the answer, so the returned sources are age-relevant (not adult or generic-pediatric).

**Why this priority**: Age is the single most important variable in parenting advice — an answer that is right for a newborn is dangerous for a toddler and vice versa. P1 because the user explicitly called this out and because returning age-inappropriate sources would actively harm trust (and potentially the baby).

**Independent Test**: Create two test babies on the same account with very different ages (e.g. 2 months and 18 months). Switch the active baby and submit the *same* research question ("when should I worry about my baby's sleep?") for each. The two responses MUST differ: the agent message MUST mention age-appropriate norms for each age, and the source URLs SHOULD include at least one page whose title or content is specific to that age band (newborn/infant vs. toddler).

**Acceptance Scenarios**:

1. **Given** the active baby is 2 months old, **When** the caregiver asks "when should I worry about my baby's sleep?", **Then** the agent's reply references newborn/infant sleep norms (e.g. short cycles, frequent night wakings as normal) and at least one source is about infant sleep.
2. **Given** the active baby is 18 months old, **When** the caregiver submits the same question, **Then** the agent's reply references toddler sleep norms (e.g. consolidated night sleep, nap transitions) and the response is materially different from Scenario 1.
3. **Given** the active baby's date of birth is set, **When** any research question is submitted, **Then** the baby's current age (in the most informative unit — days for newborns, weeks for the first few months, months thereafter) is reflected somewhere in the agent's response or in the topical focus of the returned sources.
4. **Given** a baby whose date of birth is in the future or otherwise invalid, **When** a research question is submitted, **Then** the system MUST NOT crash; it answers without an age constraint and the response notes that age-specific tailoring was skipped.

---

### User Story 4 - Sources are trustworthy and clickable (Priority: P2)

Because parenting advice has real health consequences, the "Sources" affordance the UI already renders MUST be backed by results from reputable sources — major pediatric health organizations, hospitals, government health bodies, and established parenting publications — not random forums, ad-heavy content farms, or SEO spam. Each returned source MUST have a clean, clickable URL and a human-readable title that matches the actual page title closely enough that the caregiver can recognize it before clicking.

**Why this priority**: Caregivers will click through to verify the advice — that's the entire point of citing sources. If clicks lead to junk pages, trust collapses and the feature is worse than the static placeholder it replaced. P2 (not P1) because the feature is still useful with imperfect source curation in early iterations.

**Independent Test**: Submit 10 varied research questions covering feeding, sleep, illness, milestones, and safety. For each response, manually open every source URL. Verify (a) every URL loads a real page (no 404s, no parked domains), (b) the page title roughly matches the title field returned by the API, and (c) at least 80% of all returned sources come from a maintained allow-list of trusted health/parenting domains.

**Acceptance Scenarios**:

1. **Given** any research response, **When** the caregiver clicks any source link, **Then** the URL opens the actual referenced page (no broken links, no redirects to unrelated content).
2. **Given** any research response, **When** the response is inspected, **Then** every source's title is a non-empty string that recognizably corresponds to the page at the URL.
3. **Given** the search backend returns a result from a low-quality domain (per the allow-list / block-list policy), **When** the response is assembled, **Then** that result is excluded from the `sources` array.

---

### User Story 5 - Caregivers see the standard medical disclaimer (Priority: P3)
Every research response MUST be accompanied by a clear, consistent disclaimer that the information is general guidance, not medical advice, and that the caregiver should consult a healthcare professional for medical decisions. The existing UI already renders a research-mode disclaimer banner; this story formalizes that the same reminder MUST also appear inside the agent's textual reply on every research response, removing the need to classify whether a given question is “health enough” to warrant it.

**Why this priority**: P3 because the UI already shows a static disclaimer banner today, so the legal/safety floor is covered. Reinforcing it in the agent text on every turn is a polish/safety improvement, not a launch blocker, and is trivially verifiable.

**Independent Test**: Submit 10 varied research questions — a mix of health-flavored and clearly non-health (e.g. “best stroller for travel”). Confirm every response includes the standard one-line “not medical advice / consult your pediatrician” reminder in the `agent_message`. Confirm the static UI disclaimer banner still renders for every research turn.

**Acceptance Scenarios**:

1. **Given** any research question (health-related or not), **When** the response is returned, **Then** the `agent_message` contains a brief, consistent reminder that the answer is not medical advice and to consult a healthcare professional.
2. **Given** any research response, **When** rendered in the existing UI, **Then** the standard research-mode disclaimer banner the UI already shows remains visible (no regression).
3. **Given** the same disclaimer text is included on many consecutive responses, **When** they are inspected, **Then** the wording is consistent across responses (i.e. the disclaimer is a fixed string rather than re-generated each turn).

### User Story 6 - Research stays on-topic and refuses clearly harmful requests (Priority: P2)

Research mode is a baby-care assistant, not a general-purpose search proxy. When a caregiver submits a question that is clearly outside parenting/baby-care scope (e.g. “best stock to buy this year,” “how do I file my taxes”), the system MUST politely decline and explain the scope rather than running a web search. Separately, when a question is clearly harmful to a baby (e.g. asking how to shake or discipline an infant, asking for adult medication doses for an infant, asking how to leave a baby unattended in unsafe conditions), the system MUST refuse and surface a safety-oriented message — NOT search the web for an answer.

**Why this priority**: This is the minimum responsible content policy for a baby-care product. Without it, the endpoint is a generic web-search proxy that will happily answer dangerous prompts — a meaningful reputational and safety risk. P2 (not P1) because the medical-disclaimer (US5) and the failure-mode response (US1 Scenario 3) already provide some bottom-floor protection, but P2 is firm because this is the surface where misuse is most visible.

**Independent Test**: Submit (a) 5 clearly off-topic questions (finance, taxes, code help, sports), (b) 5 clearly harmful baby-related prompts drawn from a known eval set (e.g. shaking, dosing adult meds, unsafe sleep practices framed as endorsements), and (c) 10 legitimate baby-care questions. Verify (a) returns a polite scope refusal with empty `sources`, (b) returns a safety refusal with empty `sources` and the safety message, and (c) returns normal web-backed answers — with no false positives (legitimate questions wrongly refused).

**Acceptance Scenarios**:

1. **Given** a question that is clearly outside parenting/baby-care scope, **When** submitted, **Then** the response is a polite scope-refusal message in `agent_message` (e.g. “I’m here to help with questions about your baby’s care…”), `sources` is empty, and no external web search is issued.
2. **Given** a question that requests information that could harm a baby (shaking, unsafe sleep practices framed as endorsements, adult-dose medication for an infant, etc.), **When** submitted, **Then** the response is a safety-refusal message in `agent_message` that does NOT supply the requested information, `sources` is empty, and no external web search is issued.
3. **Given** a legitimate baby-care question on the borderline (e.g. “when can my baby try peanut butter?”), **When** submitted, **Then** the scope/safety guardrail does NOT refuse; the question is treated as a normal research request.
4. **Given** any refused request (scope or safety), **When** logged, **Then** the refusal MUST be recorded with a refusal reason (`scope` or `safety`) for review, while honoring the existing PII-not-logged rule (FR-017).

---

### Edge Cases

- **Empty or single-character query** (already partially handled by the existing `min_length=1` validation): the system MUST respond with a friendly prompt to rephrase, NOT issue an empty web search.
- **Baby has no date of birth recorded** (legacy data or future invalid date): age-tailoring is skipped; the agent answers generically and SHOULD mention that age-specific tailoring was not applied so the caregiver can interpret the answer accordingly.
- **Web search backend hard failure / network timeout / quota exhausted**: the response MUST be a structured "research unavailable" reply (US1 Scenario 3) — never a stack trace, never the static placeholder.
- **Search backend returns zero results** (very obscure query): the agent MUST tell the caregiver no relevant sources were found and offer to refine the question, instead of fabricating an answer with no citations.
- **Caregiver submits a question in a non-English language**: the system MUST respond in the same language as the question, and the search query passed to the web backend MUST also be in that language (otherwise sources will be irrelevant).- **Question contains personally identifying information** (e.g. caregiver pastes the baby's full name and date of birth into the question): the system MUST NOT pass that PII verbatim into a third-party web search; it MUST rewrite the query to use only the medically relevant terms plus the baby's age.
- **Long conversation context** (caregiver has been chatting for many turns): the agent MUST keep the request within whatever conversation-window limit the existing session store already enforces — older turns may be summarized or dropped, but the latest few turns MUST always be considered for follow-up resolution.
- **Multiple babies on the account, none currently active**: the API already requires an active baby; this case continues to return the existing 4xx error and is out of scope.
- **Streaming vs. non-streaming**: the existing endpoint returns a single JSON response; this feature preserves that contract — no streaming.
- **Concurrent submissions in the same session**: if the caregiver submits a second question before the first response returns, behavior MUST be deterministic — either both succeed independently in the order received, or the second is rejected with a clear message. (Defer to the existing chat session store's concurrency model; do not introduce a new one.)
- **Refused requests still need a session turn**: when the scope or safety guardrail refuses (US6), the refusal turn MUST still be appended to the chat session store (with `sources` empty) so subsequent follow-ups (“what about…?”) have correct context and aren’t silently dropped from history.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `/v1/research` endpoint MUST execute a real web search for every caregiver submission and synthesize a natural-language answer from the top results. The static placeholder reply and static `_DEMO_SOURCES` list MUST be removed from the response path.
- **FR-002**: The endpoint MUST continue to require an authenticated user and an active baby, preserving the existing authorization contract.
- **FR-003**: The endpoint MUST continue to honor the `X-Session-ID` request header for session continuity and to echo it on the response, preserving the existing client contract.
- **FR-004**: When an inbound `X-Session-ID` corresponds to an existing research conversation, the system MUST retrieve the most recent prior turns for that session and use them as context when interpreting the new message (e.g. resolving "what about at night?" against the prior topic).
- **FR-005**: When no `X-Session-ID` is supplied or the session has no prior turns, the system MUST treat the message as a standalone query (no false context).
- **FR-006**: The research agent MUST append/persist each exchange to the chat session store as a single turn carrying (a) the caregiver's question text, (b) the agent's answer text, and (c) the full `sources` array returned to the client (each entry: `title` + `url`). Persistence MUST reuse the existing session store mechanism the diary chat already uses; no separate research-only store is introduced. Persisted sources MUST be retrievable for future UI session-history features but are NOT required to be auto-injected into the synthesis prompt of subsequent turns — only the conversation text drives follow-up resolution (FR-004).
- **FR-007**: The system MUST compute the active baby's current age from the baby's recorded date of birth at the time the request is processed, and MUST include that age in both (a) the search query issued to the web backend and (b) the context provided to the answer-synthesis step.
- **FR-008**: Age MUST be expressed in the most informative unit for the baby's life stage: days for the first 14 days, weeks up to ~12 weeks, months up to ~24 months, and years beyond that. The system MUST NOT pass an unhelpful unit (e.g. "0 years" for a 3-week-old).
- **FR-009**: If the active baby has no date of birth, an unparseable date of birth, or a date of birth in the future, the system MUST proceed without age tailoring, MUST NOT crash, and SHOULD note in the answer that age tailoring was skipped.
- **FR-010**: The system MUST NOT forward personally identifying information from the caregiver's message (baby name, full date of birth, addresses, contact info) to the external web search backend. Search queries MUST be rewritten to use only the medically/topically relevant terms plus the computed age.
- **FR-011**: The response `sources` array MUST contain the actual web sources the answer drew from. Each entry MUST have a non-empty `title` recognizable to the page it points to and a `url` that resolves to that page. The static demo source list MUST be gone.
- **FR-011a**: On a successful research response, the `sources` array MUST contain between 3 and 5 entries (target: 4) drawn from the filtered, trusted-domain results. If fewer than 3 usable results remain after filtering, the system MUST return whatever usable results it has (down to 1) rather than padding with low-quality results. If zero usable results remain, FR-013 applies (empty array + “no relevant sources found” answer).
- **FR-012**: Source results from disallowed domains (per a maintained allow-list of trusted health/parenting domains, plus a block-list for known low-quality domains) MUST be filtered out before the response is returned. The policy itself (which domains are trusted) is owned by the implementation but MUST exist and be reviewable.
- **FR-013**: If the web search backend returns zero usable sources after filtering, the response MUST be a clearly-worded "no relevant sources found" answer with an empty `sources` array — the system MUST NOT fabricate citations or invent URLs.
- **FR-014**: If the web search backend is unreachable, errors out, or does not return usable results within **15 seconds** of the request being issued to it, the response MUST be a clearly-worded "research is temporarily unavailable" message with an empty `sources` array, and the HTTP status MUST remain 200 so the existing frontend handles it identically to a normal response (preserving the current UX contract).
- **FR-015**: Every research response MUST include a brief, consistent, fixed-wording reminder in the `agent_message` that the answer is general information and not medical advice, and the caregiver should consult a healthcare professional. The reminder MUST be present regardless of whether the question is judged “health-related,” so no per-question classification is required.
- **FR-016**: The system MUST respond in the same natural language as the caregiver's question, and MUST issue the web search in that same language so that returned sources are linguistically appropriate.
- **FR-017**: The system MUST log per-request, at minimum: correlation id, user id, baby id, session id (presence), question length, computed age unit + value (or "none"), whether a web search was attempted, whether it succeeded, the count of sources returned before and after filtering, and the total handler latency. PII from the question body MUST NOT appear in logs.
- **FR-018**: The response schema (`outcome`, `agent_message`, `sources[].title`, `sources[].url`, `correlation_id`, `session_id`) MUST remain backward-compatible with the current frontend so no UI changes are required for the existing Research mode to render real answers and sources.
- **FR-019**: Health-information accuracy disclaimers and source-quality controls (FR-012, FR-015) MUST be enforced server-side; clients MUST NOT be the sole place these rules are applied.
- **FR-020**: The feature MUST NOT alter or write to any diary entries (feed/sleep/poop/appointment). Research is a read-only-with-respect-to-diary surface; only the chat session store is written.
- **FR-021**: Before issuing any external web search, the system MUST evaluate the question against (a) a parenting/baby-care scope check and (b) a baby-safety check. If the question is clearly outside parenting/baby-care scope, the system MUST return a polite scope-refusal `agent_message`, empty `sources`, and MUST NOT issue an external web search. If the question requests information that could harm a baby (e.g. shaking, dangerous sleep practices framed as endorsements, adult-dose medication for an infant), the system MUST return a safety-refusal `agent_message` that does NOT supply the requested information, empty `sources`, and MUST NOT issue an external web search.
- **FR-022**: Refused requests (scope or safety) MUST still be persisted to the chat session store as a turn (per FR-006) with `sources` empty, and the refusal reason (`scope` or `safety`) MUST be included in the structured log line (per FR-017), without logging the question body verbatim.
- **FR-023**: The scope/safety guardrail MUST be tuned to minimize false positives on legitimate borderline baby-care questions (e.g. allergen introduction, vaccine schedules, sleep training methods, formula-vs-breastmilk questions, parental mental-health-as-it-affects-parenting). The exact rules/wording are an implementation detail but the policy MUST exist and be reviewable.

### Key Entities *(include if feature involves data)*

- **Research Conversation Turn**: A single (question text, answer text, sources array, timestamp) record scoped to a chat session, a user, and a baby. Sources are stored as part of the turn payload (each entry: `title` + `url`) so they can be re-rendered by future UI history features. Reuses the existing chat session store model — no new persistent entity is introduced.
- **Active Baby Profile**: The currently selected baby for the authenticated user, including the date of birth used to derive age at request time. Already exists; this feature only reads it.
- **Source Citation**: A `(title, url)` pair returned to the client representing one page the synthesized answer drew from. Not independently persisted as an entity beyond being part of the conversation turn's stored payload.
- **Source Policy** (configuration, not a runtime entity): The maintained allow-list/block-list of domains used to filter raw web search results before they become citations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of accepted research submissions, the response is generated from real web search results (zero responses contain the legacy "(Research placeholder)" string or the legacy static three-source list).
- **SC-002**: When the same research question is asked for two babies more than 12 months apart in age on the same account, at least 90% of question pairs produce responses with materially different agent text (measured by manual rubric: "would a caregiver perceive these as age-appropriate to different ages?").
- **SC-003**: When a context-dependent follow-up (e.g. pronoun reference, "what about at night?", "and the older one?") is sent after a prior turn in the same session, at least 90% of follow-ups are interpreted in the prior turn's topical context (measured against a fixed evaluation set of paired turns).
- **SC-004**: At least 80% of source URLs returned across a 50-question evaluation set come from the trusted-domain allow-list; zero responses contain a source URL that returns 404 or redirects to an unrelated parked/spam domain.
- **SC-005**: When the web search backend is forced offline in a controlled test, 100% of research submissions return a graceful "research unavailable" HTTP 200 response with an empty `sources` array — zero 5xx responses surfaced to the client.
- **SC-006**: A caregiver can submit a research question and read an actionable, age-appropriate, source-cited answer end-to-end in under 10 seconds at the median (p50) for typical questions, including search and synthesis.
- **SC-007**: Zero pieces of PII from the caregiver's message body (baby name, full date of birth, contact info) appear in either the external web search query or in server logs, verified by an automated redaction check over a representative sample of requests.
- **SC-008**: 100% of successful research responses include the standard not-medical-advice reminder in the `agent_message`, with consistent wording across responses, verified by automated assertion over an evaluation set.
- **SC-009**: On a fixed evaluation set, at least 95% of clearly off-topic questions are scope-refused (FR-021), 100% of clearly harmful baby-related prompts are safety-refused (FR-021), and false-positive refusals on legitimate baby-care questions remain below 5%.

## Assumptions

- The existing chat session store (per `specs/003-chat-session-store/` and the Postgres baseline introduced by `specs/009-postgres-migration/`) is the persistence layer for research conversation context. No new database table is introduced by this feature.
- The existing active-baby selection mechanism (per `specs/006-user-and-baby-profiles/`) already supplies an `ActiveBabyDep` with the baby's date of birth, and that date of birth is recorded as an ISO date string at registration. This feature reads it but does not modify the baby profile contract.
- The existing frontend Research mode (`frontend/src/features/chat/ChatPanel.tsx`, `useChat.ts`) already sends the question and `X-Session-ID`, and already renders `agent_message` plus the `sources` list. No frontend changes are required for the existing UI to surface this feature's improvements.
- The existing static research-mode disclaimer banner in the UI is preserved and is NOT a substitute for the in-text reminder required by FR-015 on health-related questions.
- A web search capability (third-party search API or an internal equivalent) will be available to the backend; selecting which specific search provider is an implementation choice and is out of scope for this spec.
- "Reputable sources" is operationalized by a maintained domain allow-list/block-list owned alongside the implementation; the exact initial domain list is an implementation detail and is expected to evolve.
- Performance target SC-006 (p50 < 10s) assumes a typical question and a single search backend round-trip; pathological queries or backend cold starts may exceed this without violating the spec, as long as the graceful-failure path (FR-014) still applies past the 15-second web-search timeout. The 15s cap bounds only the external search call; subsequent answer synthesis adds its own latency on top, which is acceptable because the failure-mode UX (FR-014) is reserved for the search-backend leg specifically.
- Conversation-context window size is whatever the existing session store currently exposes for the diary chat; this feature does not introduce a different window for research.
- Research turns continue to be ephemeral with respect to the diary: nothing in this feature writes feed/sleep/poop/appointment entries, and the diary chat surface is unaffected.
