# CodeMafia — REST API contract

## Status, conventions, and types

Week 11 implements only the four **IMPLEMENTED COMPONENT** session endpoints
below. They are mountable routes, not a running production application. All other
endpoints are **PLANNED**. The production app/repository adapter is pending.
Transport shapes are the stable session integration target; policy details not
supplied in the proposal remain **PROPOSED** for team approval.

Base path `/api`; JSON bodies; opaque UUID strings for IDs; UTC ISO 8601 timestamps
for future timestamp fields. Use HTTPS outside local development. Clients send
`Authorization: Bearer <player_token>` for every protected request. Never put
tokens in URLs, use room codes as credentials, or trust client role/host flags.
Frontend types must follow the response shape, not infer private database fields.

| Type | Representation |
|---|---|
| Session/player/challenge ID | UUID string |
| RoomCode | **PROPOSED** six ASCII uppercase letters/digits; generated alphabet excludes I, O, 0, 1 |
| PlayerToken | 43 URL-safe characters encoding 32 random bytes; private, returned once |
| DisplayName | **PROPOSED** trimmed Unicode text, 1–40 characters, no control/format characters |
| Phase | WAITING, SABOTAGE, CHALLENGE, DISCUSSION, VOTING, ROUND_RESULTS, GAME_OVER |
| Role | MAFIA, DETECTIVE, HACKER, CIVILIAN |
| Round | 0 while waiting; 1–5 while playing |
| Winner | **PROPOSED** NON_MAFIA, MAFIA, or null before completion |

Registration names are non-unique labels; identities are unique UUID/token pairs.
Registration POST retries create new identities; reconnect/idempotency policy is
pending. A browser that retains its token should read its lobby rather than join
again automatically. No player-token lifetime/rotation is finalized.

Session bodies reject unknown fields, wrong types, missing required fields, and
invalid names. Room codes are case sensitive; no silent lowercase conversion.
All session responses, including errors, use `Cache-Control: no-store`.

## One error envelope

```json
{"error":{"code":"ROOM_FULL","message":"The room already has four players.","details":{}}}
```

`code` is a stable string, `message` is safe human-readable text, `details` is an
object. Validation details contain field locations/types, never supplied input.
401 responses include `WWW-Authenticate: Bearer`. SQL, internal exception text,
raw tokens, private roles, and answer keys must not appear in errors.

| HTTP | Session error code(s) | Meaning |
|---|---|---|
| 400 | HTTP_ERROR | Malformed HTTP/body encoding; sanitized protocol failure |
| 401 | UNAUTHORIZED | Missing, malformed, unknown, or tampered player token |
| 403 | NOT_ROOM_MEMBER, HOST_ONLY | Cross-room access or non-host start |
| 404 | ROOM_NOT_FOUND | Validly formatted room code not found |
| 409 | ROOM_FULL, GAME_ALREADY_STARTED, FOUR_PLAYERS_REQUIRED, INACTIVE_PLAYERS, ROLES_ALREADY_ASSIGNED, STATE_CONFLICT | Capacity or lifecycle conflict |
| 422 | INVALID_REQUEST, INVALID_ROOM_CODE | Invalid body or code format |
| 500 | ROOM_CREATION_FAILED, IDENTITY_CREATION_FAILED, PERSISTENCE_ERROR, INTERNAL_ERROR | Retry budget exhausted, persistence failure, or unexpected failure |

Planned gameplay errors use the same envelope with **PROPOSED** codes such as
WRONG_PHASE, PLAYER_ELIMINATED, DUPLICATE_VOTE, CHALLENGE_NOT_FOUND,
CHALLENGE_RESOLVED, SABOTAGE_LIMIT, INVALID_ANSWER, and GAME_NOT_OVER.
400 is reserved for malformed HTTP/protocol requests; session body parsing uses
HTTP_ERROR and Michael's shared middleware should preserve the same envelope.

## 1. Create room — IMPLEMENTED COMPONENT

`POST /api/sessions` — public. Body:

```json
{"display_name":"Jiya"}
```

201 response (`Registration`):

```json
{
  "session_id":"11111111-1111-4111-8111-111111111111",
  "room_code":"AB7K9Q",
  "player_id":"22222222-2222-4222-8222-222222222222",
  "player_token":"<private token returned only to this client>",
  "is_host":true,
  "phase":"WAITING",
  "player_count":1
}
```

Token above is an illustrative placeholder, never a usable credential. Fields:
IDs/code/token strings; `is_host` boolean; `phase` literal WAITING;
`player_count` integer 1. Room+host persist in one transaction. The production
unique index arbitrates code conflicts; the service retries bounded candidates.
Errors: 422 INVALID_REQUEST; 500 ROOM_CREATION_FAILED/PERSISTENCE_ERROR/INTERNAL_ERROR.

## 2. Join room — IMPLEMENTED COMPONENT

`POST /api/sessions/{code}/join` — public registration, not reconnect. Body:

```json
{"display_name":"Priyanshi"}
```

201 response has exactly `Registration` fields:

