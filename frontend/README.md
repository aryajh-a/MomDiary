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

Copy `.env.example` → `.env.local` and set:

- `VITE_API_BASE_URL` — backend host (default `http://localhost:8000`).
- `VITE_CLERK_PUBLISHABLE_KEY` — Clerk publishable key (`pk_test_...` / `pk_live_...`).
  Obtain from the Clerk Dashboard → API Keys. The app will fail to mount
  `<ClerkProvider>` without it (feature 008).

## Auth (feature 008)

MomDiary uses **Clerk** as the sole identity provider. The frontend embeds
Clerk's prebuilt `<SignIn />` and `<SignUp />` components at in-app routes
`/sign-in` and `/sign-up` and supplies a Clerk-issued JWT on every API
request via `Authorization: Bearer <token>`. See
[`specs/008-clerk-auth/quickstart.md`](../specs/008-clerk-auth/quickstart.md)
for Clerk dashboard configuration (email+password, Google provider, the
`momdiary-default` JWT template, and the webhook endpoint).

## Optional: Playwright

Before running `npm run test:e2e` for the first time on a clean machine:

```powershell
npx playwright install --with-deps
```
