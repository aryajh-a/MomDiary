# MomDiary frontend

Single-page React + Vite app for the MomDiary tracker UX.
For the full walkthrough see [`specs/002-tracker-ux-chat/quickstart.md`](../specs/002-tracker-ux-chat/quickstart.md).

## Scripts

| Command                | Purpose                                                  |
|------------------------|----------------------------------------------------------|
| `npm install`          | Install deps (once after clone).                          |
| `npm run dev`          | Start the Vite dev server on `http://localhost:5173`.    |
| `npm run build`        | Type-check + produce a production bundle in `dist/`.     |
| `npm run preview`      | Serve the built bundle for local smoke testing.          |
| `npm test`             | Run unit + integration + contract Vitest suites.         |
| `npm run test:coverage`| Same as above with coverage report.                      |
| `npm run test:e2e`     | Run the Playwright smoke suite (opt-in, requires deps).  |
| `npm run lint`         | Biome lint over `src/` + `tests/`.                       |
| `npm run format`       | Biome auto-format.                                       |
| `npm run typecheck`    | `tsc --noEmit`.                                          |

## Environment

Copy `.env.example` → `.env.local` and set `VITE_API_BASE_URL` to the running backend host (default `http://localhost:8000`).

## Security caveat

v1 ships with **no browser-to-backend authentication** (see [research.md §R6](../specs/002-tracker-ux-chat/research.md)). The dev backend uses a CORS allow-list (`MOMDIARY_ALLOWED_ORIGINS`) defaulted to `http://localhost:5173`. Do not expose the backend to the public internet without first wiring up Microsoft Entra ID (or another auth provider) on the API surface.

## Optional: Playwright

Before running `npm run test:e2e` for the first time on a clean machine:

```powershell
npx playwright install --with-deps
```
