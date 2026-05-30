# Prompt-quality evals (Tier 1)

This directory contains a small, env-gated eval suite that runs the **real**
`MAFAgentRunner` against a JSONL dataset of caregiver utterances and checks
that the model picks the correct tool with correct arguments.

## Why a separate directory?
The tests under `tests/integration/` use a `ScriptedAgent` that bypasses the
LLM — they verify plumbing, not prompt quality. The evals here actually hit
Azure OpenAI, so they are slow, cost real tokens, and are skipped by default.

## Running

```powershell
$env:MOMDIARY_RUN_EVALS='1'
pytest backend/tests/evals -v
$env:MOMDIARY_RUN_EVALS=''
```

A JSON report is written under `backend/eval-reports/eval-<timestamp>.json`
with pass-rates broken down by category and by expected tool. Diff two runs
to see how a prompt change moved the numbers.

## Datasets

| File | Rows | Purpose |
|---|---|---|
| `datasets/tool_routing.jsonl` | seed | Tool selection + arg extraction |

Each row supports:

- `id` — stable identifier (used as the pytest parametrize id).
- `utterance` — the caregiver message.
- `expected_tool` — the tool the model should pick (use `ask_for_clarification` for ambiguous inputs).
- `expected_tool_not_in` — list of tools the model must NOT pick (safety / prompt-injection rows).
- `expected_args` — optional dict; each key/value must match the persisted entry payload exactly.
- `category` — free-form bucket used for per-category pass-rate aggregation.
- `notes` — human note, ignored by the runner.

## Adding rows

Append to the JSONL file. Keep one JSON object per line; comments (`#`-prefixed lines) and blank lines are ignored. Use the existing IDs as a guide (`<resource>.<scenario>.<variant>`).

## Next steps (Tier 2)

When this directory grows past ~50 rows or you want LLM-as-judge scoring on
`agent_message` text, layer `azure-ai-evaluation`'s `ToolCallAccuracyEvaluator`
and `IntentResolutionEvaluator` on top of the same dataset.
