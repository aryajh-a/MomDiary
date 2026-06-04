# Feature Specification: Modular Agent Skills (Domain-Scoped SKILL.md)

**Feature Branch**: `010-agent-skills-split`
**Created**: 2026-06-03
**Status**: Draft
**Input**: User description: "I want to move away from having huge prompt and use Skill.md with agent. Split system prompt to skills specific to feed, sleep, poop, appointment and keep common instructions in system prompts. Add skill.md to agent"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Domain-scoped routed turns get a smaller, targeted prompt (Priority: P1)

When the caregiver sends a message that the intent router classifies with high confidence as a single domain (feed, sleep, poop, or appointment), the agent receives ONLY the lean common system prompt plus the SKILL.md content for that one domain — instead of today's monolithic prompt that mixes all four domains together. The slimmer prompt must preserve every behavior the current monolithic prompt enforces for that domain (canonical vocabulary, quantity rules, time handling, candidate selection, etc.).

**Why this priority**: This is the core win the user is asking for. It shrinks per-turn prompt size on the common path, lowers token cost and latency, and makes per-domain instructions easier to evolve in isolation without risking regressions in the other domains.

**Independent Test**: Send a single-domain message (e.g. "she had 120 ml formula at 2pm") through the existing chat endpoint and capture the full prompt sent to the model. The captured prompt MUST contain the feed-domain skill content and MUST NOT contain sleep/poop/appointment-specific guidance. The resulting tool call MUST be identical (same tool, same arguments) to the call produced by the current monolithic prompt on the same input.

**Acceptance Scenarios**:

1. **Given** the intent router classifies a message as `resource=feed` above the scope threshold, **When** the agent runs, **Then** the assembled prompt contains the common base prompt + feed SKILL only, and no sleep/poop/appointment domain text.
2. **Given** the intent router classifies a message as `resource=sleep` above the scope threshold, **When** the agent runs, **Then** the assembled prompt contains the common base prompt + sleep SKILL only.
3. **Given** the same caregiver input that today produces tool call `log_feed(feed_type="formula", quantity=120, unit="ml", occurred_at=...)`, **When** routed through the new skill-scoped prompt, **Then** the produced tool call matches on tool name and all canonical fields.

---

### User Story 2 - Unrouted / multi-domain turns still get full coverage (Priority: P1)

When the intent router cannot confidently classify a message (low confidence, multi-domain message like "she ate at 2 and pooped at 3", or empty/unknown text), the agent MUST receive the common base prompt plus ALL four domain skills, so behavior degrades gracefully to today's full-prompt mode. No domain-specific instruction may be silently dropped on this path.

**Why this priority**: Without this guarantee, splitting the prompt would regress the multi-event and ambiguous-input cases the current prompt explicitly handles. Same priority as US1 because together they define the contract.

**Independent Test**: Send a message the regex router classifies as `unknown` or low-confidence multi-resource. Capture the prompt sent to the model and confirm content equivalence (semantically, not byte-for-byte) with today's monolithic prompt for the same input.

**Acceptance Scenarios**:

1. **Given** a message with no resource keywords, **When** the agent runs, **Then** the prompt includes all four domain skills.
2. **Given** a message matching two or more resource patterns with near-equal hit counts, **When** the agent runs, **Then** the prompt includes all four domain skills.
3. **Given** the intent router is disabled via the existing kill switch, **When** any message is processed, **Then** the prompt includes all four domain skills (same as today).

---

### User Story 3 - Skill files are the source of truth for domain rules (Priority: P2)

Each domain skill lives in its own `SKILL.md`-shaped file under the backend source tree (one per domain: feed, sleep, poop, appointment). A maintainer editing only `feed/SKILL.md` MUST be able to change feed-domain behavior (e.g. adjust the canonical `unit` list, refine the quantity-clarification rule) without touching the common prompt or any other domain skill. The common prompt MUST NOT duplicate any rule that exists in a domain skill.

**Why this priority**: This is the maintainability payoff that justifies the refactor. P2 because the runtime behavior (US1, US2) ships first; the file-layout discipline can be verified once US1/US2 land.

**Independent Test**: Open the four skill files and the common prompt side-by-side; verify no rule about feed canonical vocabulary appears anywhere except `feed/SKILL.md`, and same for the other three domains. Make a trivial edit to `poop/SKILL.md` (e.g. add a synonym mapping) and confirm only poop-domain turns reflect the change after restart.

**Acceptance Scenarios**:

1. **Given** the four domain skill files and the common base prompt, **When** a reviewer searches for the string `feed_type`, **Then** matches appear only in the feed skill file (and code), not in any other skill or the common prompt.
2. **Given** a one-line edit to `sleep/SKILL.md`, **When** the backend restarts, **Then** only sleep-routed turns observe the new wording in their assembled prompt; feed/poop/appointment turns are byte-identical to their pre-edit prompts.

---

### Edge Cases

