---
description: "Tasks for feature 002-tracker-ux-chat"
---

# Tasks: MomDiary Tracker UX with Chat-Driven Entry

**Input**: Design documents from `/specs/002-tracker-ux-chat/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution II (NON-NEGOTIABLE) requires unit + integration + contract tiers with coverage floors ≥ 80% lines / ≥ 70% branches on `frontend/src`. Tests are authored **first** and demonstrated **failing** before the implementing task is merged.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered as an independent MVP increment.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no incomplete dependencies)
- **[Story]**: Maps a task to a user story (`US1`, `US2`, `US3`). Setup / Foundational / Polish phases have no `[Story]` label.

## Path Conventions

Web app layout (plan.md §Project Structure). Backend lives in [backend/](../../backend/) and is untouched except for the one CORS task (T007). All other source paths are under [frontend/](../../frontend/) (created in Phase 1).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the `frontend/` package and dev toolchain.

- [X] T001 Create `frontend/` directory tree per [plan.md §Project Structure](./plan.md): `frontend/{src,tests,public}` with subfolders `src/{features,shared,styles}` and `tests/{unit,integration,contract,e2e,fixtures,_msw}`.
- [X] T002 Initialize Node project: write [frontend/package.json](../../frontend/package.json) with name `momdiary-frontend`, type `module`, scripts `dev`, `build`, `preview`, `test`, `test:watch`, `test:e2e`, `lint`, `format`, `typecheck`; runtime deps `react@^18`, `react-dom@^18`, `@tanstack/react-query@^5`, `zod@^3`, `date-fns@^3`, `date-fns-tz@^3`; dev deps `typescript@^5.4`, `vite@^5`, `@vitejs/plugin-react@^4`, `vitest@^1`, `@vitest/coverage-v8`, `@testing-library/react@^15`, `@testing-library/user-event@^14`, `@testing-library/jest-dom@^6`, `jsdom@^24`, `msw@^2`, `@playwright/test@^1`, `tailwindcss@^3`, `postcss@^8`, `autoprefixer@^10`, `@biomejs/biome@^1`.
- [X] T003 [P] Create [frontend/tsconfig.json](../../frontend/tsconfig.json) with `target: ES2022`, `module: ESNext`, `jsx: react-jsx`, `strict: true`, `noUncheckedIndexedAccess: true`, `paths` mapping `@/*` → `src/*`.
- [X] T004 [P] Create [frontend/vite.config.ts](../../frontend/vite.config.ts) with the React plugin, alias `@` → `src/`, and a `test` block enabling jsdom, `globals: true`, `setupFiles: ['./tests/_msw/setup.ts']`, `coverage` thresholds (lines: 80, branches: 70).
- [X] T005 [P] Create [frontend/tailwind.config.ts](../../frontend/tailwind.config.ts), [frontend/postcss.config.js](../../frontend/postcss.config.js), and [frontend/src/styles/tailwind.css](../../frontend/src/styles/tailwind.css) (`@tailwind base/components/utilities`). Tailwind `content` globs cover `index.html` and `src/**/*.{ts,tsx}`.
- [X] T006 [P] Create [frontend/biome.json](../../frontend/biome.json) configuring Biome as the single lint+format tool: 2-space indent, double quotes, organize-imports on save, `complexity.noExcessiveCognitiveComplexity` set to 10 (Constitution I).
- [X] T007 [P] Create [frontend/index.html](../../frontend/index.html) and [frontend/src/main.tsx](../../frontend/src/main.tsx) — `main.tsx` mounts `<App />` inside a `<QueryClientProvider>` with a `QueryClient` configured for `staleTime: 30_000`, `retry: 1`.
- [X] T008 [P] Create [frontend/.env.example](../../frontend/.env.example) documenting `VITE_API_BASE_URL=http://localhost:8000` (per [quickstart.md](./quickstart.md)).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure all three user stories depend on. **No user-story task may begin until every task in this phase is complete.** Tests within each pair are authored and demonstrated failing before the implementation task is merged.

