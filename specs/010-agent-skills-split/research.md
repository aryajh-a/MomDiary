# Phase 0 Research — Modular Agent Skills

Date: 2026-06-03 · Feature: `010-agent-skills-split`

## Unknowns extracted from Technical Context

The spec resolved all `NEEDS CLARIFICATION` items inline; this phase records the
small set of design decisions that close out implementation-shape ambiguity
before Phase 1.

---

## Decision 1 — Skill file location and packaging

**Decision**: Place skill files at
`backend/src/momdiary/agents/skills/<domain>/SKILL.md`, with each domain a
sub-package containing an `__init__.py` and one `SKILL.md`. Load them via
`importlib.resources.files("momdiary.agents.skills.<domain>") / "SKILL.md"`.

**Rationale**:

- `importlib.resources` is the Python 3.9+ stdlib-blessed way to read package
  data; works identically in a wheel (production) and a source checkout
  (dev/test). No path-hacking, no `__file__` arithmetic.
- Co-locating skills with the agent module keeps the contributor mental model
  obvious ("the agent's prompt fragments live next to the agent").
- Per-domain directory leaves room for adding companion assets later (e.g.
  `examples.jsonl`, `synonyms.yaml`) without restructuring.
- The current `hatchling` build config (`packages = ["src/momdiary"]`)
  already ships every file under that package tree into the wheel, so no
  `pyproject.toml` edit is required to deliver the markdown.

**Alternatives considered**:

- Repo-root `prompts/` directory — rejected: requires hatch `force-include`
  rules; encourages drift from the agent code; resource lookup needs an
  env-aware path resolver.
- Inline Python strings in `diary_agent.py` — rejected: defeats the whole
  point of US3 (one file per domain, edit independently).
- Single combined `skills.yaml` — rejected: not "SKILL.md" as the user
  requested; merges four domains back into one file at rest.

---

## Decision 2 — Loading strategy: eager at import-time, immutable thereafter

**Decision**: A module-level `SkillRegistry` instance is built at first
`import momdiary.agents.skill_registry`. The registry reads all four skill
files synchronously, validates each is non-empty (`stripped() != ""`), stores
the contents in a `frozendict`-shaped object (`MappingProxyType` over a
`dict[str, str]`), and exposes `get(name)`, `get_all_ordered()`, and
`names()`. Subsequent imports get the cached instance.

**Rationale**:

- Spec FR-008/FR-009: load once, fail fast. Import-time load surfaces missing
  files at process start (uvicorn refuses to come up), not at first chat
  request. Matches the existing engine-singleton pattern in
  `backend/src/momdiary/db/engine.py`.
- `MappingProxyType` makes the public surface read-only without dragging in a
  dependency.
- Synchronous I/O is fine because it happens exactly once per process and
  before the event loop starts (`main.py` imports during `create_app`).

**Alternatives considered**:

- Lazy first-request load — rejected: violates FR-009 (first request would
  catch the error, defeating fail-fast).
- Async load inside lifespan — rejected: skills are static disk reads of a
  few KB; async adds complexity for zero benefit and risks delaying the
  failure past the import barrier.

---

## Decision 3 — Skill-selection contract between router and runner

**Decision**: Add a pure function
`select_skills_for(decision: RouterDecision) -> list[str]` next to
`allowed_tools_for` in `backend/src/momdiary/agents/tool_scoping.py` (the
module that already owns `allowed_tools_for`). The function uses exactly the
same `should_scope_resource` predicate that drives tool scoping:

```text
if decision.should_scope_resource and decision.resource in REGISTRY.names():
    return [decision.resource]
return sorted(REGISTRY.names())  # alphabetical → deterministic
```

`maf_runner.py` calls `select_skills_for(decision)` and passes the result to
`build_agent(tools=..., selected_skills=...)`.

**Rationale**:

- One function, one rule: skill scoping mirrors tool scoping so the two
  cannot diverge. A future router change that flips `should_scope_resource`
  automatically updates both.
