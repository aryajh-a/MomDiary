# UX Contracts

The frontend in feature `002-tracker-ux-chat` is a pure consumer of contracts already shipped by feature `001-baby-tracker-backend`. These files document the slice of those contracts that the frontend depends on, in a form usable by the frontend's contract tests.

## Files

- [`openapi.slice.yaml`](./openapi.slice.yaml) — minimal OpenAPI 3.1 fragment covering only the endpoints the frontend calls.
- [`samples/`](./samples) — captured JSON envelopes used as fixtures by Vitest contract tests.

## Endpoints covered

| Method | Path                                  | Used by         |
|--------|---------------------------------------|-----------------|
| GET    | `/v1/feeds?date={YYYY-MM-DD}`         | `useFeeds`      |
| GET    | `/v1/sleeps?date={YYYY-MM-DD}`        | `useSleeps`     |
| GET    | `/v1/poops?date={YYYY-MM-DD}`         | `usePoops`      |
| GET    | `/v1/appointments?date={YYYY-MM-DD}`  | `useAppointments` |
| POST   | `/v1/entries`                         | `useChat`       |

Each list endpoint returns `*ListResponse = { date: string, items: <Entry>[] }`. The chat endpoint returns the `AgentWriteResponse` union documented in `../data-model.md`. Error responses across all five share the `{ error, message, correlation_id }` shape.

## How contract tests use these files

Vitest tests under `frontend/tests/contract/` parse every file in `samples/` against the Zod schemas in `frontend/src/shared/types.ts`. Any drift between the backend's wire format and the frontend's schemas causes those tests to fail loudly, fulfilling Constitution II's contract-test tier.

The OpenAPI slice is **not** used for code generation in v1 — the frontend's types are hand-written Zod, deliberately kept in lock-step with the slice file. A future task may switch to generated types if drift becomes an issue.
