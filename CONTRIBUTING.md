# Contributing to CodeMafia

## Phase 1 consolidation

The user's 2026-11-17 instruction consolidates all remaining Phase 1 work on
`jiya`. Priyanshi's frontend commits and Michael's CI commit were merged there
with authorship preserved. Other branches remain available. Subsequent work
must use the agreed branch/owner workflow; this consolidation does not silently
assign later gameplay tasks to someone else.

`main` receives reviewed PRs with required checks passing. Do not force-push,
delete or rewrite another person's branch, overwrite uncommitted work, or merge
an unreviewed PR. The shared rules require all-four approval recorded in
[DECISIONS.md](docs/DECISIONS.md); implementation is not a substitute for consent.

## Review and weekly cadence

Open focused PRs by Thursday; a different teammate reviews Friday/weekend.
Review task acceptance, changed files, privacy, migrations, dependency changes,
actual test results and integration boundaries. Record approvals on GitHub.
For this consolidation, reviewers can inspect the complete Phase 1 change in
one PR from `jiya` to `main`; existing stacked frontend PRs can be coordinated
by the team after that review, without automatically closing them here.

Required contexts are Backend tests, Frontend tests and Integration tests. Main
protection must require these checks and at least one approving teammate review.
Use ordinary merge commits to preserve integrated authorship. Do not merge just
because local tests passed or an issue checkbox was checked.

## Local work and verification

```sh
git status --short
git fetch origin
git switch jiya
git diff --check
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m ruff check backend
.venv/bin/python -m ruff format --check backend
cd frontend
npm run coverage -- --maxWorkers=2 --minWorkers=1
npm run build
```

Set CODEMAFIA_TEST_DATABASE_URL to a disposable database ending in `_test` for
the real DB suite. Without it, those tests explicitly skip. Four-player browser
verification uses npm run test:e2e as documented in Readme.md. Do not run it
against production: it creates rooms. Never present fake tests as SQL evidence.

Stage named source/docs files; exclude .env, virtual environments, browser
artifacts, credentials, private test state and dependency caches. Player tokens
travel only in Authorization headers; names render as text. Publish only the
frontend build directory. Follow DATABASE.md for explicit migration/reset and
DEPLOYMENT.md for release/rollback steps.

## PR acceptance

- Link the actual Phase 1 issues, identify pending human approval gates.
- Include exact backend/PostgreSQL, frontend, browser and CI results.
- Describe schema version, seed behavior and release/rollback steps.
- State remaining Phase 2 placeholders and public deployment blockers accurately.
- Request a different person's review; never manufacture their approval.
