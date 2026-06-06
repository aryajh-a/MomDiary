# Contract: SkillRegistry + build_agent + select_skills_for

Date: 2026-06-03 · Feature: `010-agent-skills-split`

This document is the binding contract for the three new/changed surfaces
introduced by feature 010. Contract tests in
`backend/tests/unit/test_skill_separation.py` and
`backend/tests/unit/test_maf_runner_prompt.py` enforce each clause.

---

## 1. `SkillRegistry` (new, `backend/src/momdiary/agents/skill_registry.py`)

### Module surface

```python
SkillName = Literal["feed", "sleep", "poop", "appointment"]

class SkillRegistry:
    def names(self) -> tuple[SkillName, ...]: ...
    def get(self, name: SkillName) -> str: ...
    def get_many(
        self, names: Iterable[SkillName]
    ) -> list[tuple[SkillName, str]]: ...
    def all_ordered(self) -> list[tuple[SkillName, str]]: ...

REGISTRY: SkillRegistry  # module-level singleton, built at import time
```

### Clauses

| ID | Clause |
| --- | --- |
| SR-01 | Importing `momdiary.agents.skill_registry` MUST trigger eager load of all four `SKILL.md` files via `importlib.resources`. |
| SR-02 | If any of the four required skill files is missing, empty, or unreadable, import MUST raise `RuntimeError` with a message naming the offending skill. The error MUST be raised before `REGISTRY` becomes accessible. |
| SR-03 | After successful import, `REGISTRY` MUST be a `MappingProxyType`-backed object whose internal mapping cannot be mutated by callers. (Mutation attempts MUST raise `TypeError`.) |
| SR-04 | `REGISTRY.names()` MUST return the loaded skill names in alphabetical order; the return value MUST be the same on every call for the lifetime of the process. |
| SR-05 | `REGISTRY.get(name)` MUST return the exact stripped body of `<name>/SKILL.md`. It MUST raise `KeyError` for unknown names. |
| SR-06 | `REGISTRY.get_many(names)` MUST preserve caller-supplied order and MUST raise `KeyError` if any input name is unknown. |
| SR-07 | A single structured log record `agent.skills.loaded` MUST be emitted on successful load, containing `names` (list) and `byte_counts` (dict). |

---

## 2. `select_skills_for` (new, `backend/src/momdiary/agents/tool_scoping.py`)

### Signature

```python
def select_skills_for(decision: RouterDecision) -> list[SkillName]: ...
```

### Clauses

| ID | Clause |
| --- | --- |
| SS-01 | If `decision.should_scope_resource is True` AND `decision.resource in REGISTRY.names()`, the function MUST return `[decision.resource]`. |
| SS-02 | Otherwise the function MUST return `list(REGISTRY.names())` (all skills, alphabetical). |
| SS-03 | The function MUST be pure: no I/O, no logging, no mutation of `decision`. |
| SS-04 | The function MUST return a fresh list on each call (callers MUST be free to mutate the returned list without affecting the registry). |
| SS-05 | Behaviour MUST mirror `allowed_tools_for` for the unrouted/unknown cases: when `allowed_tools_for(decision)` returns `None` (full tool list), `select_skills_for(decision)` MUST return the full skill list. This invariant is asserted by a contract test. |

---

## 3. `build_agent` (modified, `backend/src/momdiary/agents/diary_agent.py`)

### Signature change

```python
# Before
def build_agent(tools: list[Any] | None = None) -> AgentBundle: ...

# After
def build_agent(
    tools: list[Any] | None = None,
    *,
    selected_skills: list[SkillName] | None = None,
) -> AgentBundle: ...
```

### Clauses

| ID | Clause |
| --- | --- |
| BA-01 | When `selected_skills is None`, `build_agent` MUST behave as if `selected_skills = list(REGISTRY.names())` (parity with today's full prompt). |
| BA-02 | The assembled system prompt MUST be exactly: `BASE_SYSTEM_PROMPT + "\n\n# Active domain skills\n\n" + "\n\n".join(f"## {name}\n{body}" for name, body in REGISTRY.get_many(selected_skills))`. |
| BA-03 | `BASE_SYSTEM_PROMPT` MUST NOT contain any of the curated domain-specific tokens listed in §5 below. Violation is a contract-test failure. |
| BA-04 | The full assembled prompt for routed single-domain turns MUST be ≤ 60% of the byte length of the legacy `SYSTEM_PROMPT` constant (SC-001). The contract test snapshots the legacy length and compares. |
| BA-05 | Identical `selected_skills` lists MUST produce byte-identical assembled prompts across processes (FR-010). |

---

## 4. `MAFAgentRunner.run` integration (modified, `backend/src/momdiary/agents/maf_runner.py`)

### Clauses

| ID | Clause |
| --- | --- |
| RU-01 | After classifying intent and computing `allowed = allowed_tools_for(decision)`, the runner MUST compute `skills = select_skills_for(decision)` and pass it as `build_agent(tools=tools, selected_skills=skills)`. |
| RU-02 | The existing `maf.intent.classified` log record MUST gain a `skills` field listing the selected skill names. No other log records are added or removed. |
| RU-03 | The existing `Routed intent:` hint line injected into the user message remains unchanged. |
| RU-04 | When the intent-router kill switch (`momdiary_intent_router_enabled = False`) is active, `NullIntentRouter` returns an `unknown` decision, `select_skills_for` returns all four skills, and the assembled prompt MUST therefore contain all four (FR-012). |

---

## 5. Forbidden-token table (FR-013 enforcement)

`BASE_SYSTEM_PROMPT` and each domain skill body MUST NOT contain tokens that
belong to other domains. Tokens are matched case-insensitively as substrings.
The contract test imports this list directly from
`tests/unit/test_skill_separation.py`.

| Domain | Forbidden in BASE and in other skills |
| --- | --- |
| `feed` | `feed_type`, `breast_milk`, `formula`, `ml`/`oz` conversion phrasing, `quantity must be a positive number` |
| `sleep` | `start_at`, `end_at`, `nap`, `sleeps` (as a list-tool name reference inside another skill) |
| `poop` | `consistency`, `watery`, `formed`, `soft` (consistency value), `hard` (consistency value) |
| `appointment` | `scheduled_at`, `add_appointment_note`, `appointment_id`, `appointment-bound notes` |

The high-level tool catalog in BASE may name tools (e.g.
`list_appointments(date?)`) without violating this rule because tool *names*
are not domain rules — only normative guidance about a domain's vocabulary
is forbidden. The contract test uses the curated substrings above (which
exclude bare tool names) to avoid false positives.

---

## 6. Backward-compatibility surface

- `build_agent(tools=…)` with no `selected_skills` MUST keep working
  (BA-01); no caller outside `maf_runner.py` is updated.
- The legacy `SYSTEM_PROMPT` symbol is renamed to `BASE_SYSTEM_PROMPT`. A
  one-line alias `SYSTEM_PROMPT = BASE_SYSTEM_PROMPT` is **NOT** added —
  there is exactly one caller in the codebase (`maf_runner.py` via
  `build_agent`) and one stub in tests; both are updated in the same PR.
- No public HTTP contract changes. No new env vars. No new Pydantic models.
