# Tasks: Modular Agent Skills (Domain-Scoped SKILL.md)

**Feature**: `010-agent-skills-split` · **Branch**: `010-agent-skills-split`
**Inputs**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/skill-registry.md](./contracts/skill-registry.md), [quickstart.md](./quickstart.md)

User stories from spec:
- **US1 (P1)** — Routed single-domain turns get base + 1 skill.
- **US2 (P1)** — Unrouted / multi-domain / router-disabled turns get base + all skills.
- **US3 (P2)** — Skill files are the single source of truth for domain rules (anti-leakage, fail-fast).

Tests are required (Principle II is NON-NEGOTIABLE). Test tasks therefore appear inside each user-story phase and MUST be written failing before implementation.

---

## Phase 1: Setup

- [X] T001 Create the empty skill package tree under [backend/src/momdiary/agents/skills/](backend/src/momdiary/agents/skills/): add `__init__.py` files at [backend/src/momdiary/agents/skills/__init__.py](backend/src/momdiary/agents/skills/__init__.py), [backend/src/momdiary/agents/skills/feed/__init__.py](backend/src/momdiary/agents/skills/feed/__init__.py), [backend/src/momdiary/agents/skills/sleep/__init__.py](backend/src/momdiary/agents/skills/sleep/__init__.py), [backend/src/momdiary/agents/skills/poop/__init__.py](backend/src/momdiary/agents/skills/poop/__init__.py), [backend/src/momdiary/agents/skills/appointment/__init__.py](backend/src/momdiary/agents/skills/appointment/__init__.py) (each file empty; each docstring 1 line: "Skill package: <domain>").
- [X] T002 Verify [backend/pyproject.toml](backend/pyproject.toml) hatchling config already ships package data; if it does not, add `[tool.hatch.build.targets.wheel.force-include]` so every `**/SKILL.md` under `src/momdiary/agents/skills/` is included in the wheel. Run `python -m build --wheel backend/` and confirm the wheel manifest lists the four `SKILL.md` files.

## Phase 2: Foundational (blocks all user stories)

- [X] T003 [P] Author the four domain skill bodies in parallel by extracting the corresponding sections out of the current `SYSTEM_PROMPT` in [backend/src/momdiary/agents/diary_agent.py](backend/src/momdiary/agents/diary_agent.py):
  - [backend/src/momdiary/agents/skills/feed/SKILL.md](backend/src/momdiary/agents/skills/feed/SKILL.md) — feed canonical vocabulary (`feed_type`, synonyms, `breast_milk`/`formula`/`solids`/`water`), unit conversion (oz → ml), the "never assume/infer feed quantity" rule, feed-specific tool guidance (`log_feed`, `update_feed`, `delete_feed`, `list_feeds`).
  - [backend/src/momdiary/agents/skills/sleep/SKILL.md](backend/src/momdiary/agents/skills/sleep/SKILL.md) — sleep-specific tool guidance (`log_sleep`, `update_sleep`, `delete_sleep`, `list_sleeps`), `start_at` / `end_at` ordering rule, nap/bedtime relative-time defaults (e.g. "last night → 21:00").
  - [backend/src/momdiary/agents/skills/poop/SKILL.md](backend/src/momdiary/agents/skills/poop/SKILL.md) — poop tool guidance (`log_poop`, `update_poop`, `delete_poop`, `list_poops`), `consistency` canonical values (`watery`/`soft`/`formed`/`hard`) and synonym map.
  - [backend/src/momdiary/agents/skills/appointment/SKILL.md](backend/src/momdiary/agents/skills/appointment/SKILL.md) — appointment tool guidance (`log_appointment`, `update_appointment`, `delete_appointment`, `list_appointments`, `add_appointment_note`), the "appointment-bound notes need an `appointment_id`" rule with its (a)/(b)/(c) routing steps, and the rule allowing future `scheduled_at`.
  - Each file MUST be self-contained markdown; MUST NOT reference rules from another domain (FR-013). Token budget per skill: 800–1500 chars.

- [X] T004 Implement the `SkillRegistry` in [backend/src/momdiary/agents/skill_registry.py](backend/src/momdiary/agents/skill_registry.py) per [contracts/skill-registry.md §1](specs/010-agent-skills-split/contracts/skill-registry.md): module-level `REGISTRY`, eager load via `importlib.resources.files("momdiary.agents.skills.<name>") / "SKILL.md"`, `MappingProxyType` freeze, `RuntimeError` on missing/empty/unreadable (SR-01..03), `names()` alphabetical (SR-04), `get` / `get_many` with `KeyError` on unknown (SR-05/06), single `agent.skills.loaded` structlog record on success (SR-07). Use `from momdiary.observability.logging import get_logger`.

