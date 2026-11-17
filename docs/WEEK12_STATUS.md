# Week 12 — Jiya roles, role UI and role tests

Tasks CM-12-JI-1 through CM-12-JI-3, 2026-11-16 to 2026-11-22. Work is on `jiya`,
starting from Phase 1 main commit 7bb206b. No change to main is part of this task.

| Task | Delivered implementation | Verification |
|---|---|---|
| CM-12-JI-1 Secret roles | Existing secure server shuffle retained; authenticated caller-private `/state`; SQL selects only caller role; strict five-field DTO | All four distinct roles, no assignment map/other identities/tokens, auth/cross-room/spoof/failure/game-over boundaries |
| CM-12-JI-2 Role UI | Lobby start routes all clients to live role page; explicit reveal/hide, loading/error/retry; retained-seat resume | Real four-client browser test, mobile layout, role identity binding, refresh preserves role and hides it again |
| CM-12-JI-3 Role tests | Authenticated duplicate joins rejected without changing identity/capacity/roles; refresh never registers; non-host start denied | Unit, PostgreSQL, frontend and browser happy/negative paths; stale/out-of-order credential responses cannot display prior player’s role |

## Verification register

- Backend: 186 passed, including 37 real PostgreSQL/application tests, with the
  disposable database URL set; no database tests
  skipped. One existing upstream Starlette HTTPX test-client deprecation warning.
- Frontend: 121 tests passed in seven files, including identity changes and late-response privacy tests.
- TypeScript and production build: passed.
- Browser integration: passed with four isolated clients, exactly one of each
  private role, mobile layout, refresh/hide/resume, fifth-player rejection, duplicate
  registration prevention and unauthorized-start rejection. The mobile role screen
  was also visually inspected using controlled test data.
- Remote CI: all three workflows passed on implementation commit `1d575c9`:
  [Backend CI](https://github.com/jgb23002/CodeMafia/actions/runs/44166307108),
  [Frontend CI](https://github.com/jgb23002/CodeMafia/actions/runs/44166307053),
  [Integration CI](https://github.com/jgb23002/CodeMafia/actions/runs/44166307016).
  [Branch comparison](https://github.com/jgb23002/CodeMafia/compare/main...jiya)
  shows the Week 12 change; later documentation pushes rerun the same checks.

No new database migration is needed; existing role_assignments already stores
one immutable role per player/session. Rejoin means using the retained bearer
credential, not recovering a lost credential by display name. Anonymous duplicate
names still represent distinct identities; authenticated duplicate joins return
ALREADY_JOINED. Tokens remain out of URLs and logs, and real roles are not persisted
in browser storage. Client-only mock state is demo data and is not a security boundary.

Timers, challenge/vote/sabotage actions and public results/history remain outside
these three tasks. Candidate rule approval is not fabricated by this implementation.
