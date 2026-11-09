# CodeMafia: Escape the System — MVP specification

UConn CSE 4095 — Agentic Programming. Team: Jiya Gorasiya (lead),
Priyanshi Sitlani, Gabriella Luciani, Michael Garcia.

## 1. Scope and decision status

A private four-player browser game combines social deduction, coding exercises,
and escape-room puzzles. Three players try to escape; a secret Mafia player
tries to stop them. This document records the supplied MVP rules. Details added
beyond those rules are labeled **PROPOSED** and require team approval.

Required MVP: private rooms, secret roles, at most five rounds, ten predefined
challenges, server-side answer checking, sabotage, voting, early victory checks,
and persistent completed match history. Optional AI puzzles, hints, additional
rooms, special abilities, built-in chat, and achievements are out of scope.

Week 11 implementation is limited to Jiya's architecture, session feature,
session tests, and leadership documents. The production app, database, frontend,
gameplay engine, and deployment are pending other owners or later weeks.

## 2. Architecture and user flow

React + TypeScript renders views and sends JSON over HTTPS to FastAPI. FastAPI
owns identity, permissions, official game state, validation, and win decisions.
PostgreSQL persists sessions, players, private roles, actions, and results.
React must never advance phases, assign roles, or decide correctness/winners.

1. A host creates a room with a display name and receives a private player token.
2. Three others enter the room code and register with their own names/tokens.
3. Authenticated members view the lobby; the host starts when four have joined.
4. The server privately assigns roles and starts Round 1 in SABOTAGE.
5. Players follow the five phases. The server rejects ineligible actions.
6. A winning condition ends the game; completed results survive server restarts.

See [API.md](API.md) for contracts and [architecture](docs/ARCHITECTURE.md) for
ownership boundaries. **PROPOSED transport:** REST polling initially; polling
intervals, WebSockets, and phase scheduling remain team decisions.

## 3. Roles and permissions

Exactly one each of MAFIA, DETECTIVE, HACKER, and CIVILIAN is assigned using
server-side secure randomness. Detective, Hacker, and Civilian have identical
abilities and objectives in the MVP. Host is a lobby permission, not a role.
The host can also be Mafia. No role is selected by the client.

| Actor | Allowed actions |
|---|---|
| New visitor | Create a room or register in a waiting room |
| Authenticated room member | Read a safe lobby and their private game state |
| Host | Start once with exactly four players |
| Active member, including Mafia | Submit eligible challenge answers and votes |
| Active Mafia | Eligible sabotage within phase and use limits |
| Eliminated member | No future gameplay actions; spectator visibility is PROPOSED |

Before GAME_OVER, players may see only their own role. All role revelation at
GAME_OVER is **PROPOSED** and reserved for the planned results/state contracts.
Lobby responses never contain roles, credentials, or challenge answer keys.

## 4. Lobby and identity

A creator becomes host. The server generates an unpredictable unique room code.
Rooms hold at most four distinct player identities, including the host. Only
WAITING rooms accept joins. Unknown, full, and started rooms reject registration.
Capacity checks and insertion must occur in a database transaction holding the
room's row lock. Start and join use the same lock to serialize competing actions.

Bearer player tokens authenticate private actions; a room code grants no private
permission. Each registration issues an independent 256-bit token. Persist only
its SHA-256 digest with global uniqueness. IDs and tokens are server-generated.
Names are labels, not proof of identity. No public API accepts a player ID as
authority to act for that player.

**PROPOSED session defaults implemented for review:** six uppercase alphanumeric
characters; generated codes exclude ambiguous characters; display names are
trimmed, 1–40 Unicode characters, with control/format characters rejected;
duplicate display names are allowed for separate identities; new registration
POSTs are non-idempotent. Reconnection, retries/idempotency keys, token lifetime,
rotation, browser token storage, and duplicate-name policy need approval.
Clients should retain their own token and must not automatically rejoin on refresh.

Creating room + host is atomic. Room-code collisions are retried with a bounded
number of new candidates, each in a fresh transaction. Starting verifies host,
WAITING, exactly four active players, and no existing assignments, then commits
all four roles, Round 1, and SABOTAGE together. Repeated starts cannot reassign roles.

## 5. Rounds and phases

At most five rounds; each round follows this state machine:

```text
WAITING -- host starts with four players --> SABOTAGE (Round 1)
SABOTAGE -> CHALLENGE -> DISCUSSION -> VOTING -> ROUND_RESULTS
ROUND_RESULTS -- no winner and round < 5 --> SABOTAGE (round + 1)
ROUND_RESULTS -- winner or round 5 complete --> GAME_OVER
Any phase -- eligible winning condition satisfied --> GAME_OVER
```

NEXT_ROUND is a transition, never a stored phase. WAITING has round 0;
active games have round 1–5. GAME_OVER is terminal. Only the server changes
phase/round. **PROPOSED:** transitions use the planned `/advance` contract;
readiness, timers, automation, and caller permission remain unapproved.

### SABOTAGE

Only active Mafia may sabotage: at most three actions per match and one per
round. Effects may reduce challenge time or temporarily hide clues. The backend
must enforce both budgets transactionally and conceal the actor's identity.
Exact durations, reduction amounts, visibility, passing, phase completion, and
effect stacking/expiry are **PROPOSED** pending team approval.

### CHALLENGE

Ten predefined challenges form five pairs: one coding exercise and one escape
puzzle in each round. Active players, including Mafia, can submit answers.
Answer keys and correctness checks live only on the server. Eight successfully
completed unique challenges win for the non-Mafia team. Multiple correct
submissions for the same challenge must never increase progress twice.

