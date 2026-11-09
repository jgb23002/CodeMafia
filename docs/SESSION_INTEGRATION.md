# Session integration handoff

## Implemented and pending

Jiya supplies `backend/app/sessions/{__init__,repository,schemas,service,router}.py`.
Four routes implement create, join, authenticated lobby, and host start, as in
sections 1–4 of [API.md](../API.md). There is no production app, repository
implementation, database engine/configuration, schema, migration, or deployment.
The only storage implementation is a test fake under `backend/tests/fakes.py`.

**Blockers:** Michael must supply the app/foundation/shared errors and dependency
lifecycle. Gabriella must supply models/migrations and a PostgreSQL adapter.
Priyanshi must connect the UI after those integrations. Non-host role retrieval
via `/state`, timers, game engine, answers, votes, sabotage, and results are PLANNED.

## 1. Run the standalone tests

From the repository root (Python 3.11+):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/tests/requirements.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest backend/tests -q -p no:cacheprovider
```

The requirements are feature-test dependencies, not the production backend
manifest. Michael should reconcile them with his shared dependency management.
The tested environment uses Python 3.13, FastAPI 0.162.2, Pydantic 2.14.3,
pytest 9.2.0 and HTTPX 0.28.1. These tests need no network or database at runtime.

All storage tests use a fresh fake per test. The fake serializes transactions
with a repository-instance RLock, checks requested lock modes, enforces modeled
uniqueness, and snapshots state for rollback/failure injection. This proves only
the service's contract and DTO/authorization behavior. It does **not** prove SQL,
actual constraints/isolation, separate-worker safety, migrations, crash recovery,
durability or real PostgreSQL integration. No real PostgreSQL tests are supplied
or claimed in this Week 11 component.

Local static QA also used Ruff 0.17.4 and PyYAML 6.0.3 in an external temporary
environment. They are optional QA tools, not production dependencies:

```sh
python -m ruff check --isolated --no-cache --select E4,E7,E9,F,I,B,BLE,RUF022 backend
python -m ruff format --isolated --check --no-cache backend
```

## 2. Michael: register the dependency and mount the router

This function can be placed in Michael's future integration layer. It creates
neither an app nor storage. Pass the existing app and Gabriella's adapter:

```python
from fastapi import FastAPI
from backend.app.sessions import (
    SessionRepository, SessionService, create_session_router,
)

def register_sessions(app: FastAPI, repository: SessionRepository) -> None:
    service = SessionService(repository)

    def get_session_service() -> SessionService:
        return service

    app.include_router(create_session_router(get_session_service))
