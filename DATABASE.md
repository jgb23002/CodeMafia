# PostgreSQL database and challenge content

Phase 1 uses PostgreSQL 16 and psycopg 3. The schema, adapter, seed content and
real database tests are consolidated on `jiya` by the owner's request.

## Schema

| Table | Purpose and key constraints |
|---|---|
| sessions | UUID PK, unique six-character room code, same-room host, valid phase/round/lifecycle, UTC timestamps |
| players | UUID PK, session FK, display name, globally unique private SHA-256 token digest, active flag |
| role_assignments | Session/player composite PK, same-room player FK, one of each role per session |
| challenges | Stable CM01–CM10 IDs, coding/escape type, round 1–5, unique round/type, private JSON answer key |
| attempts | UUID PK, same-room author, challenge FK, private answer, correctness, timestamp |
| challenge_completions | Unique session/challenge pair prevents double-counted progress; same-room solver |
| votes | Unique session/round/voter, same-room voter and target, no self-votes |
| results | One result/session, winner, reason, solved count, rounds played, completion timestamp |
| schema_migrations | Applied migration versions, SHA-256 checksums and timestamps |

`backend/migrations/001_initial.up.sql` is the executable schema. Its down file
reverses it. A deferred composite FK resolves the session/host insertion cycle
and enforces host membership at commit. Roles, votes and attempts enforce room
membership using composite FKs. All application queries are parameterized.

## Setup, migration and repeatable seeds

Set CODEMAFIA_DATABASE_URL in the ignored root `.env` or process environment.
See `.env.example`; supply real passwords through your own environment/secret store.

```sh
.venv/bin/python -m backend.app.db migrate up
.venv/bin/python -m backend.app.db seed
.venv/bin/python -m backend.app.db check
.venv/bin/python -m backend.app.db migrate status
```

Migration transactions use an advisory lock. Applied checksums cannot silently
change. New schema changes require a new numbered migration. Startup checks the
expected version; it never applies migrations automatically.

`backend/data/challenges.json` is a server-only versioned format containing ten
deterministic questions: five coding and five escape, one pair per round. Keys
are objects with an `accepted` array of exact strings. Checking trims only outer
whitespace and never executes submitted code. Seeding twice inserts zero new
rows on the second run; changed existing definitions require a reviewed migration.
`public_challenges()` selects only id/kind/round/prompt, excluding the answer key.
The frontend does not import the seed file and public OpenAPI does not expose it.
Challenge play/submission endpoints belong to Phase 2.

## Transactions and persistence

`PostgresRepository` opens a fresh connection at READ COMMITTED per operation.
Create inserts room+host in one transaction. Join/start lock the same session
row with FOR UPDATE before reading members or changing phase. Lobby reads hold
FOR SHARE until their safe snapshot is built. The adapter commits before a
successful response and rolls back failed statements, domain failures and commit
failures. Only named code/identity constraints are translated into retryable
collisions; other SQL failures remain safe persistence errors.

`MatchRepository.record_result()` locks the active session and atomically stores
its result plus GAME_OVER state. Duplicate finalization cannot overwrite history.
`read_result()` works on a new connection/process. This is internal persistence,
not a client endpoint or a completed gameplay/win-resolution engine.

## Real database tests

```sh
export CODEMAFIA_TEST_DATABASE_URL=postgresql://localhost:5432/codemafia_test
.venv/bin/python -m pytest backend/tests -m postgres -q
```

Tests require a disposable database ending in `_test`, create isolated random
schemas, and drop only those schemas. They cover migrations/rollback, immutable
seeds, schema constraints, separate-process capacity, simultaneous starts,
join/start races, shared locks, partial-write and deferred-commit failures,
private DTOs, application health/CORS/errors, and durable result read/write.
No database URL means explicit skips; CI supplies the URL and runs the real suite.

## Rollback/reset: disposable databases only

The down command drops application tables and data. Back up real databases and
review an additive migration/restore plan before any production schema change.
A disposable local reset is:

```sh
.venv/bin/python -m backend.app.db migrate down --allow-data-loss
.venv/bin/python -m backend.app.db migrate up
.venv/bin/python -m backend.app.db seed
```

A later application release must not run against schema version 0. This initial
schema is the Phase 1 baseline; gameplay changes can add numbered migrations.
