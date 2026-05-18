# Quickstart — MomDiary Tracker UX

This is the developer-facing onboarding for feature `002-tracker-ux-chat`. It assumes the backend from `001-baby-tracker-backend` is already runnable.

## Prerequisites

- Node.js 20 LTS (the LTS line current as of May 2026).
- pnpm 9 **or** npm 10. Examples below use `npm`; substitute `pnpm` freely.
- The backend prerequisites from [`specs/001-baby-tracker-backend/quickstart.md`](../001-baby-tracker-backend/quickstart.md): Python 3.12 venv, `az login`, migrations applied.

## One-time setup

```powershell
# From the repository root
cd frontend
npm install
```

Create `.env.local` (NOT committed):

```ini
VITE_API_BASE_URL=http://localhost:8000
```

On the **backend** side, enable CORS for the dev server. Open `backend/.env` and add:

```ini
MOMDIARY_ALLOWED_ORIGINS=http://localhost:5173
```

The backend's CORS middleware (added in this feature) reads that env var.

## Running both halves locally

In two terminals:

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn momdiary.main:create_app --factory --reload --port 8000
```

```powershell
# Terminal 2 — frontend
cd frontend
npm run dev
```

Open <http://localhost:5173>. You should see four sections (Feeds, Sleeps, Poops, Appointments), a date selector defaulting to today in your local timezone, and a persistent chat panel at the bottom of the viewport.

## Try a smoke flow

1. **List**: Pick today's date — every section should call its `GET /v1/{type}` endpoint and either show items or a type-specific empty state.
2. **Create via chat**: Type `120 ml breast milk just now` and click **Send**. The chat should show the assistant's confirmation, and the **Feeds** section should refresh within a couple of seconds to show the new entry.
3. **Clarify via chat**: Type `I fed the baby`. The assistant should respond with a clarifying question; nothing should appear in any section.
4. **Date navigation**: Move the date selector to yesterday. Every section refreshes.

## Tests

```powershell
cd frontend

# Unit + integration + contract — runs by default
npm test

# Watch mode while developing
npm run test:watch

# Playwright E2E smoke (boots a fresh backend with a temp SQLite under the hood)
npm run test:e2e
```

Default `npm test` does **not** start the backend. It uses MSW to stub `/v1/*` and contract fixtures committed under [`specs/002-tracker-ux-chat/contracts/samples/`](./contracts/samples/).

## Security note

In v1 there is **no per-user authentication** between the browser and the backend. The CORS allow-list (`http://localhost:5173`) is the only thing keeping arbitrary origins out. If you ever run the Vite dev server with `--host` exposing it on your LAN, anyone on the LAN can reach the backend. Don't do that until a follow-up feature adds Entra ID auth.

## File map (most relevant)

| Path | What it does |
|------|--------------|
| [frontend/src/App.tsx](../../frontend/src/App.tsx) | Layout shell — header, date bar, four sections, chat panel |
| [frontend/src/shared/apiClient.ts](../../frontend/src/shared/apiClient.ts) | `fetch` wrapper with base URL, correlation id, error mapping |
| [frontend/src/shared/types.ts](../../frontend/src/shared/types.ts) | Zod schemas mirroring the backend wire format |
| [frontend/src/features/feeds/](../../frontend/src/features/feeds/) | Feeds section + `useFeeds` query hook |
| [frontend/src/features/sleeps/](../../frontend/src/features/sleeps/) | Sleeps section + `useSleeps` query hook |
| [frontend/src/features/poops/](../../frontend/src/features/poops/) | Poops section + `usePoops` query hook |
| [frontend/src/features/appointments/](../../frontend/src/features/appointments/) | Appointments section + `useAppointments` query hook |
| [frontend/src/features/chat/](../../frontend/src/features/chat/) | Chat panel + `useChat` mutation hook + chat state reducer |

## Troubleshooting

- **CORS error in the browser console** — the backend isn't reading `MOMDIARY_ALLOWED_ORIGINS`. Restart uvicorn after editing `.env`.
- **All sections show an auth error** — the **backend** can't reach Azure OpenAI (this is a server-side problem, not a UI problem). Run `az login` and restart uvicorn.
- **Chat says "I couldn't save that"** — open the `<details>` element under the assistant's message to see the correlation id, then search the uvicorn log for that id to find the structured error line.
- **Sleeps section is empty even though you created one via chat** — `GET /v1/sleeps?date=` is scoped by the sleep's **start_at** date. A sleep that started yesterday and ended today only appears on yesterday.