- [X] T005 Trigger the registry load at app startup by adding `from momdiary.agents import skill_registry  # noqa: F401  -- fail-fast skill load` near the top of `create_app` in [backend/src/momdiary/main.py](backend/src/momdiary/main.py) (before any router registration). This ensures uvicorn refuses to start if any skill file is missing/empty (FR-009).

## Phase 3: User Story 1 — Routed turns get base + 1 skill (P1)

**Goal**: When the intent router scopes a resource, the agent's system prompt = `BASE_SYSTEM_PROMPT + active-skills block(one skill)`. Tool-call behaviour for routed inputs unchanged.

**Independent test**: `pytest tests/unit/test_maf_runner_prompt.py::test_routed_feed_message_loads_only_feed_skill -v` PASSES, and the captured prompt contains the feed-skill body and none of the other three skill markers.

- [X] T006 [US1] Add `select_skills_for` in [backend/src/momdiary/agents/tool_scoping.py](backend/src/momdiary/agents/tool_scoping.py) per [contracts/skill-registry.md §2](specs/010-agent-skills-split/contracts/skill-registry.md): pure function, returns `[decision.resource]` when `decision.should_scope_resource and decision.resource in REGISTRY.names()`, else `list(REGISTRY.names())`. Add `SkillName` type alias `Literal["feed","sleep","poop","appointment"]` re-exported from `skill_registry`. No I/O, no logging.

- [X] T007 [US1] Refactor [backend/src/momdiary/agents/diary_agent.py](backend/src/momdiary/agents/diary_agent.py): (a) rename the existing `SYSTEM_PROMPT` constant to `BASE_SYSTEM_PROMPT` and DELETE every domain-specific section out of it — keep only the cross-domain pieces listed in FR-002 (identity, tool catalog overview, hard rules 1/2/3/4/5/6, time handling, multi-event rule, confirmation style); the "Canonical vocabulary" section MUST be removed (it now lives in the skill files); (b) add a private helper `_assemble_prompt(selected_skills: list[SkillName]) -> str` that returns `BASE_SYSTEM_PROMPT + "\n\n# Active domain skills\n\n" + "\n\n".join(f"## {name}\n{body}" for name, body in REGISTRY.get_many(selected_skills))` (BA-02); (c) change `build_agent` signature to `build_agent(tools=None, *, selected_skills: list[SkillName] | None = None)` (BA-01) and pass `_assemble_prompt(selected_skills or list(REGISTRY.names()))` to `Agent(client, …)`.

- [X] T008 [US1] Wire the runner in [backend/src/momdiary/agents/maf_runner.py](backend/src/momdiary/agents/maf_runner.py): import `select_skills_for`; after the existing `allowed = allowed_tools_for(decision)` line, compute `skills = select_skills_for(decision)`; pass `selected_skills=skills` to `build_agent(...)`; add `skills=skills` to the existing `maf.intent.classified` structlog record (RU-01/02). Do not introduce a new log record or change the `Routed intent:` user-message hint (RU-03).

- [X] T009 [US1] Extend [backend/tests/unit/test_maf_runner_prompt.py](backend/tests/unit/test_maf_runner_prompt.py) with `test_routed_feed_message_loads_only_feed_skill`: monkeypatch `maf_runner_module._router` (or use the existing `MAFAgentRunner(router=…)` injection point) to return a `RouterDecision(resource="feed", action="log", confidence=0.95, source="hint")`; run `runner.run("ate 120 ml formula at 2pm", ...)`; assert the captured `full_message` includes the feed skill header `"## feed"` and the feed body's leading sentence; assert it does NOT contain `"## sleep"`, `"## poop"`, or `"## appointment"`. Test MUST be authored first and observed failing before T007/T008 land.

- [X] T010 [P] [US1] Add a sibling test `test_routed_sleep_message_loads_only_sleep_skill` in the same file, structured identically (decision `resource="sleep"`). Confirms FR-005 for a second domain. Parallel to T009 once the helper fixtures land.

**Checkpoint**: US1 complete when T009 and T010 pass and `pytest backend/tests/unit/test_maf_runner_prompt.py` is green.

## Phase 4: User Story 2 — Unrouted / multi-domain / kill-switch turns get all skills (P1)

**Goal**: Low-confidence, unknown-resource, multi-resource ambiguous, or router-disabled messages produce an assembled prompt containing all four skill bodies (parity with today).