```json
{
  "session_id":"11111111-1111-4111-8111-111111111111",
  "room_code":"AB7K9Q",
  "player_id":"44444444-4444-4444-8444-444444444444",
  "player_token":"<new private token returned only to this client>",
  "is_host":false,
  "phase":"WAITING",
  "player_count":2
}
```

The response contains a new private token/player ID, the existing session/code,
`is_host:false`, `phase:"WAITING"`, and count 2–4.
No client can choose an identity, token, permissions, or role. Joining checks
WAITING and capacity under the same exclusive room lock used for start.
Errors: 422 input/code; 404 ROOM_NOT_FOUND; 409 ROOM_FULL/GAME_ALREADY_STARTED;
500 IDENTITY_CREATION_FAILED/PERSISTENCE_ERROR/INTERNAL_ERROR. A full or started
room never creates a partial player. Duplicate display names alone are permitted.

## 3. Lobby — IMPLEMENTED COMPONENT

`GET /api/sessions/{code}` — valid member token. No body. 200 response:

```json
{
  "room_code":"AB7K9Q",
  "phase":"WAITING",
  "host_player_id":"22222222-2222-4222-8222-222222222222",
  "players":[
    {"player_id":"22222222-2222-4222-8222-222222222222","display_name":"Jiya","is_host":true,"is_active":true}
  ],
  "player_count":1,
  "capacity":4
}
```

`players` is an array of the four listed public fields only; counts are integers,
capacity is literal 4. A consistent phase/member snapshot is required. Lobby
works after start but never reveals roles, even at GAME_OVER; results have a
separate planned reveal contract. Errors: 401, 403 NOT_ROOM_MEMBER, 404, 422, 500.
Invalid credentials are rejected before looking up room existence.

## 4. Start — IMPLEMENTED COMPONENT

`POST /api/sessions/{code}/start` — host's valid member token. Required body:

```json
{}
```

200 response:

```json
{"room_code":"AB7K9Q","phase":"SABOTAGE","round":1,"player_count":4,"my_role":"DETECTIVE"}
```

Phase/round/count are literal SABOTAGE/1/4; `my_role` is the host's own Role.
Exactly four active players, WAITING, no preexisting roles, and host ownership
are required. Securely shuffled assignments contain each role exactly once.
Four role rows and the phase/round/status update commit together. Repeated start
returns 409 and never reveals or reassigns roles. No other player role is sent.
Non-host role retrieval is reserved for the planned `/state` route below.
Errors: 401; 403 NOT_ROOM_MEMBER/HOST_ONLY; 404; 409 as listed; 422; 500.

## 5. Current game state — PLANNED

`GET /api/sessions/{code}/state` — authenticated room member. 200 example:

```json
{
  "room_code":"AB7K9Q","phase":"CHALLENGE","round":1,
  "my_player_id":"22222222-2222-4222-8222-222222222222","my_role":"DETECTIVE",
  "players":[
    {"player_id":"22222222-2222-4222-8222-222222222222","display_name":"Jiya","is_active":true},
    {"player_id":"44444444-4444-4444-8444-444444444444","display_name":"Priyanshi","is_active":true},
    {"player_id":"55555555-5555-4555-8555-555555555555","display_name":"Gabriella","is_active":true},
    {"player_id":"66666666-6666-4666-8666-666666666666","display_name":"Michael","is_active":true}
  ],
  "solved_count":0,"escape_target":8,
  "challenges":[{"challenge_id":"33333333-3333-4333-8333-333333333333","type":"CODING","prompt":"Predict the output...","status":"OPEN"}],
  "winner":null
}
```

**PROPOSED types:** count/target/round integers; `my_role: Role|null` (null in
WAITING); challenge type CODING|ESCAPE, status OPEN|SOLVED|CLOSED; winner as above.
Return only the caller's role before GAME_OVER. Mafia-only budgets must go only
to Mafia, without disclosing identity through public player fields. Never include
answers, other players' role fields, hashes, or tokens. GAME_OVER full role reveal
is proposed for results. Errors: 401/403/404/422/500. Michael coordinates state
aggregation with Gabriella's challenge/progress data and Jiya's session boundary.

## 6. Challenge answers — PLANNED

`POST /api/sessions/{code}/answers` — active authenticated member, CHALLENGE phase.

```json
{"challenge_id":"33333333-3333-4333-8333-333333333333","answer":"42"}
```

200 **PROPOSED** response:

```json
{"challenge_id":"33333333-3333-4333-8333-333333333333","correct":true,"solved_count":3,"phase":"CHALLENGE","winner":null}
```

Answer is a string (size/normalization/retries PROPOSED); correctness boolean;
count integer 0–10. Server verifies membership, active state, phase, challenge
ownership/availability and answer. A unique completion changes progress at most
once. Wrong answers impose the approved time penalty. Check eight unique solves
and terminate immediately when eligible. Errors: 401/403; 404 CHALLENGE_NOT_FOUND;
409 WRONG_PHASE/CHALLENGE_RESOLVED; 422 INVALID_ANSWER/input; 500. No answer-key echo.
Gabriella owns answer validation/progress; timing policy requires team approval.

