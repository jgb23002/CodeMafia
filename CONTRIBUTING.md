# Contributing to CodeMafia

## Permanent branches and ownership

Use only these personal branches for Weeks 11–14: `jiya`, `priyanshi`,
`gabriella`, `michael`. Each member works on their own branch and keeps it for
the project. No week/task branches. `main` receives only tested, reviewed PRs.
Never work directly on main or delete/rewrite another member's branch.

| Member | Primary responsibility |
|---|---|
| Jiya Gorasiya | Lead, architecture/API, sessions, integration/QA coordination |
| Priyanshi Sitlani | React/TypeScript, lobby and gameplay UI, frontend tests |
| Gabriella Luciani | PostgreSQL models/migrations, challenge data/validation, DB tests |
| Michael Garcia | FastAPI app/shared errors/configuration, CI/deployment foundation |

Confirm shared-file changes with the affected owner. Keep PR scope focused,
preserve placeholders until their owner replaces them, and never overwrite
uncommitted work. The initial README is retained; this document defines the
specific permanent-branch workflow for this project.

## Weekly review cadence

Each member opens their PR into main by Thursday; another person reviews it.
Review and coordinated merges happen Friday or the weekend. Check issue
criteria, tests, security, contract compatibility and the actual diff. Record
approvals on GitHub; an unchecked document box is not an approval. Sync each
personal branch with main after reviewed merges. Future milestones and owners
are in [WEEKLY_STATUS.md](docs/WEEKLY_STATUS.md).

**Recommended merge policy, pending team approval:** use ordinary PR merge
commits consistently. They preserve ancestry for these permanent branches.
Repeated squash merges can cause previously merged personal-branch commits to
reappear in later PR histories and complicate comparisons. Always inspect
`origin/main...HEAD` before approval. Do not enable a linear-history-only rule
if the team chooses merge commits. Do not automatically delete personal branches.

## Clean local workflow

Commands below are instructions, not actions performed automatically by an
assistant. Stop on unexpected changes, conflicts, failed tests, or branch names.
Do not reset, clean, stash, force-push, merge or rebase someone else's work to
make a command succeed. Ask the affected owner before destructive changes.

```sh
git status --short
git fetch origin
git switch jiya                  # use only your own permanent branch
git branch --show-current
git diff --check
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

If your personal branch does not exist, create it **once** from the verified
latest main, using its assigned name. For Jiya this was `git switch -c jiya` from
clean main at `614faaf`. Do not recreate or rename it for each assignment.

After the team's reviewed merges, with your working tree clean and the team's
merge policy approved, sync **your own branch** (do not rewrite history):

```sh
git fetch origin
git switch jiya
git merge origin/main
```

This sync example is not authorization for an assistant to merge now. Resolve
conflicts with file owners, rerun relevant tests, and verify the final diff.
Avoid `git pull` with an unknown rebase/merge configuration. Never force-push.

Stage named files and create meaningful small commits; avoid blanket staging
that could include another member's files or credentials:

```sh
git add SPECIFICATION.md API.md docs/ARCHITECTURE.md
git diff --cached --check
git diff --cached --stat
git commit -m "docs: define MVP architecture and API contracts"
```

Push and open a PR only when the owner approves doing so. For Jiya:

```sh
git push --set-upstream origin jiya
gh pr create --repo jgb23002/CodeMafia --base main --head jiya \
  --title "Complete Jiya's Week 11 architecture, sessions, and QA" --web
```

Use the PR template, link approved issues, describe production blockers, attach
exact test results, and request a different teammate's review. Verify the base
is main and the head is your personal branch. Do not merge your own unreviewed PR.

## Tests and security

Run the session suite using [SESSION_INTEGRATION.md](docs/SESSION_INTEGRATION.md).
Michael/Priyanshi/Gabriella will document their own checks as their infrastructure
arrives. No production DB integration or four-browser gameplay is implied by
passing fake tests. Never commit .env values, credentials, usable tokens, or
generated test output. Render user names as text and redact credentials in logs.

GitHub issues/settings are manual pending work, described in
[WEEK11_GITHUB_ISSUES.md](docs/WEEK11_GITHUB_ISSUES.md). Documentation does not
create issues, CI checks, protection rules, or approvals.
