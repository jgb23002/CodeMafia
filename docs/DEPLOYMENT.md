# Phase 1 deployment spike

The assignment permits a deployment checklist with blockers instead of a public
preview URL. This change supplies a native deployment path exercised locally
with PostgreSQL 16, Python 3.11 and Node 24; CI exercises Ubuntu/Python 3.12/Node 22.
No paid service, public deployment, domain, or live production database is created.

## Backend deployment procedure

1. Check out the reviewed `jiya` commit on a machine with Python 3.11+ and PostgreSQL 16.
2. Create a dedicated database and deployment database role. Provide the connection
   as CODEMAFIA_DATABASE_URL through a secret store; never put it in a commit or public link.
3. Install `backend/requirements.txt` in the service environment.
4. Back up an existing database; run `python -m backend.app.db migrate up`, then
   `python -m backend.app.db seed` once as a release step, then `... db check`.
5. Start `python -m uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000`.
   A platform may substitute its assigned PORT. Do not use --reload in deployment.
6. Configure the exact HTTPS frontend origin through CODEMAFIA_CORS_ORIGINS.
7. Configure /health as the readiness URL; route traffic only after its SQL and
   schema checks pass. Provision/restart policies must preserve the database.

Local setup and disposable reset instructions are in Readme.md and DATABASE.md.
The API refuses startup with missing migrations; it never auto-migrates per worker.

## Frontend deployment procedure

1. Use Node 22+, working directory `frontend`, and run `npm ci`.
2. Set VITE_USE_MOCK_API=false, VITE_MOCK_BOTS=false and VITE_API_URL to the final
   HTTPS backend origin before `npm run build`. These are build-time values.
3. Publish only `frontend/dist` to a static host. Configure SPA fallback so paths
   such as /room/ABC234 return index.html. Never publish the repository root,
   backend/data, .env files, private answer keys or dependency caches.
4. Verify /, room routes and create/join/start in four isolated browser contexts.
   Vite preview is a local verification server, not the public hosting service.

## Acceptance checks

- [x] Versioned schema applies to a new disposable PostgreSQL database.
- [x] Ten deterministic challenge definitions seed repeatably.
- [x] Application starts with the real adapter and mounts the session routes; Week 12 adds caller-private /state.
- [x] SQL /health, configured CORS, global errors and body limits are tested.
- [x] Real database tests cover distinct-process joins and durable result read/write.
- [x] Four-player browser and backend/database restart evidence recorded in PHASE1_STATUS.md.
- [ ] Public HTTPS host, static SPA routing and actual platform readiness verified.

## Public release blockers

No public host/account, domain, secret store, backup schedule or spending decision
has been selected. Before exposing the API publicly, configure TLS, ingress rate
limits/body limits, database access restrictions, backups/restore rehearsal,
credential redaction, monitoring and an approved expiry/retention policy. The
complete gameplay engine is Phase 2 and is not implied by this Phase 1 spike.

For rollback, restore the previous reviewed application version if its schema is
compatible. Do not automatically run the destructive initial down migration in
production; review a database restore/migration plan first.
