# Implementation Plan: MomDiary Tracker UX with Chat-Driven Entry

**Branch**: `002-tracker-ux-chat` | **Date**: 2026-05-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-tracker-ux-chat/spec.md`

## Summary

Build a phone-first single-page web app that lets one caregiver (a) browse a selected day's baby-care records grouped into four sections (feeds, sleeps, poops, appointments) by calling the existing `GET /v1/*` endpoints on the FastAPI backend, and (b) create new records by chatting in natural language against the existing `POST /v1/entries` conversational endpoint. The UI is built with React 18 + TypeScript on Vite, styled with Tailwind CSS, with TanStack Query as the network/state layer. For v1 the browser talks to the backend over a permissive CORS allow-list (`localhost:5173`) without per-user auth — the existing server-side `DefaultAzureCredential` continues to mediate Azure OpenAI access. Tests use Vitest + React Testing Library; Playwright provides a smoke flow.

## Technical Context

**Language/Version**: TypeScript 5.4 (frontend), Python 3.12 (existing backend, unchanged here)
**Primary Dependencies**: React 18, Vite 5, TanStack Query v5, Tailwind CSS 3, `zod` (response validation), `date-fns` + `date-fns-tz` (local-time rendering)
**Storage**: None on the client (chat history is React state for the session; selected date is React state, not persisted)
**Testing**: Vitest + @testing-library/react + @testing-library/user-event for unit + integration; MSW (Mock Service Worker) for handler stubs; Playwright for one smoke E2E that exercises US1 + US2 against a running uvicorn + SQLite
**Target Platform**: Modern evergreen browsers (Chromium / WebKit / Firefox), phone-sized portrait viewport as primary, desktop tolerated
**Project Type**: Web application — adds `frontend/` alongside existing `backend/`
**Performance Goals**: Initial paint < 1 s on cold load; date-change refresh < 2 s end-to-end with a typical day's volume (≤ ~100 entries); chat send → confirmation visible ≤ 10 s for short messages (SC-002). **Measured (T061)**: production build emits `index ~ 80.72 KB gzip + ChatPanel ~ 2.82 KB gzip + CSS 2.59 KB gzip` — well under the 250 KB gzip cap from [research.md §R11](./research.md).
**Constraints**: CORS allow-list = `http://localhost:5173` in v1; no user auth; chat history is session-scoped; mobile portrait must work without horizontal scroll
**Scale/Scope**: One caregiver, one device, ≤ ~500 records per day in worst case (well under any browser limit)

## Constitution Check

Gate evaluation against MomDiary Constitution v1.0.0:

- **I. Code Quality & Maintainability** — PASS. Frontend will adopt Biome (single tool for lint + format, configured to fail CI), all public components/hooks get JSDoc summaries, no `any` without justification, complexity-10 budget enforced by eslint-plugin-complexity (or biome equivalent).
- **II. Testing Standards (NON-NEGOTIABLE)** — PASS. Test-first for every component / hook. Coverage floor ≥ 80% lines / ≥ 70% branches on `frontend/src`. Three tiers: unit (pure hooks, formatters), integration (component + MSW), contract (response-shape tests against backend OpenAPI fixture). No live backend in CI; Playwright smoke is opt-in.
- **III. Performance Requirements** — PASS. Date-change refresh budget ≤ 2 s (matches FR-009 / SC-003). Streaming N/A in v1 — chat is single-shot request/response and the backend's tool dispatch already returns within a couple of seconds. No unbounded caches: TanStack Query default GC is acceptable; chat history is bounded to the session and we set a soft cap of 100 messages with a documented eviction policy.
- **IV. Modular Architecture** — PASS. Code is organized as `features/<record-type>` + `features/chat` + `shared/`. Each feature exposes a single hook + a single component; no cross-feature reaches. Shared `apiClient` is the only network seam.
- **V. Microsoft Agent Framework First (NON-NEGOTIABLE)** — PASS by inheritance. All agent behavior remains server-side in the unchanged backend, which already uses Microsoft Agent Framework rc6. The frontend never instantiates an agent — it only POSTs to `/v1/entries` and renders the JSON envelope.

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-tracker-ux-chat/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output — OpenAPI fixture + sample envelopes
└── tasks.md             # Phase 2 output (produced by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/                                  # existing, unchanged in this feature
└── src/momdiary/...

frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── public/
├── src/
│   ├── main.tsx                          # React root + QueryClientProvider
│   ├── App.tsx                           # Layout shell: header + date picker + sections + chat
│   ├── shared/
│   │   ├── apiClient.ts                  # fetch wrapper, base URL, correlation id, error mapping
│   │   ├── time.ts                       # local-time formatting helpers
│   │   ├── types.ts                      # Zod schemas + inferred types matching backend
│   │   └── queryKeys.ts                  # canonical TanStack Query key factory
│   ├── features/
│   │   ├── feeds/   { FeedsSection.tsx, useFeeds.ts, FeedItem.tsx }
│   │   ├── sleeps/  { SleepsSection.tsx, useSleeps.ts, SleepItem.tsx }
│   │   ├── poops/   { PoopsSection.tsx, usePoops.ts, PoopItem.tsx }
│   │   ├── appointments/ { AppointmentsSection.tsx, useAppointments.ts, AppointmentItem.tsx }
│   │   ├── date/    { DateBar.tsx, useSelectedDate.ts }
│   │   └── chat/    { ChatPanel.tsx, ChatMessageList.tsx, useChat.ts, types.ts }
│   └── styles/      { tailwind.css }
└── tests/
    ├── unit/        # hooks, formatters
    ├── integration/ # components + MSW
    ├── contract/    # zod schemas vs. backend OpenAPI fixture
    └── e2e/         # Playwright smoke (opt-in via npm script)
```

**Structure Decision**: Web-application layout (Option 2). The existing `backend/` directory is untouched; a new sibling `frontend/` directory holds the React app. The frontend is its own package with its own `package.json` and runs via Vite. There is no monorepo tooling in v1 — the two apps are deliberately decoupled.

## Complexity Tracking

*No constitutional violations — table intentionally empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
