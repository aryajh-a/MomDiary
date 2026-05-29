"""Fixtures for the prompt-quality eval suite (Tier 1 — pytest only).

These tests exercise the *real* `MAFAgentRunner` against Azure OpenAI, so they
are gated behind the `MOMDIARY_RUN_EVALS=1` env var to keep PR CI fast and
offline. Enable locally with:

    $env:MOMDIARY_RUN_EVALS='1'
    pytest backend/tests/evals -v

The fixtures here intentionally re-use the integration-test scaffolding
(`configured_app`, `seed_caregiver`) so eval rows run against the same
migrations, repos, and active-baby context-var as the real app.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.maf_runner import MAFAgentRunner
from momdiary.auth.context import set_active_baby_id
from momdiary.db.engine import get_session_factory


def _evals_enabled() -> bool:
    return os.environ.get("MOMDIARY_RUN_EVALS", "").lower() in {"1", "true", "yes"}


# Skip the entire eval directory when the env flag isn't set.
collect_ignore_glob: list[str] = []
if not _evals_enabled():

    def pytest_collection_modifyitems(
        config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        skip = pytest.mark.skip(
            reason="Set MOMDIARY_RUN_EVALS=1 to run prompt-quality evals."
        )
        for item in items:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Real-agent fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_agent(
    configured_app: Any,
    seed_caregiver: Any,
) -> AsyncIterator[MAFAgentRunner]:
    """A real MAFAgentRunner bound to the test's ephemeral DB.

    Tools require an active baby; the `seed_caregiver` fixture creates one,
    we just bind it into the contextvar for the duration of the eval row.
    """
    set_active_baby_id(seed_caregiver.baby_id)
    runner = MAFAgentRunner()
    yield runner
    set_active_baby_id(None)


@pytest_asyncio.fixture
async def eval_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as s:
        yield s


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------


DATASETS_DIR = Path(__file__).parent / "datasets"


def load_jsonl(name: str) -> list[dict[str, Any]]:
    path = DATASETS_DIR / name
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"{path.name}:{lineno} — invalid JSON: {exc}"
                ) from exc
    return rows


# ---------------------------------------------------------------------------
# Per-run result reporter
# ---------------------------------------------------------------------------
# Every eval test appends a record to `eval_results`. After the session
# finishes we dump a single JSON file under `backend/eval-reports/` so we
# can diff prompt iterations.


_RESULTS: list[dict[str, Any]] = []


def record_result(record: dict[str, Any]) -> None:
    _RESULTS.append(record)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _evals_enabled() or not _RESULTS:
        return
    out_dir = Path(__file__).resolve().parents[2] / "eval-reports"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"eval-{stamp}.json"
    summary = {
        "generated_at": stamp,
        "total": len(_RESULTS),
        "passed": sum(1 for r in _RESULTS if r.get("passed")),
        "by_category": _summarize_by(_RESULTS, "category"),
        "by_expected_tool": _summarize_by(_RESULTS, "expected_tool"),
        "results": _RESULTS,
    }
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[evals] wrote {out_path}")


def _summarize_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        bucket = out.setdefault(
            str(r.get(key, "unknown")), {"total": 0, "passed": 0}
        )
        bucket["total"] += 1
        if r.get("passed"):
            bucket["passed"] += 1
    return out