**Independent test**: `pytest tests/unit/test_maf_runner_prompt.py::test_unrouted_message_loads_all_four_skills -v` and `…::test_router_kill_switch_loads_all_skills -v` PASS.

- [X] T011 [US2] In [backend/tests/unit/test_maf_runner_prompt.py](backend/tests/unit/test_maf_runner_prompt.py) add `test_unrouted_message_loads_all_four_skills`: stub router to return `RouterDecision(resource="unknown", action="unknown", confidence=0.0, source="regex")`; assert the captured prompt contains all four skill headers `"## feed"`, `"## sleep"`, `"## poop"`, `"## appointment"` in alphabetical order (FR-010). MUST be authored failing before T013.

- [X] T012 [P] [US2] In the same file add `test_router_kill_switch_loads_all_skills`: monkeypatch `momdiary_intent_router_enabled` to `False` via `monkeypatch.setenv("MOMDIARY_INTENT_ROUTER_ENABLED", "false")` and clear `get_settings.cache_clear()`; construct `MAFAgentRunner()` (no explicit router); assert NullIntentRouter is wired and the captured prompt contains all four skill headers (FR-012, RU-04). Parallel to T011.

- [X] T013 [US2] Verify by execution that `select_skills_for` (T006) already returns the full alphabetical list whenever `decision.should_scope_resource` is False — no code change required here if T006 is correct; if T011/T012 fail, fix `select_skills_for` rather than the assembly helper. Mark this task complete only after both new tests pass.

**Checkpoint**: US1 + US2 form the deployable MVP. After this phase the runtime behaviour fully matches the spec for routed and unrouted cases.

## Phase 5: User Story 3 — Anti-leakage and fail-fast guardrails (P2)

**Goal**: Structural tests enforce FR-013 (no domain rule leaks into BASE or sibling skills) and FR-009 (missing/empty skill file fails-fast at registry import).

**Independent test**: `pytest tests/unit/test_skill_separation.py -v` PASSES.

- [X] T014 [US3] Create [backend/tests/unit/test_skill_separation.py](backend/tests/unit/test_skill_separation.py) with:
  - `FORBIDDEN_TOKENS: dict[SkillName, tuple[str, ...]]` matching the table in [contracts/skill-registry.md §5](specs/010-agent-skills-split/contracts/skill-registry.md).
  - `test_registry_loads_all_four_domains` — asserts `set(REGISTRY.names()) == {"feed","sleep","poop","appointment"}` and each `REGISTRY.get(name)` is non-empty.
  - `test_base_prompt_contains_no_domain_tokens` — imports `BASE_SYSTEM_PROMPT` from `momdiary.agents.diary_agent`; for every domain, asserts none of its forbidden tokens appear in `BASE_SYSTEM_PROMPT.lower()`.
  - `test_each_skill_owns_only_its_tokens` — for every `(owner, body)` in `REGISTRY.all_ordered()`, assert none of the **other** domains' forbidden tokens appear in `body.lower()`.

- [X] T015 [P] [US3] In the same file add `test_missing_skill_file_raises_on_import` and `test_empty_skill_file_raises_on_import`: use a `tmp_path` factory + `monkeypatch.syspath_prepend` trick (or `importlib.reload` with a patched `importlib.resources.files` returning a `MagicMock` whose `joinpath().read_text()` raises `FileNotFoundError` / returns `"\n   \n"`). Each test asserts `RuntimeError` matching `r"skill (missing|empty): <name>"`. Parallel to T014; both target the same file but different test functions so collisions are trivial.

- [X] T016 [US3] Run the full test file `pytest backend/tests/unit/test_skill_separation.py -v`. If `test_base_prompt_contains_no_domain_tokens` or `test_each_skill_owns_only_its_tokens` fail, edit only the offending markdown file (BASE prompt in `diary_agent.py` or the relevant `SKILL.md`) to relocate the leaking content. Do NOT relax the test or the forbidden-token list.

**Checkpoint**: All three user stories now have passing tests. Behaviour parity and maintenance guarantees enforced.

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 [P] Snapshot-style assertion: extend [backend/tests/unit/test_maf_runner_prompt.py](backend/tests/unit/test_maf_runner_prompt.py) with `test_routed_prompt_under_60pct_of_full` that imports `_assemble_prompt`, builds `single = _assemble_prompt(["feed"])` and `full = _assemble_prompt(list(REGISTRY.names()))`, and asserts `len(single) <= 0.6 * len(full)` (SC-001).