Incorrect answers impose time penalties. The amount, target timer, normalization,
retry limits, accepted formats, ordering/selection of pairs, timeout handling,
and whether both challenges must be attempted are **PROPOSED** decisions.
No timer or retry rule is invented by the Week 11 session module.

### DISCUSSION

Players discuss suspicions verbally or via an external platform. Built-in chat
is out of scope. Duration and transition readiness are **PROPOSED**.

### VOTING

Rounds 1–2 record suspicion votes and eliminate nobody. Rounds 3–5 can eliminate
one candidate with a strict majority of **all active players**, including active
players who have not voted. Threshold = `floor(active_count / 2) + 1`:
four active players require three votes; three require two. Two require two
if this state is reached before a win check ends the game.

Ties and insufficient votes eliminate nobody. Eliminated players cannot answer,
vote, or sabotage in future rounds. **PROPOSED anti-duplicate rule:** one accepted
vote per voter per round, no replacements. Abstention, self-voting, late votes,
and exact voting closure are pending decisions; clients must not assume them.

### ROUND_RESULTS

The server finalizes eligible actions, tallies votes, applies any elimination,
checks wins, and advances only if no winner and fewer than five rounds elapsed.
**PROPOSED:** elimination is applied during resolution, not on each incoming vote.
Concurrent submissions/votes and phase closure require atomic boundaries.

## 6. Winning and termination

The non-Mafia team wins when eight unique challenges are solved or Mafia is
eliminated. Mafia wins if Round 5 ends without a non-Mafia victory, or if only
one non-Mafia player remains active. Games end immediately upon satisfying an
eligible win condition and never proceed beyond Round 5.

**PROPOSED resolution priority:** check non-Mafia wins before Mafia wins in the
same atomic resolution. Exactly when concurrent actions are accepted, how an
action races a phase deadline, and how competing wins are ordered need approval.
Future gameplay must define these before implementation; the session module
does not declare winners or implement round progression.

## 7. Persistence and state ownership

Gabriella owns physical models, table names, constraints, and migrations. Logical
requirements (not a competing schema) include:

- Sessions: opaque ID, unique code, host identity, phase, round, lifecycle status,
  UTC creation/start/completion timestamps as applicable.
- Players: opaque ID, session membership, display name, globally unique private
  token hash, active/eliminated state.
- Private role assignments: session, player, role; once per player and once per
  role in a session; membership enforced by relationships/constraints.
- Challenges: ten prompts, types, private answers, sequence/pairing and per-match
  unique completion state; immutable definitions separated from match progress.
- Accepted submissions, votes, sabotage uses/effects, round resolution records.
- Completed results: winner, reason, final progress, scores (formula PROPOSED),
  completion timestamp and role reveal authorization.

Completed results and session state must survive server restarts in PostgreSQL.
No production state may depend on a Python dictionary or process-local lock.
Transaction, uniqueness, authorization, and phase checks must work across workers.
Session repository contracts and integration blockers are documented in
[SESSION_INTEGRATION.md](docs/SESSION_INTEGRATION.md).

## 8. Security and errors

Use HTTPS in deployment. Keep tokens out of URLs/logs; return registration tokens
only to their registering client. Hash high-entropy tokens and index digests;
do not store raw tokens or answer keys in public DTOs. Apply explicit response
allowlists, authenticated membership checks, host checks, and no-store headers.
Reject client-selected roles, phases, host flags, and extra input fields.
Names are plain text; React renders them as text without raw HTML injection.

Use parameterized persistence; constrain input sizes and avoid diagnostic SQL,
request bodies, tokens, or private roles in errors/logs. Michael owns HTTPS/CORS,
request-size limits, credential-redacting logs, rate limits, secret configuration,
and shared error/health middleware. Rate limits are required before public
deployment; exact thresholds and session expiration are **PROPOSED**.

The API error envelope is `{ "error": { "code": "...", "message": "...",
"details": {} } }`. Distinguish invalid fields (422), missing/bad tokens (401),
forbidden actions (403), unknown resources (404), state conflicts (409), and
sanitized persistence/unexpected failures (500). A transaction failure must
not leave a partial player, role assignment, start, or accepted action.

## 9. Tests and acceptance criteria

Week 11 session tests must cover creation, collision recovery/exhaustion, joins,
invalid/full/started rooms, concurrent capacity, authentication/tampering,
cross-room denial, host-only start, four roles once, repeated starts, secrecy,
rollback expectations, input validation, and consistent errors. Fake storage tests
prove service expectations only. Real PostgreSQL transaction, constraint,
multi-worker concurrency, and persistence tests are a separate integration gate.

Full MVP acceptance requires four independent browser clients, working phases
and all gameplay rules, accurate immediate victory checks, private roles/answers,
persistent results after a restart, frontend/backend/database tests, and a
reviewed deployment. Unit session tests alone do not establish a complete game.

## 10. Pending decisions and ownership

Team approval is pending for all PROPOSED details, especially timers, penalties,
answer retries, reconnect/disconnect behavior, abstention/self-voting, phase
advancement/readiness, sabotage duration, win-race priority, token policy, and
display-name policy. Changes must update both this spec and API contracts.

| Owner | Week 11 responsibility |
|---|---|
| Jiya | Architecture/API, standalone sessions/tests, leadership/QA documents |
| Priyanshi | React/TypeScript setup, lobby/routes, frontend tests |
| Gabriella | PostgreSQL models/migrations, ten challenges, database tests/adapter |
| Michael | FastAPI foundation, shared errors/configuration, CI/deployment foundation |

Reviews, production integration, GitHub issues/settings, and later-week work are
tracked explicitly as pending in [WEEKLY_STATUS.md](docs/WEEKLY_STATUS.md).
