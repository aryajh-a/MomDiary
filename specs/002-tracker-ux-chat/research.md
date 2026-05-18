# Phase 0 — Research: MomDiary Tracker UX

This document captures decisions and rejected alternatives for every non-trivial choice in `plan.md`. No `NEEDS CLARIFICATION` markers remain after this phase.

## R1. Frontend framework

- **Decision**: React 18 + TypeScript on Vite 5.
- **Rationale**: Largest mainstream ecosystem for the patterns this app needs (lists, hooks, suspense-friendly query lib). Vite gives instant cold-start and zero-config TS. The team's existing familiarity matters more than micro-perf for a single-caregiver UI.
- **Alternatives considered**:
  - **Next.js** — adds a full-stack story this feature doesn't need (no SSR requirement, no API routes; the FastAPI backend already covers that). Rejected as over-scoped.
  - **Svelte / SvelteKit** — smaller bundle but unfamiliar tooling; would slow delivery and add a fresh learning surface for testing.
  - **Vue 3** — comparable to React for this use case; rejected purely on ecosystem inertia with TanStack Query and Tailwind.

## R2. Styling

- **Decision**: Tailwind CSS 3 utility classes, no component library.
- **Rationale**: One file (`tailwind.css`) configures the design tokens; class-based composition keeps each component self-contained which aligns with Constitution IV (modularity). Mobile-portrait constraints (FR-020) are easier to enforce with utility-first.
- **Alternatives considered**:
  - **MUI / Chakra / Mantine** — bring opinionated components but inflate bundle size and lock the visual identity (Constitution III performance budget; SC-001 readability).
  - **CSS Modules** — viable but more boilerplate per component; Tailwind is faster for a phone-first single-page UI.

## R3. Data fetching & cache

- **Decision**: TanStack Query v5 over the `fetch` API.
- **Rationale**: Built-in dedup, refetch-on-window-focus, mutation invalidation — directly satisfies FR-008 (manual refresh), FR-009 (section auto-refresh after chat write), and SC-003 (date-change < 2 s). Query keys give us a typed seam for tests.
- **Alternatives considered**:
  - **Raw `fetch` + `useState` / `useEffect`** — forces us to hand-roll cache invalidation, retry policy, and request dedup; rejected on Constitution I (maintainability) and II (testability).
  - **SWR** — comparable; TanStack chosen because its `useMutation` semantics dovetail neatly with chat-driven writes and section invalidation.
  - **axios** — extra dependency for nothing this app needs; the browser `fetch` is sufficient and Zod handles parsing.

## R4. Response validation

- **Decision**: Zod 3 schemas describing each list response (`FeedListResponse`, `SleepListResponse`, `PoopListResponse`, `AppointmentListResponse`) and the conversational write envelope. Schemas live in `frontend/src/shared/types.ts` and are imported by both the hooks and the contract tests.
- **Rationale**: The backend's Pydantic schemas are the source of truth on the server. Mirroring them in Zod on the client gives the frontend a typed boundary, a single place to fail loud on shape drift, and a reusable fixture for contract tests (Constitution II).
- **Alternatives considered**:
  - **`io-ts`** — more powerful but heavier-weight API and unfamiliar to most React teams.
  - **TypeScript-only declarations** — no runtime check; would silently render garbage on backend changes.

## R5. Local-time rendering

- **Decision**: `date-fns` + `date-fns-tz`. The backend returns ISO-8601 strings with offset already; the frontend converts to the **browser's** local timezone via `Intl.DateTimeFormat` (no external tz database needed). `date-fns-tz` is retained only for the rare case we need to anchor to a specific zone.
- **Rationale**: FR-018 mandates human-friendly local time. Browsers already ship the IANA tz database, so we lean on the platform and use `date-fns` purely for formatting (`format`, `differenceInMinutes` for sleep duration).
- **Alternatives considered**:
  - **Luxon** — heavier and brings its own tz layer we don't need.
  - **Day.js with tz plugin** — comparable; date-fns wins on tree-shake and explicit imports.

## R6. Authentication for v1

- **Decision**: No browser-to-backend authentication in v1. The FastAPI server enables a CORS allow-list of `http://localhost:5173` (Vite dev server) and refuses all other origins. The backend's Azure access continues to flow through server-side `DefaultAzureCredential`.
- **Rationale**: The current backend identity model is **server-to-Azure**, not **user-to-backend** — there is no JWT issuer wired up and adding MSAL.js + a JWT-validating dependency in the backend is materially larger than this feature. FR-019 says "use the existing flow"; the existing flow is server-side credential. For local development this is safe and unblocks the UX work. Production hardening is deferred to a follow-up feature.
- **Alternatives considered**:
  - **MSAL.js + Entra ID** — requires backend changes (JWT bearer middleware, new `azure-identity` token validation), which is out of scope for this feature.
  - **Static dev token in env var** — provides no real security and just adds a wiring step; rejected as security-theater without benefit.