- [X] T009 Add FastAPI CORS middleware in [backend/src/momdiary/main.py](../../backend/src/momdiary/main.py): read `MOMDIARY_ALLOWED_ORIGINS` (comma-separated) from settings, default `http://localhost:5173`; allow methods `GET, POST, PUT, OPTIONS` and headers `*`. Also extend [backend/src/momdiary/config.py](../../backend/src/momdiary/config.py) with the `momdiary_allowed_origins: list[str]` Pydantic setting and update [backend/.env.example](../../backend/.env.example).
- [X] T010 [P] Test-first: write [frontend/tests/contract/schemas.test.ts](../../frontend/tests/contract/schemas.test.ts) — parses every JSON fixture under [frontend/tests/fixtures/](../../frontend/tests/fixtures/) against its Zod schema in `@/shared/types`; one `it()` per fixture. Tests MUST fail initially because the fixtures and schemas do not yet exist.
- [X] T011 [P] Copy the seven sample envelopes from [specs/002-tracker-ux-chat/contracts/samples/](./contracts/samples/) into [frontend/tests/fixtures/](../../frontend/tests/fixtures/) (`feeds.list.json`, `sleeps.list.json`, `poops.list.json`, `appointments.list.json`, `entries.created.json`, `entries.clarification.json`, `error.validation.json`).
- [X] T012 Create [frontend/src/shared/types.ts](../../frontend/src/shared/types.ts) — Zod schemas mirroring [data-model.md §Wire entities](./data-model.md): `FeedEntry`, `SleepEntry`, `PoopEntry`, `AppointmentNote`, `AppointmentEntry`, the four `*ListResponse` wrappers, `AgentWriteRequest`, `AgentWriteResponse` (discriminated union on `outcome`), `ErrorBody`. Export inferred TypeScript types. After this task, T010 MUST pass.
- [X] T013 [P] Test-first: write [frontend/tests/unit/time.test.ts](../../frontend/tests/unit/time.test.ts) — covers `formatLocalTime(iso)` (renders local hh:mm a), `formatDateHeading(date)` (e.g. "Today" / "Mon, May 17"), `formatDuration(minutes)` ("1h 30m"). Tests MUST fail initially.
- [X] T014 Create [frontend/src/shared/time.ts](../../frontend/src/shared/time.ts) implementing the three helpers from T013 using `date-fns` + `Intl.DateTimeFormat`. After this task, T013 MUST pass.
- [X] T015 [P] Test-first: write [frontend/tests/unit/queryKeys.test.ts](../../frontend/tests/unit/queryKeys.test.ts) — asserts `queryKeys.feeds(date)`, `.sleeps(date)`, `.poops(date)`, `.appointments(date)` produce stable, deterministic keys; asserts `queryKeys.allForDate(date)` returns the four keys.
- [X] T016 Create [frontend/src/shared/queryKeys.ts](../../frontend/src/shared/queryKeys.ts) implementing the typed key factory. After this task, T015 MUST pass.
- [X] T017 [P] Test-first: write [frontend/tests/unit/apiClient.test.ts](../../frontend/tests/unit/apiClient.test.ts) — stubs `globalThis.fetch`; verifies each method (`getFeeds`, `getSleeps`, `getPoops`, `getAppointments`, `postEntry`) sends the right URL + method + body, generates a `X-Correlation-ID` header per call, parses the response through Zod, and maps non-2xx into a typed `ApiError`.
- [X] T018 Create [frontend/src/shared/apiClient.ts](../../frontend/src/shared/apiClient.ts) — `fetch` wrapper reading `import.meta.env.VITE_API_BASE_URL`; generates a UUID v4 correlation id per request; parses via the schemas from T012; throws `ApiError` with `{ status, code, message, correlationId }` on error envelopes. After this task, T017 MUST pass.
- [X] T019 [P] Create the MSW test scaffolding: [frontend/tests/_msw/handlers.ts](../../frontend/tests/_msw/handlers.ts) (default handlers returning the fixtures from T011) and [frontend/tests/_msw/setup.ts](../../frontend/tests/_msw/setup.ts) (Node server, `beforeAll`/`afterEach`/`afterAll`, `@testing-library/jest-dom` matchers).
- [X] T020 [P] Create [frontend/src/App.tsx](../../frontend/src/App.tsx) layout shell — `<main>` with three regions: header + `<DateBar />` placeholder, the four `*Section` placeholders in a single-column phone-first layout, and a `<ChatPanel />` placeholder pinned to the bottom. Real components are wired in their respective user stories.

**Checkpoint**: Foundation complete — `npm test` passes the schema + helper + apiClient tests; the dev server starts and renders the empty shell.

---

## Phase 3: User Story 1 — Browse today's records by type (Priority: P1) 🎯 MVP

**Goal**: With seeded backend data, the caregiver opens the app and sees today's records grouped into four sections; they can navigate to any date and the sections refetch.