## 7. Voting — PLANNED

`POST /api/sessions/{code}/votes` — active member in VOTING.

```json
{"candidate_player_id":"44444444-4444-4444-8444-444444444444"}
```

200 **PROPOSED** response:

```json
{"accepted":true,"round":3,"phase":"VOTING"}
```

Server verifies eligible candidate and enforces proposed one accepted vote per
voter/round using uniqueness. Rounds 1–2 cannot eliminate; rounds 3–5 require
`floor(all_active_players/2)+1` votes for one candidate. Ties/insufficient votes
produce no elimination. Proposed resolution occurs at ROUND_RESULTS. Do not
expose private votes. Abstention/self-voting/replacements are pending.
Errors: 401; 403 PLAYER_ELIMINATED/member; 404 candidate/room; 409 WRONG_PHASE,
DUPLICATE_VOTE or ineligible candidate; 422; 500. Gameplay owner allocation pending.

## 8. Sabotage — PLANNED

`POST /api/sessions/{code}/sabotage` — active Mafia in SABOTAGE.

```json
{"action":"HIDE_CLUE"}
```

200 **PROPOSED** response:

```json
{"accepted":true,"round":2,"remaining_sabotages":1}
```

Proposed action enum HIDE_CLUE|REDUCE_TIME. Server atomically enforces at most
three per match and one per round; duration/effects/pass are pending approval.
`remaining_sabotages` integer 0–3 is private to Mafia. Do not broadcast the actor.
Errors: 401; 403 non-Mafia/eliminated/member; 404; 409 WRONG_PHASE/SABOTAGE_LIMIT;
422 invalid action; 500. Gameplay owner allocation pending.

## 9. Phase advancement — PLANNED, PROPOSED

`POST /api/sessions/{code}/advance`, empty `{}` body. Authentication required;
caller policy (host or server-controlled), readiness and deadlines require approval.

```json
{"room_code":"AB7K9Q","phase":"CHALLENGE","round":1,"winner":null}
```

200 proposed Phase/Round/Winner types. Never accept arbitrary client target phase
or round. Validate readiness, apply effects/resolution/wins atomically, and honor
terminal GAME_OVER. Errors: 401/403/404/409 WRONG_PHASE or not-ready/422/500.
No endpoint is implemented until advancement rules and owner are approved.

## 10. Results — PLANNED, PROPOSED

`GET /api/sessions/{code}/results` — proposed room-member-only after GAME_OVER.

```json
{
  "session_id":"11111111-1111-4111-8111-111111111111","winner":"NON_MAFIA",
  "reason":"ESCAPED","solved_count":8,"final_round":4,
  "completed_at":"2026-11-09T20:00:00Z",
  "players":[
    {"player_id":"22222222-2222-4222-8222-222222222222","role":"DETECTIVE","score":0},
    {"player_id":"44444444-4444-4444-8444-444444444444","role":"MAFIA","score":0},
    {"player_id":"55555555-5555-4555-8555-555555555555","role":"HACKER","score":0},
    {"player_id":"66666666-6666-4666-8666-666666666666","role":"CIVILIAN","score":0}
  ]
}
```

200 proposed result object; integer scores need an approved formula (0 above is
illustrative); reason enum ESCAPED|MAFIA_ELIMINATED|ROUND_LIMIT|MAFIA_PARITY is
proposed. Role reveal only after GAME_OVER. Errors: 401/403/404/409 GAME_NOT_OVER/500.
Gabriella owns persistent result storage; resolution/API owner requires agreement.

## 11. History — PLANNED, PROPOSED

`GET /api/sessions/{code}/history?limit=20&cursor=<opaque>` — proposed room-member
authorization, `limit` integer 1–100; cursor optional string.

```json
{
  "items":[{"session_id":"11111111-1111-4111-8111-111111111111","winner":"NON_MAFIA","completed_at":"2026-11-09T20:00:00Z"}],
  "next_cursor":null
}
```

200 proposed page. A room currently represents one match, so its history has at
most one completed result. Cross-room/account history and rematches are not
defined. Persist records across restarts, never publicize tokens/answers. Errors:
401/403/404/422 invalid pagination/500. Scope, retention and access need approval.

## Integration and model requirements

`repository.py` defines immutable Room/Player records and a transaction protocol,
not SQL models. Required adapter semantics: unique room codes; unique UUIDs and
token digests; correct session/host/role membership; each role once per room;
atomic room+host creation and four-role start; rollback/commit failures surfaced
before success; shared/exclusive room locking under suitable transaction isolation.
No in-memory fallback is permitted for production. Gabriella owns migrations,
physical names and status mappings. Michael owns the app/engine lifecycle, shared
errors, CORS, request limits, rate limiting, deployment, and CI.

See [SESSION_INTEGRATION.md](docs/SESSION_INTEGRATION.md) for exact imports,
registration, adapter operations and PostgreSQL verification gates. Tests this
week use fake storage only. API.md and SPECIFICATION.md must both change when a
proposed rule becomes approved. Planned shapes are review targets, not completed
implementations or authorization for additional Week 11 features.
