# Weekly status — CodeMafia

Updated 2026-11-09 (America/New_York). Owner: Jiya Gorasiya, team lead.
This records local work and pending handoffs, not team approval or deployment.

## Milestones

| Week | Milestone | Current state | Evidence / exit gate |
|---|---|---|---|
| 11 | Architecture, foundation, lobby | Jiya's local scope complete; team integration pending | Spec/API, component/tests and templates; real DB/app/frontend/review still required |
| 12 | Core gameplay | Pending | Full five-phase matches, all wins, votes/sabotage/challenges and tests |
| 13 | Integration and freeze | Pending | Four-browser regression, security/restart evidence, prioritized bugs resolved |
| 14 | Deployment and demo | Pending | Production smoke tests, persistence, documentation and rehearsal |

## Per-member responsibilities and handoffs

| Member / permanent branch | Week 11 work | Status | Next handoff |
|---|---|---|---|
| Jiya / jiya | Architecture, sessions, fake tests, leadership/QA docs | Locally implemented, review pending | Contract review, push/PR approval, issue/protection coordination |
| Priyanshi / priyanshi | React setup, lobby/routes, UI tests | Pending integration; no code reviewed here | Connect four session routes and decide token UI/storage policy |
| Gabriella / gabriella | Models/migrations, adapter, ten seeds, DB tests | Missing from this checkout | Implement repository protocol and prove real PostgreSQL guarantees |
| Michael / michael | FastAPI/shared errors/config, CI/deployment foundation | Missing from this checkout | Mount router, manage engine/dependencies, run integration and CI |

Weeks 12–14: Priyanshi continues UI/testing; Gabriella persistence/challenge
validation/data; Michael shared backend/CI/deployment; Jiya sessions/integration/QA
leadership. Specific voting, sabotage, game-engine and resolution owners remain
pending team allocation; no assignments are silently transferred by this document.

## Local verification

Command (feature-test environment installed separately):

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest backend/tests -q -p no:cacheprovider
```

Latest result: **125 passed, 0 failed, 0 skipped; 1 warning**. Warning:
Starlette deprecates its HTTPX test-client integration in the tested dependency
versions. All storage-backed tests use the in-memory fake; **zero real PostgreSQL
tests ran**. API tests use only a test harness, not Michael's production app.
Environment and limitations: [SESSION_INTEGRATION.md](SESSION_INTEGRATION.md).

Static checks passed: Ruff lint and formatting for all 10 Python files,
Python parse/compile checks, JSON example parsing, local Markdown link checks,
issue-template YAML, twelve issue drafts, and whitespace checks. Final commit
identifiers are reported after the repository review. No CI run, deployment or
GitHub setting change is implied by local checks.

## Blockers and decisions

| Item | Owner | Status / required evidence |
|---|---|---|
| Production app/bootstrap, engine and shared errors | Michael | Pending; startup/health/OpenAPI evidence |
| Repository adapter/models/migrations | Gabriella | Pending; real constraints, locks, rollback and restart tests |
| Four-browser lobby/start UI | Priyanshi + team | Pending integrated backend and safe credential UI |
| Non-host role retrieval through `/state` | Coordinated backend owner | PLANNED; role view cannot rely on host start response |
| Spec/API review and proposed session policy | All members | Approval pending; name/code/token/idempotency/reconnect policy |
| Gameplay policies | All members | Timers, penalties/retries, abstention/disconnect, advancement, sabotage duration and win races pending |
| CI/check names and deployment foundation | Michael | Pending; no workflow supplied in Jiya scope |
| GitHub issues/main protection/merge policy | Jiya + administrator + reviewer | Drafts/manual steps exist; execution and verification pending |

## PR, review and approval register

| Owner | PR / base | Reviewer | Approval | Merge |
|---|---|---|---|---|
| Jiya | Not opened; intended jiya → main | Different teammate, unassigned | Pending | Pending |
| Priyanshi | Not verified | Pending | Pending | Pending |
| Gabriella | Not verified | Pending | Pending | Pending |
| Michael | Not verified | Pending | Pending | Pending |

No push, PR, issue creation, merge, rebase, branch deletion or GitHub setting
change is performed by this Week 11 work. Do not replace pending entries with
complete until actual links, reviewers and test evidence are recorded.

## Week 11 completion ledger

- [x] Original setup inspected; clean main at `614faaf` preserved.
- [x] One permanent local `jiya` branch created for all future Jiya work.
- [x] Three architecture/contract documents populated with PROPOSED/PLANNED labels.
- [x] Four-route standalone session component and transaction protocol implemented.
- [x] Fake-backed success/security/failure/concurrency tests pass.
- [x] Integration guide, templates, twelve issue drafts and contribution/QA docs.
- [ ] Different teammate reviews and approves Jiya's work.
- [ ] Owner approves push and PR; actual issue URLs and protections recorded.
- [ ] Production app, PostgreSQL adapter, frontend and CI integrated and verified.
- [ ] Four-browser game flow and production persistence verified in their phases.

Thursday PRs and Friday/weekend reviews are the recurring cadence. Follow
[INTEGRATION_CHECKLIST.md](INTEGRATION_CHECKLIST.md) for each milestone's definition
of done; document completion does not imply the full application is finished.
