# MomDiary Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-27

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
- 008-clerk-auth: Added Python 3.12 (backend, unchanged), TypeScript 5.4 (frontend, unchanged).
- 007-profile-management: Added Python 3.12 (backend, unchanged surface area); TypeScript 5.4 (frontend)
- 006-user-and-baby-profiles: Added caregiver accounts (email + Argon2id-hashed password), rolling 30-day HttpOnly session cookies, single-owner baby profiles, and `baby_id NOT NULL` scoping on every existing diary endpoint. Chat session store repartitioned by `(user_id, baby_id, session_id)`. No new AI agent introduced.


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