```

Use `from app.sessions import ...` instead if launching with `backend` on
PYTHONPATH. The router already includes `/api/sessions`; do not prepend `/api`
again. Reuse one service/adapter backed by the shared engine/pool, with a fresh
connection/transaction per operation. Never share mutable transaction objects.
Synchronous routes use FastAPI's worker thread pool; do not inject an async-only
driver without an explicit adapter/design change. Engine creation/disposal is
Michael's lifespan responsibility. Do not inject the fake into deployed code.

`SessionRoute` provides feature-scoped error envelopes and no-store headers.
Michael can consolidate this with his shared infrastructure once it exists,
preserving 401 challenges, 403/404/409/422/500 codes and safe validation details.
Global 404/405 and middleware errors remain Michael's responsibility. Do not
serialize exception text or log request/response credentials. Add HTTPS/CORS,
body limits, rate limits, health checks and deployment configuration in his work.

## 3. Gabriella: implement the exact repository contract

Import domain records and persistence exceptions from
`backend.app.sessions.repository`. Domain IDs are UUID strings; phases/roles
are string enums. Physical ORM classes and names are your responsibility.

| Operation | Required semantics |
|---|---|
| `repository.transaction()` | Context manager yields a SessionTransaction; commit before success, rollback on any failure including commit failure, release resources/locks |
| `tx.create_room(room, host)` | Insert both; consistent session/host membership; no partial externally visible state |
| `tx.get_room(code, lock="exclusive")` | Lock the existing session row until transaction exit, read fresh state after waiting; absent returns None |
| `tx.get_room(code, lock="shared")` | Hold a shared row lock so the lobby's phase and member list form a consistent snapshot |
| `tx.find_player_by_token_hash(digest)` | Global indexed lookup returning Player or None; never accepts plaintext token |
| `tx.list_players(session_id)` | All room members in a stable order, including inactive members |
| `tx.add_player(player)` | Insert after exclusive room lock; enforce identity/hash uniqueness and membership |
| `tx.get_roles(session_id)` | Private mapping of player UUID strings to Role enums; do not attach roles to public DTOs |
| `tx.start_game(session_id, assignments)` | Under exclusive room lock, conditionally transition WAITING; insert four roles, set SABOTAGE/round 1 and active lifecycle status in the same transaction; reject preexisting roles; never commit internally |

Choose PostgreSQL READ COMMITTED with explicit `SELECT ... FOR UPDATE` for
membership/start, and `FOR SHARE` for lobby reads. Count/read members **after**
locking. Every future membership/phase writer must lock that same session row.
Re-evaluate after lock acquisition; do not use a stale ORM identity-map snapshot.
Do not use process-local locks or a count-then-insert outside the transaction.
If choosing stronger isolation, explicitly handle serialization retries without
duplicating actions; agree on the contract before changing the isolation policy.

Use parameterized SQL/ORM operations. Translate only the named room-code unique
constraint to `RoomCodeCollision`, generated ID/hash unique constraints to
`IdentityCollision`, failed conditional lifecycle changes to `StateConflict`,
and other database failures to `RepositoryError`. Do not misclassify arbitrary
integrity errors as code collisions. Service registration retries use a fresh
transaction, so no savepoint is required by this protocol. Failed writes must
fully roll back before retry. Domain/session errors must also roll back.

The fake's commit failure models an abort, not an ambiguous network failure after
a database may already have committed. For uncertain commit outcomes, surface a
safe RepositoryError and do not automatically replay the operation. Production
idempotency/reconciliation behavior must be designed with the pending retry and
reconnect policies; fake rollback tests cannot establish those guarantees.

## 4. Schema and migration requirements (logical, not a migration)

- Sessions: UUID PK, globally unique room code, host player association,
  phase/round/status, creation/start/completion timestamps as applicable.
- Players: UUID PK, session FK, display name, **private 64-character SHA-256
  hex token hash with a global unique index**, active flag. No raw-token field.
- Roles: session/player membership association; unique `(session, player)` and
  `(session, role)`; allowed four role values; enforce same-room ownership.
- Host membership must belong to the same session. For cyclic room/host FKs,
  choose deferred constraints or a nullable-within-transaction host link. That
  choice belongs in Gabriella's reviewed migration, not this feature.
- Enforce valid phases/round ranges and lifecycle state where practical; stored
  NEXT_ROUND is invalid. Map internal status values inside the adapter.
- Defaults for other required fields/counters; UTC timestamps; private answer
  storage never included in session queries/responses.
- Unique accepted-action/progress constraints are later gameplay requirements,
  not implemented by Jiya's session protocol.

Token digests are unsalted SHA-256 of ASCII tokens generated from 32 random bytes,
not hashes of low-entropy passwords. Persist only the digest. Hash/key format
changes need a coordinated API/adapter policy. Token expiry/reconnect/rotation
remain PROPOSED; do not silently change existing identities this week.

## 5. Production verification gate after their work arrives

1. Review model/adapter mappings and error codes against this protocol and API.md.
2. Use Gabriella's documented migration command against an **empty disposable**
   PostgreSQL database, then verify constraints and upgrade/rollback procedures.
   No migration command can be truthfully supplied until her tool/config exists.
3. Run adapter conformance tests against real PostgreSQL: creation and collision
   rollback, at least eight simultaneous joins with only three accepted, duplicate
   starts, both join/start lock orders, partial role failure and commit failure.
4. Repeat using separate connections/processes or app workers. Confirm four roles
   exactly once, capacity four, no partial writes, and no leaked private fields.
5. Restart the backend with the same PostgreSQL database and verify tokens, rooms,
   roles and completed results remain available under proper authorization.
6. Mount in Michael's test app; verify the four routes' OpenAPI, errors, no-store,
   authentication and sanitized failures. Priyanshi tests four browser sessions.

**Proposed verification command contract** for the future adapter tests (this
file does not exist yet; Gabriella/Michael must create it):

```sh
# Set CODEMAFIA_TEST_DATABASE_URL securely in your shell for a disposable DB.
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  backend/tests/test_postgres_session_repository.py -q -p no:cacheprovider
```

Expected smoke calls after Michael supplies the actual app startup command:

```sh
curl -i -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' --data '{"display_name":"Host"}'
curl -i -X POST http://127.0.0.1:8000/api/sessions/ROOM_CODE/join \
  -H 'Content-Type: application/json' --data '{"display_name":"Guest"}'
```

`ROOM_CODE` is a placeholder; substitute the generated six-character code.
Use a client that protects its Authorization header for authenticated lobby/start
checks. Do not paste real player tokens into committed documentation or logs.
Complete three joins before host start; confirm a fifth join and repeated start
fail. There is deliberately no `uvicorn` command pointing to a nonexistent app.

## 6. Acceptance and policy blockers

Team review is pending for code/name format, duplicate names, reconnect/token
lifetime/storage, and registration idempotency. Subsequent gameplay needs timer,
retry, abstention/disconnect, phase-readiness and sabotage-duration decisions.
The fake tests are a local Week 11 session gate only. Track production integration,
four-browser verification and policy approval in [WEEKLY_STATUS.md](WEEKLY_STATUS.md).