**Independent Test**: Seed the backend with at least one entry of each type for today, open the app: all four sections render correctly with local-time formatting; switch to yesterday → sections refetch and show yesterday's data (or empty states). No write actions involved.

### Tests for User Story 1 (test-first)

- [X] T021 [P] [US1] Write [frontend/tests/integration/feeds-section.test.tsx](../../frontend/tests/integration/feeds-section.test.tsx) — three cases: loaded (fixture from T011 renders 2 items in time order, primary attribute prominent), empty (MSW returns `{ date, items: [] }` → renders "No feeds logged for this date"), error (MSW returns 500 → renders inline retry affordance). Must fail.
- [X] T022 [P] [US1] Write [frontend/tests/integration/sleeps-section.test.tsx](../../frontend/tests/integration/sleeps-section.test.tsx) — loaded (renders duration as `1h 30m`), empty, error. Must fail.
- [X] T023 [P] [US1] Write [frontend/tests/integration/poops-section.test.tsx](../../frontend/tests/integration/poops-section.test.tsx) — loaded (consistency label), empty, error. Must fail.
- [X] T024 [P] [US1] Write [frontend/tests/integration/appointments-section.test.tsx](../../frontend/tests/integration/appointments-section.test.tsx) — loaded (renders most-recent-note preview, "+1 more" indicator when notes.length > 1), empty, error. Must fail.
- [X] T025 [P] [US1] Write [frontend/tests/integration/date-bar.test.tsx](../../frontend/tests/integration/date-bar.test.tsx) — default value equals today in `Intl.DateTimeFormat().resolvedOptions().timeZone`; prev/next buttons shift by one day; selecting a date invalidates the four query keys. Must fail.
- [X] T026 [P] [US1] Write [frontend/tests/integration/section-isolation.test.tsx](../../frontend/tests/integration/section-isolation.test.tsx) — when feeds endpoint returns 500, the other three sections still render successfully (FR-007). Must fail.

### Implementation for User Story 1

- [X] T027 [P] [US1] Create [frontend/src/features/feeds/useFeeds.ts](../../frontend/src/features/feeds/useFeeds.ts) — `useQuery` with key `queryKeys.feeds(date)`, `queryFn` calling `apiClient.getFeeds`.
- [X] T028 [P] [US1] Create [frontend/src/features/sleeps/useSleeps.ts](../../frontend/src/features/sleeps/useSleeps.ts).
- [X] T029 [P] [US1] Create [frontend/src/features/poops/usePoops.ts](../../frontend/src/features/poops/usePoops.ts).
- [X] T030 [P] [US1] Create [frontend/src/features/appointments/useAppointments.ts](../../frontend/src/features/appointments/useAppointments.ts).
- [X] T031 [P] [US1] Create [frontend/src/features/feeds/FeedItem.tsx](../../frontend/src/features/feeds/FeedItem.tsx) — shows local time + `<quantity> <unit> <feed_type label>`; quantity is the visually prominent element.
- [X] T032 [P] [US1] Create [frontend/src/features/sleeps/SleepItem.tsx](../../frontend/src/features/sleeps/SleepItem.tsx) — shows start–end local time + duration via `formatDuration`; duration is the prominent element.
- [X] T033 [P] [US1] Create [frontend/src/features/poops/PoopItem.tsx](../../frontend/src/features/poops/PoopItem.tsx) — shows local time + consistency label; consistency is the prominent element.
- [X] T034 [P] [US1] Create [frontend/src/features/appointments/AppointmentItem.tsx](../../frontend/src/features/appointments/AppointmentItem.tsx) — shows scheduled local time + most-recent note preview + "+N more" badge when needed; scheduled time is the prominent element.
- [X] T035 [P] [US1] Create [frontend/src/features/feeds/FeedsSection.tsx](../../frontend/src/features/feeds/FeedsSection.tsx) — header with title + item count, loading state, empty state (`empty.ts` copy), error state with retry button calling the query's `refetch`. Must satisfy T021.
- [X] T036 [P] [US1] Create [frontend/src/features/sleeps/SleepsSection.tsx](../../frontend/src/features/sleeps/SleepsSection.tsx). Must satisfy T022.
- [X] T037 [P] [US1] Create [frontend/src/features/poops/PoopsSection.tsx](../../frontend/src/features/poops/PoopsSection.tsx). Must satisfy T023.
- [X] T038 [P] [US1] Create [frontend/src/features/appointments/AppointmentsSection.tsx](../../frontend/src/features/appointments/AppointmentsSection.tsx). Must satisfy T024.
- [X] T039 [US1] Create [frontend/src/features/date/useSelectedDate.ts](../../frontend/src/features/date/useSelectedDate.ts) — React Context exposing `{ date, setDate }`; default = today in browser tz.
- [X] T040 [US1] Create [frontend/src/features/date/DateBar.tsx](../../frontend/src/features/date/DateBar.tsx) — heading via `formatDateHeading`, prev/next buttons, native date input. Must satisfy T025.
- [X] T041 [US1] Wire `DateBar` + four sections into [frontend/src/App.tsx](../../frontend/src/App.tsx); wrap the tree in `useSelectedDate` provider. Must satisfy T026.
- [X] T042 [US1] Add a manual refresh control in `App.tsx` header — clicking it calls `queryClient.invalidateQueries({ predicate: q => q.queryKey[0] in {feeds,sleeps,poops,appointments} })` (FR-008).

