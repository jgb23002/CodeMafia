# CodeMafia: Escape the System — MVP specification

CSE 4095 — Agentic Programming. Team: Jiya Gorasiya, Priyanshi Sitlani,
Gabriella Luciani and Michael Garcia.

## Scope and implementation status

Four private browser clients play a social-deduction game with coding and escape
puzzles. Phase 1 implements PostgreSQL-backed create/join/lobby/start, frontend
mock/live adapters and waiting UI, ten deterministic seeded challenges, durable
match storage, migration tooling, CI and deployment/setup documentation.
Week 12 on `jiya` implements the private role screen and authenticated `/state`
role slice. Challenge/vote/result screens and the gameplay engine/actions remain
later Phase 2 work. Optional AI puzzles, hints, chat and extra roles
are outside MVP scope. See [API.md](API.md) and [DECISIONS.md](docs/DECISIONS.md).

The decision document specifies complete candidate policies, including timings,
answer retries, disconnects, votes, sabotage and win priority. All-four agreement
remains a human acceptance gate; candidate details are not claimed approved.

## Identity, lobby and start

A creator becomes host; three others join with the generated room code. Capacity
is four identities, including host. Only waiting rooms accept joins. Full,
unknown and started rooms reject registration. Names are labels, not credentials.
Independent bearer tokens authenticate players; persist only SHA-256 digests.
A room code is never authority to read private state or act for another player.
Retained-token resume reads the existing identity; authenticated duplicate join
attempts return ALREADY_JOINED. Anonymous matching names remain separate identities.

The host starts only once with exactly four active players. The server randomly
assigns exactly one MAFIA, DETECTIVE, HACKER and CIVILIAN, and atomically commits
four assignments plus SABOTAGE/round 1. Host is independent of role and can be
Mafia. The three non-Mafia roles have identical MVP powers. Lobby responses
never contain roles, tokens or answers. Start returns only the caller's role;
every member retrieves only their own role from the implemented `/state` endpoint.

Creation, membership and start use database transactions. Join/start serialize
on the same session row; failures cannot leave partial hosts, players or roles.
Fresh connections make state durable across workers and process restarts.

## Shared state machine and round rules

```text
WAITING (round 0) -- host + exactly four --> SABOTAGE (round 1)
SABOTAGE -> CHALLENGE -> DISCUSSION -> VOTING -> ROUND_RESULTS
ROUND_RESULTS -- no winner, round < 5 --> SABOTAGE (round + 1)
ROUND_RESULTS -- winner or round 5 ends --> GAME_OVER
Any eligible winning action/resolution --> GAME_OVER
```

NEXT_ROUND is not stored. GAME_OVER is terminal; only the server advances phases.
Candidate phase windows are 15/180/60/30/10 seconds respectively, persisted as
server deadlines. A host request cannot bypass the server's deadline. Every
future phase/action writer must lock the same session row before validation.

Ten predefined challenges form five fixed coding/escape pairs, one per round.
Server-only answers use exact comparison after outer-whitespace trimming. Active
players, including Mafia, may submit up to three attempts per challenge/round;
wrong accepted answers remove 15s from the shared timer. Unique session/challenge
completions prevent duplicate progress. Detailed boundary rules are in DECISIONS.md.

Only active Mafia may sabotage: one action/round, three/match. Candidate effects
are a 30s challenge-time reduction or hiding the escape prompt for the first 30s;
no action is pass. Effects expire that round. Discussion happens externally.

Rounds 1–2 record suspicion votes without elimination. Rounds 3–5 eliminate one
candidate only with floor(all active players/2)+1 votes: 3 of 4, 2 of 3, 2 of 2.
Ties/insufficient votes eliminate nobody. One immutable vote per voter/round;
no self-voting; missing votes abstain at deadline. Eliminated players cannot
answer, vote or sabotage. Disconnects do not pause timers or remove identities.

## Wins and completed results

NON_MAFIA wins at eight unique solved challenges or Mafia elimination. MAFIA
wins when only one non-Mafia remains, or round 5 ends without a NON_MAFIA win.
Evaluate NON_MAFIA first when conditions coincide. Eligible wins end play
immediately and atomically. At GAME_OVER, candidate result visibility reveals
roles only to authenticated room members; MVP individual scores stay zero.
Persist winner/reason/progress/round/time. MatchRepository supplies durable
internal result storage; gameplay resolution/public result APIs are not Phase 1.

## Frontend, errors and security

React/TypeScript renders safe server state and never assigns roles, validates
private answers, declares winners or advances official state locally. It sends
credentials only in Authorization headers, retains each tab's seat on refresh,
and renders names as plain text. Mock mode remains available independently.

The shared error envelope is `{ "error": { "code": "...", "message": "...",
"details": {} } }`; field validation reports locations/types without input.
Keep secrets and internal errors out of logs/DTOs. Distinguish 401/403/404/409/422,
413 body limits, 500 failures and 503 readiness. Private responses are no-store.
Use explicit CORS origins, parameterized SQL and HTTPS outside local development.
No public deployment until rate limits, token expiry, backups and TLS are reviewed.

## Verification and remaining human gates

Phase 1 tests cover fake-backed session contracts and real PostgreSQL constraints,
transactions, independent-process joins, duplicate starts, rollback, persistence,
health/CORS/errors, frontend unit coverage/build, and four-player browser flow.
Setup/migrations/reset instructions are in [DATABASE.md](DATABASE.md); the verified
local deployment path and public-hosting blockers are in [DEPLOYMENT.md](docs/DEPLOYMENT.md).

Approval by all four teammates, independent PR review and a reviewed merge remain
separate acceptance steps. Phase 1 verification does not claim a completed game.