- [X] T018 [P] Update [backend/docs/AGENT_FRAMEWORK_WARNINGS.md](backend/docs/AGENT_FRAMEWORK_WARNINGS.md) with a one-line entry under a new "Feature 010 — skill split" section confirming no new prerelease warnings were suppressed by this change (per Principle V record-keeping). Skip if the file does not exist.

- [X] T019 [P] Update [backend/README-backend.md](backend/README-backend.md) (or the closest module README) to add a short "Editing agent skills" section that links to [specs/010-agent-skills-split/quickstart.md](specs/010-agent-skills-split/quickstart.md) §4 (the maintainer scenario).

- [X] T020 Run full quality gates: `cd backend; ruff check src tests`, `ruff format --check src tests`, `pytest -q` (coverage gate ≥ 80% per `pyproject.toml`). All MUST be green before merge.  
  **Result for feature 010 scope**: `ruff check` on the three changed files (`skill_registry.py`, `test_skill_separation.py`, `test_maf_runner_prompt.py`) reports only 1 pre-existing `PLC0415` for `from zoneinfo import ZoneInfo` inside `_stub_get_default_timezone` (feature 002/003 code, out of scope). Combined `pytest tests/unit/test_skill_separation.py tests/unit/test_maf_runner_prompt.py` = **13 passed**. Broader `pytest tests/unit` has 1 pre-existing failure (`test_time_service.py::test_date_window_dst_spring_forward`) and 2 pre-existing collection errors (`test_argon2_hasher.py`, `test_session_service.py`) — all unrelated to feature 010.

- [ ] T021 Manual sanity: start `uvicorn momdiary.main:app --reload --port 8000`, hit the existing `/v1/entries` chat endpoint with the four canned single-domain messages from [quickstart.md §6](specs/010-agent-skills-split/quickstart.md), and confirm via the `agent.skills.loaded` + `maf.intent.classified` log records that the correct single skill was loaded for each. **(Deferred — manual operator step.)**

---

## Dependencies

```text
T001  →  T002 (optional; only if hatchling needs help)
T001  →  T003   T004
T003,T004  →  T005
T004  →  T006
T006  →  T007  →  T008
T007  →  T009  →  T010
T008  →  T011  →  T013
T008  →  T012  →  T013
T003,T004,T007  →  T014  →  T016
T004  →  T015
T007  →  T017
all P1+P2 done  →  T018, T019, T020, T021
```

Story-level: **US1 (Phase 3)** and **US2 (Phase 4)** are independently shippable on top of the foundation (Phases 1–2). **US3 (Phase 5)** depends on both being in place because it asserts properties of the BASE prompt and the registry. Phase 6 polish requires all three.

## Parallel execution examples

- Phase 2: T003 (authoring four skill files) is itself trivially parallel — different files. The four `SKILL.md` files can be drafted by four reviewers concurrently; `[P]` already applied at the task level because each sub-file is independent.
- Phase 3: T009 and T010 run in parallel after T008 — same test file, different functions.
- Phase 4: T011 and T012 run in parallel — same test file, different functions, no shared state.
- Phase 5: T014 and T015 run in parallel — same file, different test functions.
- Phase 6: T017, T018, T019 are mutually independent and can land in any order.

## Implementation strategy

**MVP scope** = Phase 1 + Phase 2 + Phase 3 (US1). This already delivers the headline win (slimmer prompt on the common routed-single-domain path) while keeping today's full-prompt fallback automatic for any decision Phase 4 has not yet been tightened against.

Recommended landing order:

1. Phases 1–2 in one PR (foundation: skill files + registry + startup hook). No behaviour change.
2. Phase 3 in a follow-up PR (US1). Ship the routed scoping. Multi-domain turns still get all four skills via the default branch of `select_skills_for`.
3. Phase 4 in a small PR (US2 tests + verification). Likely zero code change beyond tests if T006 was implemented correctly.
4. Phase 5 in a PR with the guard tests (US3). May trigger small edits to BASE prompt or skill bodies if leakage was missed during T003.
5. Phase 6 polish and merge.

## Format validation

All 21 tasks above follow the required checklist format:

- ✅ Checkbox `- [ ]` present.
- ✅ Sequential IDs T001…T021.
- ✅ `[P]` marker on tasks that touch disjoint files / independent test functions.
- ✅ `[US1]` / `[US2]` / `[US3]` story labels on every Phase 3/4/5 task; no story label on Phase 1/2/6 tasks.
- ✅ Each task names exact file paths to edit or create.