**Checkpoint**: User Story 1 is independently functional. The app shows today's records, lets the user navigate dates, and refreshes on demand. All US1 tests pass.

---

## Phase 4: User Story 2 — Add a record by chatting in plain language (Priority: P1)

**Goal**: A persistent chat panel lets the caregiver type a free-form message; the assistant replies and any newly created record is visible in its section within 2 seconds.

**Independent Test**: With the backend running, type "120 ml breast milk just now" in chat → assistant confirmation appears, feeds section shows the new entry. Type "I fed the baby" → assistant asks a clarifying question, no record created. Trigger a 500 from MSW → chat shows a friendly error, caregiver's draft is preserved.

### Tests for User Story 2 (test-first)

- [X] T043 [P] [US2] Write [frontend/tests/unit/chatReducer.test.ts](../../frontend/tests/unit/chatReducer.test.ts) — pure reducer covering: submit appends caregiver msg + sets `inFlight=true`; success appends assistant msg; error appends assistant msg + preserves draft; FIFO eviction at 100 messages (Constitution III bounded-memory). Must fail.
- [X] T044 [P] [US2] Write [frontend/tests/integration/chat-panel.test.tsx](../../frontend/tests/integration/chat-panel.test.tsx) — sending "120 ml breast milk just now" with MSW returning `entries.created.json`: assistant confirmation visible; submit button is disabled while in flight; thinking indicator visible; chat history grows. Must fail.
- [X] T045 [P] [US2] Write [frontend/tests/integration/chat-clarification.test.tsx](../../frontend/tests/integration/chat-clarification.test.tsx) — MSW returns `entries.clarification.json`: assistant question appears, no section invalidation triggered, input retains focus. Must fail.
- [X] T046 [P] [US2] Write [frontend/tests/integration/chat-error.test.tsx](../../frontend/tests/integration/chat-error.test.tsx) — MSW returns 500: assistant renders the localized error message, `<details>` element shows `correlation_id`, the input draft equals the caregiver's submitted text. Must fail.
- [X] T047 [P] [US2] Write [frontend/tests/integration/chat-refresh.test.tsx](../../frontend/tests/integration/chat-refresh.test.tsx) — after a `created` envelope with `entry_type=feed`, the feeds query is invalidated and the next render shows the new feed within 2 seconds (FR-009). Must fail.

### Implementation for User Story 2

- [X] T048 [P] [US2] Create [frontend/src/features/chat/types.ts](../../frontend/src/features/chat/types.ts) — `ChatMessage`, `ChatSession`, `ChatAction` types per [data-model.md §Client state shape](./data-model.md).
- [X] T049 [US2] Create [frontend/src/features/chat/reducer.ts](../../frontend/src/features/chat/reducer.ts) — pure `chatReducer(state, action)` with FIFO cap at 100. Must satisfy T043.
- [X] T050 [US2] Create [frontend/src/features/chat/useChat.ts](../../frontend/src/features/chat/useChat.ts) — combines `useReducer(chatReducer)` with `useMutation`. On `outcome ∈ {created, updated, deleted}`, calls `queryClient.invalidateQueries({ queryKey: queryKeys[entryTypePlural(entry_type)](selectedDate) })`. On any non-2xx, dispatches the error action preserving the draft.
- [X] T051 [P] [US2] Create [frontend/src/features/chat/ChatMessageList.tsx](../../frontend/src/features/chat/ChatMessageList.tsx) — renders messages with role-distinct styling, monospaced correlation id inside `<details>` for assistant error messages, auto-scroll to bottom on new message.
- [X] T052 [US2] Create [frontend/src/features/chat/ChatPanel.tsx](../../frontend/src/features/chat/ChatPanel.tsx) — `<textarea aria-label="Message">`, send button (disabled while `inFlight`), thinking indicator, draft persistence on error. Must satisfy T044, T045, T046.
- [X] T053 [US2] Wire `ChatPanel` into [frontend/src/App.tsx](../../frontend/src/App.tsx) via `React.lazy` + `<Suspense>` to honor the bundle-split decision in [research.md §R11](./research.md). Must satisfy T047.

