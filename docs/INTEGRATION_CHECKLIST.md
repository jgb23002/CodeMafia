# Weekly integration and QA checklist

Record actual evidence, not inferred approvals. Current results and GitHub links
are in [PHASE1_STATUS.md](PHASE1_STATUS.md).

## Phase 1 / foundation and lobby

- [x] Complete candidate rules, HTTP contracts, error shapes and shared state machine.
- [x] Create/join/lobby/start with capacity four, host-only start, private assignments.
- [x] React/TypeScript routes, layout, state hooks and live/mock adapters.
- [x] Lobby validation/full/expired-mock/loading/error/waiting states and unit tests.
- [x] PostgreSQL schema, FK/uniqueness constraints, versioned migration and rollback.
- [x] Ten deterministic challenge definitions with server-only answer keys.
- [x] Real database tests for schema/seeds/transactions/concurrency/persistence.
- [x] Runnable FastAPI app, configuration, SQL /health, shared safe errors and CORS.
- [x] Backend/frontend/integration workflows and environment/setup documentation.
- [x] Deployment procedure with verified local path and public-hosting blockers.
- [x] Record twelve actual GitHub issue URLs and verified required-check protections.
- [x] Record successful remote backend/frontend/integration CI and consolidated PR #17.
- [x] Record final four-browser and backend/database restart smoke evidence.
- [ ] All four members approve candidate rules themselves.
- [ ] Independent teammate approves the consolidated PR before merge.

## Phase 2 / gameplay

- [ ] Private /state for every player; timers/deadlines and server advancement.
- [ ] Coding/escape actions and unique progress with private answer checking.
- [ ] Voting, sabotage, elimination and immediate win/round-limit resolution.
- [ ] Public member-authorized results/history, completed gameplay screens.
- [ ] Real database, API, unit and four-client complete-match regression.

## Freeze and public deployment

- [ ] Complete games and results survive app/database restart under authorization.
- [ ] Record cross-browser regressions, fixes and approved scope freeze.
- [ ] Review production TLS, ingress limits, token expiry, backups and monitoring.
- [ ] Deploy to an approved host, verify public smoke and rehearse demo.
