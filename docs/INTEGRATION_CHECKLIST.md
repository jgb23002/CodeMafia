# Weekly integration and QA checklist

Check a box only with evidence and owner/reviewer names. A template, fake test,
or proposed issue is not evidence of a deployed or database-integrated feature.
Current status is in [WEEKLY_STATUS.md](WEEKLY_STATUS.md).

## Week 11 — foundations and lobby

- [x] Jiya: MVP/spec/API/architecture drafts document scope and proposed decisions.
- [x] Jiya: standalone create/join/lobby/start component and fake-backed tests.
- [x] Jiya: repository protocol, integration handoff, PR/issue/QA documents.
- [ ] Team: approve proposed rules and review Jiya's PR into main.
- [ ] Priyanshi: React/TypeScript setup, routes, lobby and private role-screen contract.
- [ ] Priyanshi: create/join/start states, errors, safe token handling and UI tests.
- [ ] Gabriella: PostgreSQL models, constraints, migration and repository adapter.
- [ ] Gabriella: ten predefined challenges (five coding/five escape), private keys.
- [ ] Gabriella: real DB tests for constraints, rollback, persistence and concurrency.
- [ ] Michael: FastAPI bootstrap, health, shared errors/configuration, dependency lifecycle.
- [ ] Michael: mount session router and run real adapter/API integration tests.
- [ ] Michael: CI and deployment foundation; secrets supplied outside Git.
- [ ] Jiya/team: create/assign approved issues, configure reviewed main protections.
- [ ] Team: four-client lobby/create/join/start smoke test with private roles.

**Definition of done:** reviewed foundation PRs merged; four clients use the real
backend/PostgreSQL lobby; exactly four can start; unique roles are private;
frontend/backend/DB checks pass. Fake-only session tests do not finish this gate.

## Week 12 — core gameplay (pending)

- [ ] Team: approve timers, penalties, retries, disconnect/reconnect, abstention,
  phase advancement, sabotage duration and concurrent win ordering.
- [ ] Gabriella/coordinated owner: one coding + one escape challenge each round.
- [ ] Gameplay owners (to assign): server answer validation, unique progress,
  wrong-answer penalties and immediate eight-solve win.
- [ ] Gameplay owners: Mafia-only sabotage, three per match/one per round.
- [ ] Gameplay owners: discussion/readiness, phase transitions, five-round limit.
- [ ] Gameplay owners: suspicion voting without elimination in rounds 1–2.
- [ ] Gameplay owners: round 3+ strict majority of all active players; ties yield none.
- [ ] Gameplay owners: eliminated-player action rejection and duplicate-action safety.
- [ ] Gameplay owners: all wins/early termination and atomic result persistence.
- [ ] Priyanshi: challenge/voting/sabotage/results screens integrated and tested.
- [ ] Michael: shared game-state/API integration and CI checks for added features.

**Definition of done:** a complete match follows every required phase/rule,
terminates correctly, and persists results; backend and frontend tests cover
success/failure/boundary cases. Ownership for unspecified gameplay work must be
agreed before implementation, not inferred from this checklist.

## Week 13 — integration and feature freeze (pending)

- [ ] Team: run a complete game in four independent browser sessions.
- [ ] Team: verify auth/membership, no other-player roles or answer keys leaked.
- [ ] Team: verify real DB races, duplicate requests, phase closure and restarts.
- [ ] Team: verify agreed refresh/reconnect/disconnect and timer behavior.
- [ ] Priyanshi: accessibility, loading/errors and responsive UI regression checks.
- [ ] Gabriella: completed history retained after backend/database restart.
- [ ] Michael: deployed staging smoke tests, CORS/TLS/log redaction/rate limits.
- [ ] Jiya: triage bugs, assign owners/severity, collect reproduction/test evidence.
- [ ] Team: feature freeze; no stretch features; fix critical/high-severity bugs.
- [ ] Different reviewers approve every PR and verify final diffs/checks.

**Definition of done:** full four-browser flow is repeatable, security and
persistence gates pass, critical/high bugs are resolved or explicitly accepted
by the team, and feature scope is frozen.

## Week 14 — deployment and demonstration (pending)

- [ ] Michael: reviewed production deployment, environment secrets and health checks.
- [ ] Gabriella: production migrations, backup/restore and durable match history.
- [ ] Priyanshi: deployed frontend points to the approved backend and handles failures.
- [ ] Team: final public-URL four-player smoke test and automated regression suite.
- [ ] Jiya: current setup/API/architecture, known limitations and contribution record.
- [ ] Team: presentation, demo rehearsal, roles, recovery plan and course deliverables.
- [ ] Team: final reviewed release and evidence captured; no credentials in artifacts.

**Definition of done:** the deployed MVP is accessible, tested, documented,
durable and demonstrable by all members, with all nonnegotiable rules met.

## Every PR / integration gate

- [ ] Thursday PR from the owner's permanent branch into main; linked issue.
- [ ] Acceptance criteria and proposed-policy changes documented.
- [ ] Relevant tests run; counts, warnings and fake/DB distinctions recorded.
- [ ] API/migration compatibility reviewed by affected owners.
- [ ] No secrets, private role leaks, answer-key leaks or generated artifacts.
- [ ] Different teammate approves on GitHub; conversations/checks resolved.
- [ ] Friday/weekend merge coordinated using the approved consistent merge policy.
- [ ] Each member syncs their own permanent branch with main after review/merges.
