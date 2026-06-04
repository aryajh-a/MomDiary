# MomDiary Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-06-05

## Active Technologies
- Python 3.12 + FastAPI, Microsoft Agent Framework (`agent-framework`, `agent-framework-azure-ai`, prerelease per constitution), `azure-identity`, SQLAlchemy 2.x (async) + `aiosqlite`, Alembic, Pydantic v2, `structlog` (or `python-json-logger`) (001-setup-environment)
- SQLite (local file via `sqlite+aiosqlite`), Alembic-managed schema (001-setup-environment)
- TypeScript 5.4 (frontend), Python 3.12 (existing backend, unchanged here) + React 18, Vite 5, TanStack Query v5, Tailwind CSS 3, `zod` (response validation), `date-fns` + `date-fns-tz` (local-time rendering) (002-tracker-ux-chat)
- None on the client (chat history is React state for the session; selected date is React state, not persisted) (002-tracker-ux-chat)
- Python 3.12 (backend, unchanged) + FastAPI, `agent-framework==1.0.0rc6`, `agent-framework-azure-ai==1.0.0rc6`, `azure-identity`, SQLAlchemy 2.x async, `pydantic` v2, `structlog` (003-chat-session-store)
- In-memory (Python dict in the FastAPI process). No SQLite/Alembic changes. The existing `momdiary.db` file is untouched. (003-chat-session-store)
- Python 3.12 (backend) + FastAPI, SQLAlchemy 2.x async + `aiosqlite`, Alembic, Pydantic v2, `structlog`, `argon2-cffi` (new). TypeScript 5.4 (frontend) + React 18, Vite 5, TanStack Query v5, Tailwind CSS 3, `zod`. (006-user-and-baby-profiles)
- SQLite (`backend/momdiary.db`); new tables `users`, `user_sessions`, `babies`; `baby_id NOT NULL` FK added to every existing diary table; pre-existing diary rows hard-deleted on migration. (006-user-and-baby-profiles)
- Python 3.12 (backend, unchanged surface area); TypeScript 5.4 (frontend) (007-profile-management)
- SQLite (`backend/momdiary.db`); no new tables, no new columns, no Alembic migration. (007-profile-management)
- Python 3.12 (backend, unchanged), TypeScript 5.4 (frontend, unchanged). (008-clerk-auth)
- SQLite (`backend/momdiary.db`) via `sqlite+aiosqlite`. One new Alembic revision (`2026XXXX_008_clerk_users.py`). (008-clerk-auth)
- Python 3.12 (backend) + FastAPI, SQLAlchemy 2.x async, Alembic, **asyncpg>=0.29** (replaces aiosqlite for runtime), Pydantic v2, `structlog` (009-postgres-migration)
- Azure Database for PostgreSQL Flexible Server (`legion.postgres.database.azure.com`) hosting both relational tables and `chat_sessions` JSONB; new Alembic baseline `0004_postgres_baseline.py`; legacy SQLite revisions retained as history only (009-postgres-migration)
- Python 3.12 (backend, unchanged); TypeScript 5.4 (frontend, unchanged for this feature) + FastAPI; `agent-framework-core==1.0.0rc6`; `agent-framework-azure-ai==1.0.0rc6` (Principle V — MAF-first, prerelease channel); `azure-identity`; `azure-ai-projects` (new — for `WebSearchTool` model + Foundry chat client surface); SQLAlchemy 2.x async; Pydantic v2; `structlog` (011-research-web-context)
- Azure Database for PostgreSQL Flexible Server (single datastore per feature 009). No new tables, no Alembic migration. Research turns reuse the existing `chat_sessions` JSONB row with an extended `ChatTurn` carrying an optional `sources: list[{title,url}]` field. (011-research-web-context)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.12: Follow project lint/format gates (ruff, black-compatible). TypeScript 5.4: project ESLint + Prettier.

## Recent Changes
- 011-research-web-context: Added Python 3.12 (backend, unchanged); TypeScript 5.4 (frontend, unchanged for this feature) + FastAPI; `agent-framework-core==1.0.0rc6`; `agent-framework-azure-ai==1.0.0rc6` (Principle V — MAF-first, prerelease channel); `azure-identity`; `azure-ai-projects` (new — for `WebSearchTool` model + Foundry chat client surface); SQLAlchemy 2.x async; Pydantic v2; `structlog`
- 009-postgres-migration: Switched backend storage from SQLite (aiosqlite) to Azure Postgres Flex via asyncpg; chat sessions now persist in a `chat_sessions` JSONB table with a background TTL sweeper (`pg_try_advisory_lock`).
- 008-clerk-auth: Added Python 3.12 (backend, unchanged), TypeScript 5.4 (frontend, unchanged).


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
