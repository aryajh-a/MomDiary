# Implementation Plan: Modular Agent Skills (Domain-Scoped SKILL.md)

**Branch**: `010-agent-skills-split` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-agent-skills-split/spec.md`

## Summary

Split today's monolithic `SYSTEM_PROMPT` (in `backend/src/momdiary/agents/diary_agent.py`) into:

1. A lean **common base prompt** containing only cross-domain rules (identity, one-tool-per-turn contract, `ask_for_clarification`, time handling, entry-id authority, multi-event rule, confirmation style, tool catalog overview).
2. Four **domain skill files** — `feed/SKILL.md`, `sleep/SKILL.md`, `poop/SKILL.md`, `appointment/SKILL.md` — each owning that domain's canonical vocabulary, synonym maps, unit conversion, clarification rules, and tool-usage notes.

Per turn, the runner consults the existing intent router and assembles `BASE + selected_skills`:

- Router scopes resource (high confidence or `entry_type` hint) → load **one** skill.
- Router cannot scope (low confidence, multi-domain, router disabled) → load **all four** skills (today's behaviour).

Skills are loaded **once at process startup** via a `SkillRegistry` and assembled in-memory per turn (no per-request disk I/O). Missing/empty skill files fail-fast at import.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged)
**Primary Dependencies**: Microsoft Agent Framework (`agent-framework-core==1.0.0rc6`, `agent-framework-azure-ai==1.0.0rc6`); no new third-party deps.
**Storage**: N/A — skill files are static markdown shipped in the wheel.
**Testing**: `pytest` + `pytest-asyncio` (existing). New deterministic tests; no live-model calls.
**Target Platform**: Linux container (Azure App Service), same as today.
**Project Type**: web-service (backend only — frontend unaffected).
**Performance Goals**: Per-turn prompt-assembly overhead < 100 µs (string concatenation of pre-loaded buffers). Routed single-domain prompt size ≤ 60% of today's monolithic prompt (SC-001).
**Constraints**: Behavior parity required — same caregiver input must produce the same tool call for routed single-domain turns (SC-002). No new runtime dependency. No change to intent router thresholds or kill-switch semantics.
**Scale/Scope**: 4 domain skills; ~1 markdown file each (300–800 chars typical); single Python module (`SkillRegistry`); edits in 3 existing modules (`diary_agent.py`, `maf_runner.py`, one new test file + extension of `test_maf_runner_prompt.py`).

## Constitution Check

| Principle | How this plan satisfies it |
| --- | --- |
| **I. Code Quality & Maintainability** | Single-responsibility `SkillRegistry` module; `BASE_SYSTEM_PROMPT` is the only prompt-bearing constant in `diary_agent.py`; skill files are self-documenting markdown. No `TODO`s, dead code, or duplicated rules between files (FR-013 enforces this). |
| **II. Testing Standards (NON-NEGOTIABLE)** | New unit tests written first: (a) prompt-composition test extends `test_maf_runner_prompt.py` to assert routed prompt contains only the relevant skill; (b) new `test_skill_separation.py` asserts no domain leakage and fail-fast on missing file. Contract test (existing `test_maf_runner_prompt.py`) updated. All tests deterministic; `build_agent` already stubbed by tests. Coverage floor preserved (only adding tests, removing no logic). |
| **III. Performance Requirements** | Per-turn assembly is two string concatenations over pre-loaded buffers — negligible. Routed single-domain prompts shrink (smaller prompt → fewer prompt tokens → lower latency/cost). No new caches or unbounded state. No hot-path benchmark regression expected; existing `tests/benchmarks/` are untouched. |
| **IV. Modular Architecture** | New `SkillRegistry` module owns skill loading; `build_agent` accepts a `selected_skills` parameter (pluggable). `maf_runner` is the only caller that maps router decision → skill set. Skill files are pure data with no code dependency. No cyclic imports introduced (`SkillRegistry` depends on stdlib only; `diary_agent` depends on `SkillRegistry`; `maf_runner` depends on both). |
| **V. Microsoft Agent Framework First (NON-NEGOTIABLE)** | No framework swap. `build_agent` continues to construct a MAF `Agent` with the same `AzureOpenAIChatClient`. Pinned prerelease versions unchanged. No new warning suppressions. |

**Gate**: PASS — no violations, Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-agent-skills-split/
├── plan.md                # This file (/speckit.plan command output)
├── research.md            # Phase 0 output
├── data-model.md          # Phase 1 output (skill registry entities)
├── quickstart.md          # Phase 1 output (how to add/edit a skill)
├── contracts/
│   └── skill-registry.md  # Phase 1 output (SkillRegistry + build_agent contract)
├── spec.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── src/momdiary/
│   ├── agents/
│   │   ├── diary_agent.py            # MODIFIED: SYSTEM_PROMPT → BASE_SYSTEM_PROMPT;
│   │   │                             #           build_agent accepts selected_skills
│   │   ├── maf_runner.py             # MODIFIED: derive selected_skills from router
│   │   │                             #           decision, pass to build_agent
│   │   ├── skill_registry.py         # NEW: loads + caches skill files, fail-fast
│   │   └── skills/                   # NEW: domain skill files (markdown)
│   │       ├── __init__.py           # NEW: marks package; re-exports nothing
│   │       ├── appointment/SKILL.md  # NEW
│   │       ├── feed/SKILL.md         # NEW
│   │       ├── poop/SKILL.md         # NEW
│   │       └── sleep/SKILL.md        # NEW
│   └── main.py                       # MODIFIED: import skill_registry at startup
│                                     #           to trigger fail-fast load
└── tests/
    └── unit/
        ├── test_maf_runner_prompt.py # MODIFIED: assert routed prompt = base + 1 skill;
        │                             #           unrouted prompt = base + 4 skills
        └── test_skill_separation.py  # NEW: FR-013 anti-leakage + fail-fast tests
```

**Structure Decision**: Backend-only change inside the existing `backend/src/momdiary/agents/` package. Skill files live as a sibling sub-package `skills/` (one directory per domain, each containing a single `SKILL.md`). Shipped in the wheel by the existing `hatchling` `packages = ["src/momdiary"]` configuration; markdown files included because they live under a package containing an `__init__.py` (hatch include defaults). Frontend, database, alembic, and config are unchanged.

## Complexity Tracking

> No constitution violations; this section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _none_    | _n/a_      | _n/a_                                |
