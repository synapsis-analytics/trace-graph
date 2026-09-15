# TRACE Graph — frontend

The graph explorer SPA: Vite + React 18 + TypeScript, Tailwind, **sigma.js v3 + graphology** (WebGL),
TanStack Query, react-router. It talks to the TRACE HTTP API described in `docs/PLAN.md` §4 and renders
the contract node/edge shape:

```ts
node = { id, type, label, size?, band?, attrs }
edge = { id, source, target, predicate, attrs }
```

## Quick start

```bash
npm ci

# 1. Fully standalone: bundled mock API (:8432) + Vite (:5173)
npm run dev:mock

# 2. Against the real backend on :8431 (or set TRACE_API_TARGET)
npm run dev
TRACE_API_TARGET=http://localhost:8413 npm run dev

npm run lint      # eslint, 0 warnings allowed
npm test          # vitest (graph adapter + lens filter)
npm run build     # tsc -b && vite build → dist/
```

Stop the servers when you are done: `lsof -i :5173 -t | xargs kill` and `lsof -i :8432 -t | xargs kill`.

## How it reaches the API

* **Production**: FastAPI serves `frontend/dist` on the same origin, so every call is relative —
  `/api/...`, `/health`. No base URL, no CORS, no env var baked into the bundle.
* **Development**: Vite proxies to the backend. The proxy patterns are anchored on purpose:

  ```ts
  "^/api/":    → TRACE_API_TARGET (default http://localhost:8431, :8432 in `--mode mock`)
  "^/health$": → same
  "^/docs$":   → same (OpenAPI)
  ```

  A bare `"/api"` prefix would also swallow the SPA route `/api-guide`.

## The mock API (`mock/`)

`mock/server.mjs` (Express) + `mock/fixture.mjs` (deterministic generator) implement the §4 endpoints
over an invented but realistic SP01 graph: **256 objects across all 16 types, 918 links across all 16
predicates, ~940 claims**, the five lenses, taxonomy coverage with unmatched terms, a working QA gate
for `POST /api/claims` (`?dry_run=1` included) and `POST /api/claims/{id}/decide`.

```bash
node mock/server.mjs                 # :8432, write key "demo-key"
PORT=8433 MOCK_ASK=1 node mock/server.mjs   # enable a canned /api/ask answer
MOCK_LATENCY_MS=400 node mock/server.mjs    # exercise the loading states
```

`/api/ask` answers **503** by default — that is the real behaviour when no model key is configured, and
the Ask page is built to explain it rather than to fail.

## Layout

```
mock/              fixture.mjs · server.mjs
src/
  lib/             types.ts (API contract) · api.ts (fetch client) · graphAdapter.ts (API → graphology)
                   lens.ts (lens/type/predicate filtering) · theme.ts (type → colour + icon) · utils.ts · storage.ts
  hooks/useApi.ts  TanStack Query hooks + useDebounced
  components/      Layout · GraphCanvas · NodeDetailDrawer · CommandPalette · ObjectSearch · KeyDialog
                   TypeBits (badges/legend) · ui/primitives.tsx (button, badge, sheet, dialog, tabs, table…)
  pages/           Explore · PathFinder · Framework · Coverage · Registry · Ask · ApiGuide · NotFound
```

Tests live next to the code they cover (`src/lib/*.test.ts`) and run in jsdom.

## Conventions

* TypeScript strict; `any` is banned by lint. Untrusted API values are `unknown` and narrowed at the edge.
* Colour encodes **object type** only (one palette, `src/lib/theme.ts`); QA band is opacity/ring; community
  colouring is an explicit toggle that temporarily overrides type colour.
* Every list/detail view has loading, error and empty states; all search inputs are debounced (200–250 ms).
* The write key (`X-Access-Key`) and the attestor id live in `localStorage` only, set through the header
  key dialog. Nothing is written without it.
