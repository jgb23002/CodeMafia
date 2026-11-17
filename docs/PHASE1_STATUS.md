# Phase 1 acceptance and evidence

Updated 2026-11-17 (America/New_York). All implementation is consolidated on
`jiya` at the user's request. Original frontend and CI commits retain authorship.
This records delivered code and actual verification separately from human approval.

| Original owner | Assignment | Implementation evidence | Acceptance gate |
|---|---|---|---|
| Jiya | Architecture | SPECIFICATION.md, API.md, complete candidate defaults in DECISIONS.md | All four people must approve rules |
| Jiya | Sessions | Mounted create/join/lobby/start, real PostgreSQL adapter and session tests | Independent PR review |
| Jiya | Leadership/QA | README setup, templates, weekly checklist and GitHub issue/protection work | 12 assigned issues and main protection verified |
| Priyanshi | Frontend foundation | React/TypeScript, common layout, routes and hooks | Independent PR review |
| Priyanshi | Lobby UI | Live/mock adapters, capacity, create/join/start and error/waiting states | Independent PR review |
| Priyanshi | UI QA | Responsive tokens/components, loading/errors, 94 unit tests | Independent PR review |
| Gabriella | Database | DATABASE.md, versioned SQL migrations, FKs/uniqueness/lifecycle checks | Independent schema review |
| Gabriella | Content | Ten deterministic coding/escape questions, private keys, repeatable seed command | Content review |
| Gabriella | Data tests | Real PostgreSQL migrations/seeds/constraints/concurrency/persistence tests | Independent PR review |
| Michael | Backend foundation | App factory, env config, DB connection, SQL health and shared errors | Independent PR review |
| Michael | CI/environments | Backend/frontend/integration workflows, pinned backend and npm lockfile, env examples | All three workflows passed on implementation commit 0d0abb1 |
| Michael | Deployment spike | Verified local path, deployment checklist and explicit public-host blockers | No public preview claimed |

## Verification register

- Backend: 162 passed, 0 skipped with CODEMAFIA_TEST_DATABASE_URL set; one upstream
  Starlette HTTPX test-client deprecation warning. Includes real PostgreSQL tests,
  distinct-process capacity, partial-write rollback and deferred commit failure.
- Frontend: 94 unit tests passed across five files; 93.72% line coverage.
  TypeScript/production build passed. One real Chromium integration test passed
  with four independent players, refreshed seat, fifth-player rejection and host start.
- Restart smoke: stopped/restarted both the backend process and the disposable
  PostgreSQL instance. Authenticated lobby, four roles, ten challenges and an
  internal match-result fixture remained available afterward.
- Python lint and formatting passed; no production credentials are committed.
- GitHub: [12 real issues, #5–#16](WEEK11_GITHUB_ISSUES.md), assigned to original
  task owners for acceptance/review. Main protection was applied and read back:
  Backend tests, Frontend tests and Integration tests are required, branches must
  be current, one independent approval and resolved conversations are required,
  admins are included, and force-push/deletion are disabled.
- Published draft PR: [#17 — Complete Phase 1 foundation, PostgreSQL persistence and integrated lobby](https://github.com/jgb23002/CodeMafia/pull/17).
- All three push workflows passed on implementation commit `0d0abb1`:
  [Backend CI](https://github.com/jgb23002/CodeMafia/actions/runs/44155863386),
  [Frontend CI](https://github.com/jgb23002/CodeMafia/actions/runs/44155863448),
  [Integration CI](https://github.com/jgb23002/CodeMafia/actions/runs/44155863775).
  New pushes and the PR run the same checks again; inspect the PR for current-head results.

## Human acceptance still required

- All four members record their own approval of the candidate rules.
- Another teammate reviews and approves the consolidated PR.
- A reviewed merge into main occurs only after required checks pass.

No human approval, merge or public deployment is inferred from automated tests.
Gameplay state/answer/vote/sabotage/results endpoints remain Phase 2, and their
screens are still placeholders as allowed by the Phase 1 assignment.
