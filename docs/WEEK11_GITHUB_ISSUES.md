# Proposed Week 11 GitHub issues

**Status: PROPOSED; none created by this work.** Twelve issue drafts, three per
member, balance ownership. `W11-01` etc. are planning labels, not GitHub issue
numbers. Assign real GitHub accounts manually after confirming their handles.
Use `.github/ISSUE_TEMPLATE/feature_task.md`, paste the scope/criteria/tests,
link actual dependencies, and request a different member's review.

## W11-01 — Architecture and shared API contracts

Owner Jiya; branch `jiya`. Scope: MVP/spec/API and ownership boundaries.
Dependencies: team proposal and policy review.

- [ ] SPECIFICATION.md, API.md and docs/ARCHITECTURE.md are consistent.
- [ ] All required game rules, security boundaries and endpoints are documented.
- [ ] Unapproved choices are PROPOSED; unimplemented endpoints are PLANNED.
- [ ] Different member reviews contracts; decisions recorded before integration.

Tests/evidence: document/link review; compare session OpenAPI against implemented
contracts. Local drafts exist; issue/review/approval remain pending.

## W11-02 — Standalone multiplayer sessions and tests

Owner Jiya; branch `jiya`. Scope: create/join/lobby/start and persistence protocol.
Dependencies: W11-01; production integration depends on W11-07 and W11-10.

- [ ] Host/token creation, capacity four, host-only start and four private roles.
- [ ] Collision retries, auth failures, duplicate starts and atomicity are tested.
- [ ] Router accepts dependency injection; no competing app/schema is created.
- [ ] Fake-only results and remaining PostgreSQL gates are explicit.

Tests: `python -m pytest backend/tests -q -p no:cacheprovider`; include exact
results and `docs/SESSION_INTEGRATION.md`. Local implementation exists; review pending.

## W11-03 — Leadership, review workflow and QA

Owner Jiya; branch `jiya`. Dependencies: all member handoffs and team review.

- [ ] PR/issue templates, weekly checklist/status and CONTRIBUTING.md are usable.
- [ ] Twelve issues are approved/assigned in GitHub; no fake issue numbers.
- [ ] Main protections and merge policy are reviewed and verified separately.
- [ ] Thursday PR / Friday-weekend review cadence and blockers are tracked.

Tests/evidence: templates reviewed; actual issue URLs and protection evidence
added after authorized GitHub actions. Documents exist; GitHub actions are pending.

## W11-04 — React and TypeScript foundation

Owner Priyanshi; branch `priyanshi`. Dependencies: W11-01/W11-10 API base contract.

- [ ] React/TypeScript app runs with documented setup and scripts.
- [ ] Home, lobby, role, challenge, voting and results route placeholders exist.
- [ ] Shared API client supports JSON errors without logging tokens.
- [ ] Original project structure is preserved; optional features excluded.

Tests/evidence: owner supplies actual install/build/type-check commands and output.
No frontend scripts or files beyond the original placeholder are supplied by Jiya.

## W11-05 — Create/join lobby UI and session integration

Owner Priyanshi; branch `priyanshi`. Dependencies: W11-02/W11-04/W11-07/W11-10.

- [ ] Name/code forms handle validation, loading, unknown/full/started-room errors.
- [ ] Authenticated lobby shows host, safe players and four-player capacity.
- [ ] Host-only start controls reflect server state; client cannot choose roles.
- [ ] Refresh never auto-registers a duplicate; token handling policy is reviewed.
- [ ] Four-browser session flow is demonstrated against the integrated backend.

Tests/evidence: Vitest/interaction tests and four-client smoke evidence; role-screen
integration may remain blocked by the PLANNED `/state` endpoint and must be recorded.

## W11-06 — Frontend tests and safe UI states

Owner Priyanshi; branch `priyanshi`. Dependencies: W11-04/W11-05.

- [ ] Vitest setup covers forms, errors, host controls and lobby rendering.
- [ ] Role/token/answer fields are not rendered in public player lists.
- [ ] Display names render as text; API failures have accessible messages.
- [ ] Document real test/build/type-check results and integration limitations.

Tests/evidence: owner documents actual Vitest/build commands once the manifest exists.

## W11-07 — PostgreSQL models, migrations and session adapter

Owner Gabriella; branch `gabriella`. Dependencies: W11-01/W11-02 interface.

- [ ] Logical session/player/role requirements map to reviewed production models.
- [ ] Token-hash/code/role uniqueness and host/session membership constraints exist.
- [ ] Adapter implements every transaction protocol operation with real row locks.
- [ ] Migrations apply to an empty disposable database; commands are documented.
- [ ] No raw tokens or answer keys are exposed through public models.

Tests/evidence: migration output and repository conformance tests against PostgreSQL.
Jiya supplies only the protocol, not physical models or migration commands.

## W11-08 — Ten predefined challenge seeds

