# CodeMafia frontend

React 18 + TypeScript (strict) + Vite, React Router v6, Vitest + React Testing Library.
Owner: Priyanshi. Covers the Week 11 foundation and lobby. Role, challenge, vote and
result screens are placeholders until later weeks.

## Run it

Requires Node 20+.

```sh
cd frontend
npm install
cp .env.example .env     # mock API with bots, see below
npm run dev              # http://localhost:5173
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check, then production build into `dist/` |
| `npm run typecheck` | `tsc --noEmit` only |
| `npm test` | Run the Vitest suite once |
| `npm run test:watch` | Vitest in watch mode |
| `npm run coverage` | Tests with a v8 coverage report (`coverage/`) |

## Mock API vs real API

The UI talks to a `GameApi` interface ([src/api/types.ts](src/api/types.ts)) with two
implementations, chosen in [src/api/index.ts](src/api/index.ts) from `.env`:

| Variable | Default in `.env.example` | Meaning |
|---|---|---|
| `VITE_USE_MOCK_API` | `true` | `true` = in-memory mock ([mockApi.ts](src/api/mockApi.ts)); anything else = real HTTP ([httpApi.ts](src/api/httpApi.ts)) |
| `VITE_MOCK_BOTS` | `true` | Mock only: fake players join a new room every ~1.5s so one tab can fill a lobby |
| `VITE_API_URL` | `http://localhost:8000` | Real API base URL; requests go to `${VITE_API_URL}/api/sessions…` |

**Switching to the real backend:** set `VITE_USE_MOCK_API=false`, point `VITE_API_URL` at
the FastAPI server, and restart `npm run dev` (Vite reads `.env` only at startup). The
backend must allow the frontend origin via CORS.

The HTTP client follows Jiya's session contract in `API.md` (create, join, lobby and start).
There is **no leave endpoint yet**, so in real mode "Leave room" only clears this tab's
seat locally.

### Playing with several tabs

Each browser tab is a separate player: its seat (room code, player ID, name and private
token) lives in `sessionStorage`, so refreshing keeps your seat. The mock keeps rooms in
`localStorage`, which all tabs on the same origin share. To test four human players, set
`VITE_MOCK_BOTS=false` and open four tabs. To reset the mock, clear the site's local storage.

### Seeded demo codes (mock only)

| Code | Behavior |
|---|---|
| `PACKED` | Room is full → "That room already has 4 players…" |
| `EXPRD9` | Room expired → "That room has expired…" (expiry is PROPOSED, not in the backend) |
| `STARTD` | Game already started → "That game has already started…" |
| any other valid code | Room not found |

The mock also enforces the backend's rules: 4-player cap, duplicate names allowed,
host-only start, exactly 4 players to start, no joining a started room, and token auth.

## Structure

```
src/
  api/         GameApi types, HTTP client, mock, error messages, ApiProvider
  components/  Button, TextField, Spinner/LoadingState, ErrorState, Banner
  hooks/       useMutation (pending/error), useRoom (2s polling)
  lib/         validation (room codes, names)
  pages/       Home, Lobby, placeholders, 404
  session/     SessionProvider (this tab's seat)
  styles/      tokens.css (design tokens), global.css, components.css
  test/        test setup and render helpers
```

Tests inject a fake `GameApi` through `<ApiProvider>` (see
[src/test/renderApp.tsx](src/test/renderApp.tsx)), so no network or timers are needed.

## Security notes

- The player token is stored in `sessionStorage` and sent only in the
  `Authorization: Bearer` header. It never appears in URLs or logs. The team has not yet
  approved a token storage policy.
- Player names are rendered as React text, never as HTML.
