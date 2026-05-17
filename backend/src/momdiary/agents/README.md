# MomDiary Diary Agent

This package owns the single Microsoft Agent Framework (MAF) agent that
mediates every write to the diary. The contract is defined in
[`specs/001-baby-tracker-backend/contracts/agent-tools.md`](../../../../specs/001-baby-tracker-backend/contracts/agent-tools.md);
this README is the developer-facing tour.

## Modules

- [`diary_agent.py`](diary_agent.py) — model client (`AzureOpenAIChatClient`
  via `DefaultAzureCredential`), `SYSTEM_PROMPT`, and `build_agent()`
  factory. Registers the full tool set from
  [`tools/registry.py`](tools/registry.py) by default.
- [`dispatcher.py`](dispatcher.py) — `AgentDispatcher` runs an `AgentRunner`,
  measures latency, and writes an `agent_interactions` audit row per
  invocation (FR-013, SC-002).
- [`maf_runner.py`](maf_runner.py) — adapter that satisfies the
  `AgentRunner` protocol with the live MAF agent. Scaffolded; not
  exercised in CI.
- [`tools/`](tools/) — pure async tool functions (`log_*`, `update_*`,
  `delete_*`, `add_appointment_note`). Each accepts an `AsyncSession`,
  validates its argument schema, calls a repository, and returns an
  `AgentRunResult`. Tools are registered on the agent via
  `tools.registry.TOOL_REGISTRY`.

## System-prompt invariants

The prompt in [`diary_agent.py`](diary_agent.py) enforces:

- **FR-002**: one tool per turn, never fabricate fields.
- **FR-011**: missing/ambiguous required fields ⇒ `ask_for_clarification`
  (no persistence).
- **FR-017**: explicit `(entry_id, entry_type)` in the envelope is
  authoritative; otherwise infer the target, and if ≥ 2 candidates match,
  clarify with the candidate list.
- **FR-018**: soft-deleted rows are invisible to resolution and to
  subsequent updates/deletes.

## Contract tests

- [`tests/contract/test_agent_tools_log.py`](../../../tests/contract/test_agent_tools_log.py) —
  `log_*` argument schemas.
- [`tests/contract/test_agent_tools_update_delete.py`](../../../tests/contract/test_agent_tools_update_delete.py) —
  `update_*`, `delete_*`, `add_appointment_note` argument schemas.
- [`tests/contract/test_openapi.py`](../../../tests/contract/test_openapi.py) —
  HTTP surface vs. `contracts/openapi.yaml`.

## Deterministic test agent

Integration tests do not call the live model. `tests/conftest.py` exposes
a `ScriptedAgent` that pops `(tool_name, kwargs)` pairs off a queue and
invokes them through `tools.registry.invoke_tool`. This means every
integration test exercises the real repositories and the real audit path.