- **Risks documented**: If the Vite dev server is exposed beyond localhost (e.g., `--host 0.0.0.0` on a shared network) the backend becomes accessible to anyone on that network. The quickstart explicitly warns against this and recommends a follow-up feature for proper auth.

## R7. Chat history persistence

- **Decision**: Session-scoped in-memory React state. No `localStorage`, no `IndexedDB`.
- **Rationale**: FR-017 explicitly bounds history to the session. Persisting across reloads would require an eviction policy and a privacy story we don't want to commit to in v1. Constitution III (bounded memory) is satisfied via a soft cap of 100 messages with FIFO eviction.
- **Alternatives considered**:
  - **`sessionStorage`** — survives accidental refresh; deferred to a v1.1 follow-up.
  - **Round-trip to a `/v1/agent_interactions` GET** — the backend audit table is not designed for caregiver-facing replay; rejected.

## R8. Optimistic vs. server-truth updates after chat write

- **Decision**: **Server-truth.** After the chat assistant replies with `outcome=created|updated|deleted`, the frontend invalidates the matching TanStack Query key (e.g., `["feeds", date]`) and refetches. No optimistic insert.
- **Rationale**: The backend may normalize fields (e.g., ounces → ml) and the conversational reply may not include every field the list view shows. A refetch costs ≤ 200 ms locally and keeps the UI as the source of *display* with the backend as the source of *truth*. FR-009 requires the visible refresh within 2 s — well within budget.
- **Alternatives considered**:
  - **Optimistic insert from the envelope** — possible because the response payload mirrors the entry schema, but it risks divergence on field normalization. Reserved for a follow-up performance pass if SC-002 (10 s end-to-end) becomes binding.

## R9. Error envelopes

- **Decision**: Map backend HTTP error bodies (`{ error, message, correlation_id }`) to user-facing chat messages and per-section retry affordances. The `correlation_id` is shown in a `<details>` element so power users can copy it; non-technical users never see it by default.
- **Rationale**: FR-007 (per-section error), FR-012 (correlation_id visible on error), FR-016 (non-technical messages).
- **Alternatives considered**:
  - **Toast / snackbar layer** — adds a global UI primitive for one use case; rejected as overkill.

## R10. Testing strategy details

- **Decision**:
  - **Unit** (Vitest): formatters in `shared/time.ts`, query-key factory, Zod schemas (round-trip parse tests).
  - **Integration** (Vitest + RTL + MSW): each `*Section` component with a MSW handler returning fixtures; covers empty state, error state, and loaded state.
  - **Contract** (Vitest): for each Zod schema, parse a captured backend response (committed under `frontend/tests/fixtures/*.json` and refreshed from the backend's OpenAPI fixture in `specs/001-baby-tracker-backend/contracts/`).
  - **E2E** (Playwright, opt-in): one test that boots uvicorn against a temp SQLite, opens the app, logs a feed via chat, and asserts the feeds section shows it within 10 s. Not run in default CI.
- **Rationale**: Matches Constitution II tiers (unit / integration / contract) without inflating CI time. E2E lives behind `npm run test:e2e` so the default `npm test` stays fast.

## R11. Bundle size & performance budgets

- **Decision**: Target initial JS bundle ≤ 250 KB gzip. Tailwind + React + TanStack Query + Zod fit comfortably. Vite-generated chunks split chat from the date-list automatically via dynamic import (`React.lazy` on `ChatPanel`).
- **Rationale**: SC-001 (find a record in 5 s) implies fast initial paint on a phone-class device. Constitution III performance budgets translate to a measurable bundle cap.
- **Alternatives considered**: Skipping the lazy split keeps the code simpler but pushes a chat panel that's not always needed on first paint; rejected.

## R12. Accessibility floor

- **Decision**: Each record type uses both color **and** an icon + text label (FR-021). Buttons have `aria-label`. The chat input is a `<textarea>` with `aria-label="Message"` and a visible send button. Color tokens for the four sections are chosen from the WCAG AA contrast scale against a white background.
- **Rationale**: Constitution I (maintainability includes accessibility for a self-consistent product); FR-021 mandates a non-color cue.
- **Alternatives considered**: Color-only differentiation — explicitly rejected by FR-021.

## R13. Backend changes required by this feature

- **Decision**: The only backend change is enabling CORS for `http://localhost:5173`. Add `fastapi.middleware.cors.CORSMiddleware` with an `allow_origins` list driven by an env var `MOMDIARY_ALLOWED_ORIGINS` (default `http://localhost:5173`).
- **Rationale**: Without CORS the browser cannot call the API at all. No other backend changes are required.
- **Alternatives considered**: Vite dev-server proxy. Works for dev but doesn't carry to any future deployment; rejected as paving over a real issue.
