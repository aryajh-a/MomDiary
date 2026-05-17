# Microsoft Agent Framework — Warning Suppressions

Per the **MomDiary Constitution**, Principle V (Microsoft Agent Framework
First, NON-NEGOTIABLE):

> Compiler and tooling warnings originating from Microsoft Agent Framework
> packages MUST be suppressed at the narrowest possible scope and
> documented in a single `AGENT_FRAMEWORK_WARNINGS.md`.
>
> Suppression of warnings from non-Microsoft-Agent-Framework libraries is
> PROHIBITED under this principle.

This file is the canonical record for MomDiary.

## Scope of suppression

Suppressions apply ONLY to modules whose dotted path begins with
`agent_framework` or `agent_framework_azure_ai`. They are enforced in two
places:

1. **`backend/pyproject.toml`** under `[tool.pytest.ini_options]`
   `filterwarnings` — applies during the test suite.
2. **`backend/src/momdiary/observability/logging.py`** — calls
   `warnings.filterwarnings("ignore", module=r"agent_framework.*")` at
   application startup.

## Suppressed categories (initial)

| Category                       | Origin module                | Reason                                                                 |
| ------------------------------ | ---------------------------- | ---------------------------------------------------------------------- |
| `DeprecationWarning`           | `agent_framework`            | Prerelease API churn; we track the latest preview and update on cadence. |
| `DeprecationWarning`           | `agent_framework_azure_ai`   | Same.                                                                  |
| `PendingDeprecationWarning`    | `agent_framework`            | Same.                                                                  |
| `PendingDeprecationWarning`    | `agent_framework_azure_ai`   | Same.                                                                  |
| `UserWarning`                  | `agent_framework`            | Preview-API notices; replace with narrower categories as MAF stabilizes its warning class hierarchy. |
| `UserWarning`                  | `agent_framework_azure_ai`   | Same.                                                                  |

## Resolved prerelease versions

Recorded per release for reproducibility (Principle V + Technology &
Dependency Constraints clause).

| Package                       | Version (filled at install time) | Date       |
| ----------------------------- | -------------------------------- | ---------- |
| `agent-framework`             | _(populate from `uv.lock`)_      | _(date)_   |
| `agent-framework-azure-ai`    | _(populate from `uv.lock`)_      | _(date)_   |

When upgrading, append a new row rather than editing existing ones.
