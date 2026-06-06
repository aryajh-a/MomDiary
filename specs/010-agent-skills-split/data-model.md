# Data Model — Modular Agent Skills

Date: 2026-06-03 · Feature: `010-agent-skills-split`

This feature introduces **no database tables, no Pydantic request/response
schemas, and no Alembic migrations**. The "entities" below are pure
in-process Python types used by the new `SkillRegistry` and by the
`build_agent` contract update.

---

## Entity: `SkillName`

- **Kind**: `Literal["feed", "sleep", "poop", "appointment"]`
- **Source of truth**: the set of subdirectory names under
  `backend/src/momdiary/agents/skills/`.
- **Validation**: at registry build time, the discovered directory set MUST
  equal `{"feed", "sleep", "poop", "appointment"}` exactly. A surplus
  directory (e.g. `medication/`) is allowed only if it also contains a
  `SKILL.md`; a missing required directory is a fatal error (FR-009).

---

## Entity: `Skill`

| Field | Type | Notes |
| --- | --- | --- |
| `name` | `SkillName` | Matches the owning subdirectory. |
| `body` | `str` | Stripped contents of `SKILL.md` (newline-normalized to `\n`). |
| `source_path` | `str` | `momdiary.agents.skills.<name>.SKILL.md` (informational; logged on load). |

**Invariants**:

- `body` is non-empty after stripping leading/trailing whitespace; empty bodies fail-fast at load (FR-009).
- `body` is treated as opaque markdown text — the registry does not parse or
  transform it.

---

## Entity: `SkillRegistry`

A read-only, process-global container. Constructed exactly once at first
import of `momdiary.agents.skill_registry`.

| Member | Signature | Behaviour |
| --- | --- | --- |
| `names()` | `() -> tuple[SkillName, ...]` | Returns the loaded skill names in alphabetical order. |
| `get(name)` | `(name: SkillName) -> str` | Returns the skill body. `KeyError` if the name is not registered. |
| `get_many(names)` | `(names: Iterable[SkillName]) -> list[tuple[SkillName, str]]` | Returns `(name, body)` pairs in input order. Used by `build_agent` to preserve the caller's chosen order. |
| `all_ordered()` | `() -> list[tuple[SkillName, str]]` | Convenience: `get_many(self.names())`. |

**Lifecycle**:

1. Module import — eager file reads via `importlib.resources.files()`.
2. Validation — non-empty bodies, exhaustive `SkillName` coverage.
3. Freeze — internal `dict` wrapped in `types.MappingProxyType` so callers
   cannot mutate the registry at runtime.
4. Logged once: `agent.skills.loaded` with `names=[…]` and per-skill byte
   counts.

**Failure modes** (all raised before `create_app` returns):

- `RuntimeError("skill missing: <name>")` — required subdirectory absent.
- `RuntimeError("skill empty: <name>")` — file exists but body is whitespace.
- `RuntimeError("skill unreadable: <name>: <os error>")` — I/O failure.

---

## Entity: `RouterDecision` (unchanged, referenced)

Already defined in `backend/src/momdiary/agents/intent_router.py`. This
feature only **reads** `decision.resource` and the existing
`decision.should_scope_resource` property; it does not modify the type.

---

## Pure function: `select_skills_for`

| Signature | `select_skills_for(decision: RouterDecision) -> list[SkillName]` |
| --- | --- |
| Lives in | `backend/src/momdiary/agents/tool_scoping.py` (sibling of `allowed_tools_for`). |
| Rule | If `decision.should_scope_resource` and `decision.resource` is a registered skill name, return `[decision.resource]`. Otherwise return the full alphabetical list from `SkillRegistry.names()`. |
| Determinism | Output depends only on `decision` and the (process-immutable) registry. Identical inputs → identical outputs across processes (FR-010). |

---

## Modified contract: `build_agent`

| Before | After |
| --- | --- |
| `build_agent(tools: list[Any] \| None = None) -> AgentBundle` | `build_agent(tools: list[Any] \| None = None, *, selected_skills: list[SkillName] \| None = None) -> AgentBundle` |

- When `selected_skills is None`, `build_agent` calls
  `SkillRegistry.names()` (all four) — preserves backward compatibility for
  any caller that hasn't been updated (today only `maf_runner.py` is a
  caller; the test stub `_FakeBundle` accepts arbitrary kwargs via
  `lambda tools=None, **_: ...`).
- Constructs the final system prompt: `BASE_SYSTEM_PROMPT + "\n\n# Active
  domain skills\n\n" + "\n\n".join(f"## {name}\n{body}" for name, body in
  registry.get_many(selected_skills))`.
- The function remains pure: no I/O, no caching beyond what the registry
  already provides.

---

## State transitions

None. Skills are loaded once at startup and never mutate. Per-turn behavior is a pure mapping `(decision, registry) → assembled_prompt`.