- **Skill file missing or unreadable at startup**: the agent MUST fail fast at process start with a clear error, not at first request — partial domain coverage is worse than no server.
- **Intent router returns a resource the skill registry doesn't know about** (e.g. a future `medication` resource added to the router before its skill exists): the agent falls back to loading all currently-registered skills for that turn.
- **Hinted `entry_type` in the request envelope conflicts with a multi-domain message body** ("update feed #42" but the body also describes a poop): the hint wins (matches today's router behavior); only the feed skill is loaded.
- **Common prompt accidentally contains a domain rule after refactor**: caught by a structural test (US3 Acceptance Scenario 1) — the rule MUST be moved to the appropriate skill.
- **Skill file grows to include cross-domain guidance** (e.g. someone adds a time-handling note inside `feed/SKILL.md` that should live in the common base): caught by review against the common prompt's responsibility list; out-of-scope content in a skill is a defect.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent system prompt MUST be split into (a) one common base prompt that applies to every turn and (b) four domain-specific skill files, one each for feed, sleep, poop, and appointment.
- **FR-002**: The common base prompt MUST contain only cross-domain rules: tool-call-per-turn limits, the `ask_for_clarification` contract, time-handling rules, the entry-id authority rule, the multi-event message rule, the confirmation-style rule, and the high-level tool catalog. It MUST NOT contain any canonical vocabulary or domain-specific clarification rule that belongs to a single resource.
- **FR-003**: Each domain skill file MUST contain everything domain-specific that the current monolithic prompt enforces for that domain, including (where applicable) canonical field values, synonym normalization, unit conversion, quantity-clarification rules, appointment-note routing rules, and the resource-specific subset of read/write tools.
- **FR-004**: For every turn, the agent MUST be invoked with a system prompt assembled from the common base prompt plus exactly the set of domain skills selected for that turn (see FR-005, FR-006).
- **FR-005**: When the intent router's decision is high-confidence enough to scope the tool list (the existing `should_scope_resource` predicate), the agent MUST load only the skill for that resource.
- **FR-006**: When the intent router does NOT scope the tool list — including the low-confidence, unknown-resource, and router-disabled cases — the agent MUST load all four domain skills (parity with today's full prompt).
- **FR-007**: An `entry_type` hint in the request envelope MUST select that domain's skill alone (matches today's `HintIntentRouter` confidence=1.0 behavior).
- **FR-008**: Skill loading MUST happen once at process startup (skills are static files); per-turn assembly MUST be a cheap in-memory concatenation, not a disk read.
- **FR-009**: Missing, empty, or unreadable skill files MUST cause the process to fail at startup with a log message naming the offending file. The agent MUST NOT start with partial skill coverage.
- **FR-010**: When the assembled prompt is constructed, the order MUST be: common base prompt first, then domain skills in a deterministic order (e.g. alphabetical), so identical inputs produce byte-identical prompts across processes.
- **FR-011**: The set of behaviors observable through the existing chat surface MUST be preserved: every input that today produces a specific tool call MUST produce the same tool call (same tool name, same canonical fields) after the refactor, for at least the routed single-domain cases.
- **FR-012**: The existing intent-router kill switch (`momdiary_intent_router_enabled = false`) MUST continue to work and MUST cause all four skills to be loaded on every turn (FR-006).
- **FR-013**: The structural separation between the common prompt and each domain skill MUST be verifiable by an automated check that fails if a known domain-specific token (e.g. `feed_type`, `consistency`, `scheduled_at`, sleep `start_at`/`end_at` rule) appears in any file other than its owning skill.

### Key Entities

- **Common base prompt**: the static text used on every turn. Owns identity ("You are MomDiary..."), tool-call-per-turn contract, ask-for-clarification contract, time handling, entry-id authority, multi-event rule, confirmation style, and a high-level catalog of available tools.
- **Domain skill**: a named, self-contained block of instructions for one resource (feed, sleep, poop, or appointment). Each skill owns that resource's canonical vocabulary, synonym maps, unit handling, validation/clarification rules, and any resource-specific tool-usage notes.
- **Skill assembly**: the per-turn composition of the common prompt with the selected subset of domain skills, driven by the intent router's decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For routed single-domain turns (feed | sleep | poop | appointment with high-confidence routing), the assembled system prompt is at most 60% of the length (in characters) of today's monolithic prompt.
- **SC-002**: On a held-out replay of representative single-domain caregiver messages, the produced tool call (tool name + all canonical fields) matches the pre-refactor output on at least 95% of inputs.
- **SC-003**: For unrouted / multi-domain / router-disabled turns, the assembled prompt is semantically equivalent to today's monolithic prompt (no domain rule missing) — verified by the structural check in FR-013 finding zero leakage and a manual diff finding no omissions.
- **SC-004**: A maintainer can change a domain's rules by editing exactly one file (its `SKILL.md`) and no other prompt-bearing file, and the change is observable only on that domain's routed turns.
- **SC-005**: Process startup fails within 1 second when any of the four skill files is missing or empty, with a log entry naming the missing file.

## Assumptions

- The existing intent router (`HintIntentRouter` + `RegexIntentRouter` chain) and its confidence thresholds remain the source of truth for which skills to load. This feature does not change the router; it only changes what the runner does with the router's decision.
- Domain skills are static text shipped with the backend (no runtime fetching, no per-tenant overrides). Skills live in the backend source tree and ship in the same image.
- The four current domains (feed, sleep, poop, appointment) are exhaustive for this refactor. Adding a fifth domain later is an additive change — out of scope here.
- "SKILL.md" is used as the conceptual shape (markdown-formatted, single-domain, self-contained); the exact filenames/locations are an implementation concern resolved in `/speckit.plan`.
- The existing routed-hint line the runner already injects ("Routed intent: resource=…") stays as-is and is independent of the skill content.
- Behavior parity is judged against the current `SYSTEM_PROMPT` in `backend/src/momdiary/agents/diary_agent.py` and the current tool-scoping logic in `backend/src/momdiary/agents/maf_runner.py`.
- The existing test that captures the `full_message` passed to the agent (`tests/unit/test_maf_runner_prompt.py`) is the obvious place to add prompt-composition assertions; concrete test layout is an implementation concern.