**Checkpoint**: User Stories 1 + 2 both fully functional. The caregiver can browse a date and add records via chat; new records appear in their section within 2 seconds.

---

## Phase 5: User Story 3 — Visual distinction across record types (Priority: P2)

**Goal**: Each of the four section types has a distinct, accessible visual identity (icon + accent color + label) so first-time users find each section by visual cue alone in ≤ 3 seconds.

**Independent Test**: Render the app with one entry of each type. A first-time viewer correctly identifies each section in under 3 seconds. Color-blind simulation still distinguishes sections via icon + label (FR-021).

### Tests for User Story 3 (test-first)

- [X] T054 [P] [US3] Write [frontend/tests/integration/visual-identity.test.tsx](../../frontend/tests/integration/visual-identity.test.tsx) — for each section: queryByRole "region" with the expected `aria-label`, a visible icon (svg role="img" with a non-empty `<title>`), and a header text label. The most prominent number/duration/consistency/time element MUST carry a Tailwind class indicating large font (e.g., `text-2xl` or `text-3xl`). Must fail.

### Implementation for User Story 3

- [X] T055 [P] [US3] Extend [frontend/tailwind.config.ts](../../frontend/tailwind.config.ts) with theme tokens `colors.feed`, `colors.sleep`, `colors.poop`, `colors.appointment` (WCAG AA contrast against white).
- [X] T056 [P] [US3] Add icon components: [frontend/src/features/feeds/icon.tsx](../../frontend/src/features/feeds/icon.tsx) (bottle), [frontend/src/features/sleeps/icon.tsx](../../frontend/src/features/sleeps/icon.tsx) (moon), [frontend/src/features/poops/icon.tsx](../../frontend/src/features/poops/icon.tsx) (diaper), [frontend/src/features/appointments/icon.tsx](../../frontend/src/features/appointments/icon.tsx) (calendar). Each `<svg role="img"><title>…</title></svg>`.
- [X] T057 [US3] Apply icon + accent color + `aria-label` in each `*Section` header.
- [X] T058 [US3] Bump primary-attribute typography (quantity / duration / consistency / scheduled time) in each `*Item` to `text-2xl font-semibold`. Must satisfy T054.

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening before declaring the feature done.

- [ ] T059 [P] Create [frontend/tests/e2e/smoke.spec.ts](../../frontend/tests/e2e/smoke.spec.ts) — Playwright smoke: boots uvicorn against a temp SQLite, opens the app, logs a feed via chat, asserts the feeds section shows it within 10 s. Opt-in via `npm run test:e2e`; not part of default `npm test`.
- [X] T060 [P] Run `npm test -- --coverage` and verify ≥ 80% lines / ≥ 70% branches on `frontend/src`; commit the coverage summary into [specs/002-tracker-ux-chat/coverage.md](./coverage.md).
- [X] T061 [P] Run `npm run build` and confirm the gzipped main bundle is ≤ 250 KB per [research.md §R11](./research.md); record the actual size in [plan.md](./plan.md) under Performance Goals.
- [ ] T062 [P] Run `npx playwright install --with-deps` once in the dev environment so T059 can execute on demand; document in [frontend/README.md](../../frontend/README.md).
- [X] T063 [P] Create [frontend/README.md](../../frontend/README.md) — short README pointing at [quickstart.md](./quickstart.md), listing the npm scripts, and naming the security caveat from [research.md §R6](./research.md).
- [ ] T064 Accessibility audit: run `@axe-core/react` or `axe-playwright` against the rendered app; file follow-up issues (NOT this feature) for any non-trivial violations. Document the audit in [specs/002-tracker-ux-chat/a11y-audit.md](./a11y-audit.md).
- [X] T065 Update [.specify/feature.json](../../.specify/feature.json) to point at this feature directory (already done at /speckit.specify time — verify).
- [ ] T066 Walk through [quickstart.md](./quickstart.md) end-to-end on a clean checkout to confirm the steps work; fix any drift in the quickstart text.

