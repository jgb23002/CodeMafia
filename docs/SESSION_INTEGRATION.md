# Integrated session component

The session router is mounted in `backend.app.main:create_app`. It receives a
shared SessionService backed by PostgresRepository; each operation opens its
own transaction/connection. There is no shared mutable transaction or production
fake. Run the documented commands in [Readme.md](../Readme.md).

## Live routes

- POST /api/sessions — room plus host, returns this player's private token.
- POST /api/sessions/{code}/join — registration while waiting and below capacity.
- GET /api/sessions/{code} — authenticated safe lobby, no roles or credentials.
- POST /api/sessions/{code}/start — host only, exactly four active players, one start.
- GET /health — SQL readiness and expected schema version.

The router already includes /api/sessions; do not mount another /api prefix.
Session DTOs retain their original snake_case shapes, which the frontend HTTP
adapter maps to its camelCase types. The UI can use mocked or real endpoints.
Use explicit CORS origins matching the frontend scheme/host/port exactly.

## Persistence contract

See [DATABASE.md](../DATABASE.md) and sessions/repository.py. Join/start writers
lock the session row before counting/reading fresh members. Lobby reads hold a
shared row lock. A deferred host-membership FK permits atomic room+host creation.
Only a room-code unique violation retries a code; only generated ID/token unique
violations retry identity. Other database failures produce safe persistence
errors. Failed transactions fully roll back before retries.

There is no automatic replay after an uncertain commit outcome. Registration
POSTs are non-idempotent; the client never automatically re-registers on refresh.
A lost tab cannot transfer its token to a new seat. No leave/expiry endpoint is
implemented. These limitations are reflected in the frontend guide and rules.

## Verified gates

Use the exact commands in Readme.md and PHASE1_STATUS.md. The backend suite has
fake unit tests plus real PostgreSQL tests for row locks, separate-process
capacity, concurrent starts, join/start races, schema constraints, rollback,
deferred-commit failure and persistent match storage. Application tests mount
the real router and check health, errors, body bounds, CORS and safe OpenAPI.
The browser test creates four isolated players through the real HTTP adapter,
refreshes one seat, rejects a fifth player and moves all four to the role placeholder.

## Boundaries for Phase 2

The start response reveals only the host's own role. Non-host private role
retrieval through /state, gameplay timers, answer/vote/sabotage APIs, public
results and the win-resolution engine remain planned. Role/challenge/vote/result
screens deliberately remain placeholders for the later phase. Completed match
storage can be tested internally without exposing a client winner-setting API.
