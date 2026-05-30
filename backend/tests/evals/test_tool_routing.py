"""Tool-selection eval — exercises the real MAFAgentRunner against a JSONL
dataset of caregiver utterances and asserts the model picks the right tool.

Run locally:

    $env:MOMDIARY_RUN_EVALS='1'
    pytest backend/tests/evals/test_tool_routing.py -v

A JSON report is written under `backend/eval-reports/` so you can diff
results across prompt iterations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.maf_runner import MAFAgentRunner

from .conftest import load_jsonl, record_result

DATASET = load_jsonl("tool_routing.jsonl")

logger = logging.getLogger("momdiary.evals.tool_routing")


def _row_id(row: dict[str, Any]) -> str:
    return row.get("id", row["utterance"][:40])


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _emit(lines: list[str]) -> None:
    """Print to stdout (visible with `pytest -s`) and log at INFO
    (visible with `--log-cli-level=INFO`). Belt-and-braces so the eval
    output shows up regardless of how the suite is invoked."""
    block = "\n".join(lines)
    print("\n" + block, flush=True)
    logger.info("\n%s", block)


@pytest.mark.asyncio
@pytest.mark.parametrize("row", DATASET, ids=[_row_id(r) for r in DATASET])
async def test_tool_routing(
    row: dict[str, Any],
    real_agent: MAFAgentRunner,
    eval_session: AsyncSession,
) -> None:
    utterance: str = row["utterance"]
    expected_tool: str | None = row.get("expected_tool")
    expected_args: dict[str, Any] = row.get("expected_args") or {}
    forbidden_tools: list[str] = row.get("expected_tool_not_in") or []
    category = row.get("category", "uncategorized")
    rid = _row_id(row)

    _emit(
        [
            "=" * 72,
            f"[eval IN ] id={rid}  category={category}",
            f"[eval IN ] utterance: {utterance!r}",
            f"[eval IN ] expected_tool={expected_tool!r}  "
            f"forbidden={forbidden_tools!r}",
            f"[eval IN ] expected_args={_dump(expected_args)}",
        ]
    )

    result = await real_agent.run(
        utterance,
        session=eval_session,
        correlation_id=f"eval-{rid}",
        history=[],
    )
    selected = result.selected_tool
    payload = result.payload or {}

    _emit(
        [
            f"[eval OUT] selected_tool={selected!r}  outcome={result.outcome!r}",
            f"[eval OUT] entry_type={result.entry_type!r}  "
            f"entry_id={result.entry_id!r}  unchanged={result.unchanged!r}",
            f"[eval OUT] agent_message: {result.agent_message!r}",
            f"[eval OUT] payload: {_dump(payload)}",
            f"[eval OUT] suggested_candidates: "
            f"{_dump(result.suggested_candidates)}",
        ]
    )

    # --- check 1: tool selection ------------------------------------------
    tool_ok = True
    if expected_tool is not None:
        tool_ok = selected == expected_tool
    if forbidden_tools:
        tool_ok = tool_ok and selected not in forbidden_tools

    # --- check 2: argument subset match (only for write outcomes) ---------
    args_ok = True
    arg_diffs: dict[str, dict[str, Any]] = {}
    if expected_args and payload:
        for key, want in expected_args.items():
            got = payload.get(key)
            if got != want:
                args_ok = False
                arg_diffs[key] = {"expected": want, "actual": got}

    passed = tool_ok and args_ok

    _emit(
        [
            f"[eval CHK] tool_ok={tool_ok}  args_ok={args_ok}  "
            f"passed={passed}",
            f"[eval CHK] arg_diffs: {_dump(arg_diffs)}" if arg_diffs
            else "[eval CHK] arg_diffs: (none)",
            f"[eval RES] {'PASS' if passed else 'FAIL'} :: {rid}",
            "=" * 72,
        ]
    )

    record_result(
        {
            "id": rid,
            "category": category,
            "utterance": utterance,
            "expected_tool": expected_tool,
            "selected_tool": selected,
            "outcome": result.outcome,
            "tool_ok": tool_ok,
            "args_ok": args_ok,
            "arg_diffs": arg_diffs,
            "agent_message": result.agent_message,
            "passed": passed,
        }
    )

    # Soft failure: each row is its own pytest case, so an `assert` here
    # gives us per-row red/green in the terminal. The JSON report still
    # captures the full picture for whichever rows failed.
    assert tool_ok, (
        f"tool routing miss: expected={expected_tool!r}, "
        f"got={selected!r}; utterance={utterance!r}"
    )
    assert args_ok, f"arg mismatch: {arg_diffs}; utterance={utterance!r}"