Owner Gabriella; branch `gabriella`. Dependencies: W11-01/W11-07.

- [ ] Five coding and five escape challenges support one of each per round.
- [ ] Prompts/type/pairing are distinct from server-only answer keys.
- [ ] Seed procedure is repeatable without duplicate definitions.
- [ ] Answer-normalization/retry/timer decisions are flagged for approval.

Tests/evidence: seed tests count ten unique challenges and five of each type;
public serialization tests hide answer keys. Full challenge engine is later work.

## W11-09 — Database integrity, concurrency and persistence tests

Owner Gabriella; branch `gabriella`. Dependencies: W11-07/W11-08/W11-02.

- [ ] Real constraints reject duplicate codes, credentials and role assignments.
- [ ] Concurrent joins/start use distinct DB connections, then separate workers.
- [ ] Partial insert/start/commit failures roll back; exactly four roles persist.
- [ ] Restart/reconnect preserves authorized session state and seeded data.
- [ ] Tests use disposable databases and never modify production data.

Tests/evidence: real PostgreSQL test counts, migration version and restart evidence.
Passing fake tests cannot close this issue.

## W11-10 — FastAPI foundation and session mounting

Owner Michael; branch `michael`. Dependencies: W11-01; session mounting needs
W11-02/W11-07. Scope: shared app/config/errors and dependency lifecycle.

- [ ] App starts with health endpoint and documented environment requirements.
- [ ] Shared errors follow API envelope without diagnostics/credential leakage.
- [ ] Shared engine/adapter lifecycle mounts `/api/sessions` once.
- [ ] CORS, request limits, redacted logs and rate-limit plan are documented.
- [ ] Integrated session API checks run against the real adapter.

Tests/evidence: owner-provided startup/test commands, health and route/OpenAPI checks.

## W11-11 — Continuous integration foundation

Owner Michael; branch `michael`. Dependencies: W11-02/W11-04/W11-07/W11-10.

- [ ] PR workflows run relevant backend/frontend checks with documented versions.
- [ ] DB integration uses isolated PostgreSQL, not application production secrets.
- [ ] Checks expose stable names that Jiya can select for branch protection.
- [ ] Failing checks prevent recommended merge; limitations/skips are visible.

Tests/evidence: actual successful and intentionally failing workflow runs. No
workflow or required-status setting is created by the Jiya session component.

## W11-12 — Deployment foundation and environment handoff

Owner Michael; branch `michael`. Dependencies: W11-04/W11-07/W11-10 and team platform choice.

- [ ] Proposed hosting/TLS/frontend/API/database topology and costs are reviewed.
- [ ] Environment/secrets setup and health checks are documented without real secrets.
- [ ] Migration/startup/rollback responsibilities and commands are coordinated.
- [ ] Deployment gaps are tracked; do not label the full game deployed this week.

Tests/evidence: approved platform plan and minimal staging readiness/smoke evidence
when deployment is authorized. Full production release remains Week 14.

## Manual GitHub issue steps (not performed)

1. First push `jiya` and open its PR only when Jiya approves. Templates become
   available through GitHub's default-branch UI after their reviewed merge into main.
2. Before that merge, choose **Issues → New issue → Blank issue** and paste each
   draft manually. Afterward choose the **Feature task** template.
3. Create each of the twelve issues, set its actual assignee, week/permanent branch,
   scope, dependencies and acceptance criteria. Create labels/milestones only after
   team approval; these planning IDs are not labels that already exist.
4. Record actual issue numbers/URLs in weekly status and PR descriptions. Coordinate
   by Thursday and request a different member's review. Do not close integration
   issues until their real acceptance evidence exists.

Authenticated `gh` tooling was available during repository inspection, but no
GitHub mutation is authorized for this work. Availability does not mean issues,
protections, workflows, approvals, PRs or deployments have been created.

## Manual main-protection and merge-policy steps (not performed)

An administrator should review the policy, then open repository **Settings →
Branches → Add branch protection rule** (or an equivalent active ruleset) for
the exact branch `main`:

1. Require a pull request, at least one approving review from a different person,
   dismissal of stale approvals and resolution of review conversations.
2. Require relevant status checks after Michael's workflows exist and have run;
   select their actual names, never guessed or nonexistent checks. Agree whether
   branches must be up to date before merging.
3. Block force pushes and branch deletion. Apply the rule to administrators where
   available and review bypass permissions. Check account/repository plan support
   if the controls are unavailable; do not claim protection without verifying it.
4. Prefer ordinary PR merge commits for permanent personal branches, pending team
   approval. Avoid a conflicting linear-history rule and automatic head-branch
   deletion. Review available merge methods in Settings → General → Pull Requests.
5. Verify the saved rule with a separate reviewer, record evidence, and confirm an
   unreviewed/failed-check PR cannot be merged. Keep main as the default branch.

See [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
for the controls. Documentation and recommendations above do not change settings.
