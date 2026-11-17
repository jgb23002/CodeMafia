# CodeMafia: Escape the System

CSE 4095 — Agentic Programming. A four-player social-deduction game combining
Mafia, coding challenges, and escape-room puzzles.

Phase 1 is consolidated on `jiya`, including Priyanshi's frontend and Michael's
original CI commit. React/TypeScript + FastAPI + PostgreSQL now support a real
create/join/four-player/start flow. Gameplay screens remain Phase 2 placeholders.
The four-person rule approval and PR review are separate human acceptance gates.

## Local setup

Requires Python 3.11+, Node 22+ and a running PostgreSQL 16 server. Commands below
run from the repository root on macOS/Linux. PostgreSQL's `createdb` must connect
to a role allowed to create databases; set connection environment variables if
your server needs a host, port, user, or password. Never commit real credentials.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cp .env.example .env
createdb codemafia
createdb codemafia_test
# Edit .env to match your own PostgreSQL connection.
.venv/bin/python -m backend.app.db migrate up
.venv/bin/python -m backend.app.db seed
.venv/bin/python -m backend.app.db check
.venv/bin/python -m uvicorn backend.app.main:create_app --factory --env-file .env --reload
```

Backend: http://localhost:8000; health: http://localhost:8000/health;
OpenAPI: http://localhost:8000/docs. Startup fails safely if PostgreSQL or the
migration is missing. Migrations run explicitly, never inside request handling.

In a second terminal:

```sh
cd frontend
npm ci
cp .env.example .env
# Set VITE_USE_MOCK_API=false and VITE_API_URL=http://localhost:8000 in frontend/.env.
npm run dev
```

Open http://localhost:5173 in four independent browser contexts, create a room,
join three players, and start as host. `VITE_USE_MOCK_API=true` instead runs the
original standalone mock, including expired/full-room demo codes. Real Phase 1
rooms do not expire automatically. A seat is retained in sessionStorage on
refresh; closing the tab loses it. There is no real leave/reconnect endpoint.

## Verification

Unit tests can run without a database. PostgreSQL tests use a fresh schema per
test and refuse database names that do not end in `_test`. Export the test URL
explicitly; `.env` is not automatically loaded by the pytest fixtures.

```sh
export CODEMAFIA_TEST_DATABASE_URL=postgresql://localhost:5432/codemafia_test
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m ruff check backend
.venv/bin/python -m ruff format --check backend
cd frontend
npm run coverage -- --maxWorkers=2 --minWorkers=1
npm run build
npx playwright install chromium
```

For the real four-player browser test, migrate/seed a disposable database first,
then run from `frontend/`:

```sh
export CODEMAFIA_DATABASE_URL=postgresql://localhost:5432/codemafia_test
export CODEMAFIA_PYTHON="$(pwd)/../.venv/bin/python"
npm run test:e2e
```

This starts its own backend/frontend on ports 18000/15173 and closes them after
testing. Do not point browser tests at production: they create real test rooms.
CI runs backend/PostgreSQL tests, frontend unit/build checks, and browser integration.

## Project guides

- [Rules and state machine](SPECIFICATION.md), [HTTP contracts](API.md)
- [Complete candidate decisions and team sign-off](docs/DECISIONS.md)
- [Database, challenges, migration and reset guide](DATABASE.md)
- [Architecture](docs/ARCHITECTURE.md), [session integration](docs/SESSION_INTEGRATION.md)
- [Deployment checklist and blockers](docs/DEPLOYMENT.md)
- [Phase 1 acceptance and verification](docs/PHASE1_STATUS.md)
- [Contribution/review workflow](CONTRIBUTING.md), [weekly checklist](docs/INTEGRATION_CHECKLIST.md)

Team: Jiya Gorasiya, Priyanshi Sitlani, Gabriella Luciani, Michael Garcia.
Changes to `main` require a reviewed PR and successful required checks.