**Checkpoint**: Feature 002-tracker-ux-chat is feature-complete and meets all six success criteria from [spec.md §Success Criteria](./spec.md).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup, T001–T008)**: no upstream dependencies; T001 must finish before any [P] sibling because they all write into the directory tree it creates.
- **Phase 2 (Foundational, T009–T020)**: depends on Phase 1 (frontend toolchain) and is itself a **hard block** for all user-story phases. T010 (contract tests) must be written failing **before** T012 lands; same for T013→T014, T015→T016, T017→T018.
- **Phase 3 (US1)**: depends on Phase 2 complete. Internally: T021–T026 (tests) must be authored and failing before their matching implementation tasks (T035–T040, T041 for isolation). Hooks (T027–T030) and Items (T031–T034) can land in parallel; Sections (T035–T038) depend on their hook + item.
- **Phase 4 (US2)**: depends on Phase 2 complete. Independent of US1 except for `queryClient.invalidateQueries` calls in T050 which target keys created in US1; T050 may land before US1 sections — invalidation is a no-op when keys aren't observed.
- **Phase 5 (US3)**: depends on US1 sections existing (T035–T038) since the visual changes apply to their headers and items.
- **Phase 6 (Polish)**: depends on every user story being complete.

### User Story Dependencies

- **US1 (P1)** — no story dependencies.
- **US2 (P1)** — no hard dependency on US1; the chat panel works without sections existing. The "refresh after write" behavior (T047, T053) is only observable once US1 sections exist; if US2 lands first, mark T047 with a TODO referring to US1.
- **US3 (P2)** — depends on US1 sections.

### Within Each User Story

- Tests are authored first and demonstrated **failing** before the matching implementation task is merged (Constitution II).
- Hooks → Items → Sections → Wiring within each phase.

### Parallel Opportunities

- **Within Phase 2**, T010 + T011 + T013 + T015 + T017 + T019 + T020 are mutually independent.
- **Within Phase 3**, all six US1 test tasks (T021–T026) are parallelizable; all four hook tasks (T027–T030), four item tasks (T031–T034), and four section tasks (T035–T038) are pairwise independent.
- **Within Phase 4**, T043–T047 (tests) are parallelizable. T048 + T051 are parallel; T049 depends on T048; T050 depends on T049; T052 depends on T050 + T051.
- **Within Phase 5**, T055 + T056 are parallel; T057 depends on T056; T058 depends on T057.
- **Within Phase 6**, T059–T063 are parallelizable.
- **Across user stories**: with two engineers, one can pick US1 and another US2 immediately after Phase 2 completes.

---

## Implementation Strategy

### MVP scope (recommended cut)

**Phases 1 + 2 + 3 (US1)** delivers a viewable, navigable record dashboard wired to the existing backend GET endpoints. That alone justifies shipping if the chat agent is not yet stable.

### Incremental delivery

1. **MVP**: ship after US1. Caregivers can already browse. Chat-driven writes use the backend's existing HTTP path (e.g., via `requests.http` or curl) until US2 lands.
2. **MVP+1**: ship after US2. The differentiating chat-driven entry is in place.
3. **Polish**: ship US3 + Phase 6 together as a final delivery sweep.

### Format validation

Every task above follows the strict format `- [ ] T### [P?] [Story?] Description with file path` mandated by the `/speckit.tasks` workflow. Setup, Foundational, and Polish tasks carry no `[Story]` label; every US-phase task carries its `[USn]` label.

---

## Task Count Summary

| Phase | Tasks | Test tasks | Implementation tasks |
|-------|-------|------------|----------------------|
| 1 — Setup | T001–T008 (8) | 0 | 8 |
| 2 — Foundational | T009–T020 (12) | 4 (T010, T013, T015, T017) | 8 |
| 3 — US1 | T021–T042 (22) | 6 (T021–T026) | 16 |
| 4 — US2 | T043–T053 (11) | 5 (T043–T047) | 6 |
| 5 — US3 | T054–T058 (5) | 1 (T054) | 4 |
| 6 — Polish | T059–T066 (8) | 1 (T059) | 7 |
| **Total** | **66** | **17** | **49** |

### Independent test criteria recap

- **US1**: open the app, see today's records in four sections, navigate dates, refresh manually. All without any write.
- **US2**: type a free-form chat message, see a confirmation or clarifying question or friendly error; new records appear in their section within 2 seconds.
- **US3**: first-time viewer identifies each section visually in ≤ 3 seconds; accessibility holds under color-vision simulation.