- Located alongside `allowed_tools_for` so reviewers see them together.
- Deterministic ordering (alphabetical sort of registry names) satisfies
  FR-010 (byte-identical prompts across processes for identical inputs).
- Unknown future resource (e.g. router returns `medication` before that
  skill exists) falls through the `in REGISTRY.names()` guard → all skills
  loaded (matches spec edge case).

**Alternatives considered**:

- Embed selection logic inside `maf_runner.run` — rejected: harder to unit
  test, harder to reuse if a future endpoint (e.g. eval harness) needs the
  same mapping.
- Have `SkillRegistry` know about routing — rejected: violates Principle IV
  (registry would import router types, creating a cycle).

---

## Decision 4 — Prompt assembly format

**Decision**: `build_agent` composes the final prompt as:

```text
<BASE_SYSTEM_PROMPT>

# Active domain skills

## <domain_1>
<skill_1 markdown body>

## <domain_2>
<skill_2 markdown body>
...
```

Skills are joined in the order returned by `select_skills_for` (already
sorted). The `# Active domain skills` header is emitted only when at least
one skill is selected (always true today, but guards a future zero-skill
case).

**Rationale**:

- One explicit boundary marker (`# Active domain skills`) so the model can
  visually parse where common rules end and domain rules begin.
- Per-skill `## <domain>` headers give the model an unambiguous anchor when
  the multi-skill (unrouted) case is in play.
- No JSON wrapper: keeps the prompt human-readable in logs.

**Alternatives considered**:

- Interleave skills inside the base (one section per topic) — rejected:
  reintroduces the maintenance burden the refactor is trying to remove.
- Use XML-style tags (`<skill name="feed">…</skill>`) — rejected: noisier in
  logs; markdown headers are sufficient for the gpt-4.1 deployment we use.

---

## Decision 5 — Test surface for FR-013 anti-leakage

**Decision**: Add `backend/tests/unit/test_skill_separation.py` with three
test functions:

1. `test_registry_loads_all_four_domains` — asserts the registry exposes
   exactly `{"feed", "sleep", "poop", "appointment"}` and each value is
   non-empty.
2. `test_base_prompt_contains_no_domain_tokens` — searches
   `BASE_SYSTEM_PROMPT` for a curated forbidden-token list per domain (e.g.
   feed: `feed_type`, `breast_milk`, `formula`, `quantity`, `oz`/`ml`
   conversion phrasing; sleep: `start_at`, `end_at`, `nap`; poop:
   `consistency`, `watery`, `formed`; appointment: `scheduled_at`,
   `add_appointment_note`, `appointment_id`).
3. `test_each_skill_owns_only_its_tokens` — for each domain skill, asserts
   the **other three** domains' forbidden tokens do not appear inside it.

Plus extension of `test_maf_runner_prompt.py`:

4. `test_routed_feed_message_loads_only_feed_skill` — stubs the router to
   return a high-confidence `feed` decision, captures `full_message`, and
   asserts feed skill content present and other three skill markers absent.
5. `test_unrouted_message_loads_all_four_skills` — stubs router to return
   `unknown`, asserts all four skill markers present.

**Rationale**:

- Curated forbidden-token lists are cheap to maintain and catch the realistic
  defect mode ("someone copy-pasted a rule into the wrong file"). They are
  not exhaustive AST analysis but they are exactly the FR-013 promise.
- Hooks into the existing stubbing pattern in `test_maf_runner_prompt.py`
  (`monkeypatch.setattr(maf_runner_module, "build_agent", ...)`) — no new
  test infrastructure.

**Alternatives considered**:

- LLM-based content review — rejected: non-deterministic, violates
  Principle II.
- Diff against a golden file — rejected: high churn; defeats the
  maintainability goal.

---

## Open Questions

None. All NEEDS CLARIFICATION items from the spec were resolved by the spec
itself; the decisions above are pure implementation-shape choices that do not
affect external behavior.
