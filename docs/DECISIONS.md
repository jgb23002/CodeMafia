# Candidate MVP decisions and human sign-off

Updated 2026-11-17, America/New_York. These are concrete candidate defaults for
team review. Jiya's request authorized implementation on `jiya`; it did not
record agreement from the other three people. No approval is inferred here.

## Implemented Phase 1 defaults

- Four identities per room, including the host; only the host starts at exactly four.
- Exactly one MAFIA, DETECTIVE, HACKER, CIVILIAN, assigned privately on the server.
- Six uppercase alphanumeric room codes; generation excludes I/O/0/1.
- Names: trimmed, 1–40 Unicode characters, no control/format characters; duplicates allowed.
- Independent 256-bit bearer tokens, SHA-256 digests stored with global uniqueness.
- This tab's sessionStorage retains its seat on refresh; no automatic rejoin.
- Registration is not idempotent and is never automatically retried by the UI.
- No automatic room/token expiry, reconnect transfer, token rotation or real leave API.
- Poll the authenticated lobby every two seconds; never publish private roles or keys.

## Complete candidate gameplay policy for Phase 2

- Five rounds maximum. Each follows SABOTAGE → CHALLENGE → DISCUSSION → VOTING →
  ROUND_RESULTS. A nonterminal resolution advances to SABOTAGE of the next round.
  NEXT_ROUND is a transition, never a stored phase. GAME_OVER is terminal.
- Server windows: sabotage 15s, challenge 180s, discussion 60s, voting 30s,
  round results 10s. Persist server deadlines. A timer worker advances phases;
  an authenticated host may request advancement only after the server deadline.
  An eliminated host retains this timing request permission, not gameplay powers.
- The server locks the session, reads database time, verifies phase/deadline,
  and accepts an action only before that deadline. Accepted operations resolve
  atomically; clients cannot supply phases, round numbers or deadlines.
- Use challenge pair CM01/02 in round 1 through CM09/10 in round 5. Both are
  available simultaneously. A unique challenge can increase team progress once.
- Active players, including Mafia, may answer. Answers are 1–2000 characters;
  trim outer whitespace, then compare case-sensitively with a server-only key.
  At most three attempts per player/challenge/round. A wrong accepted answer
  subtracts 15s from the shared challenge deadline, floored at database time.
  Solving both challenges closes CHALLENGE early; otherwise wait for its deadline.
- Active Mafia may choose REDUCE_TIME or HIDE_CLUE during SABOTAGE, at most one
  action per round and three per match. REDUCE_TIME subtracts 30s from the next
  challenge window, minimum 15s; HIDE_CLUE hides the marked clue for its first
  30s. No action means pass. Effects expire in that round and never stack across rounds.
- Discussion uses an external conversation channel; built-in chat is out of scope.
- One immutable vote per active player/round; candidate must be another active
  member. Self-votes/replacements are rejected. Missing votes abstain at deadline.
  Close voting early if every active player voted, otherwise at its deadline.
- Rounds 1–2 never eliminate. Rounds 3–5 eliminate only with a strict majority of
  all active players: floor(active/2)+1. Ties or insufficient votes eliminate nobody.
  Apply elimination atomically at ROUND_RESULTS; eliminated players cannot act.
- NON_MAFIA wins immediately at eight unique solves or Mafia elimination. MAFIA
  wins when only one non-Mafia player remains, or round 5 resolves without a
  non-Mafia win. If conditions coincide, evaluate NON_MAFIA before MAFIA.
- Disconnection does not pause timers or remove identities. Missing actions
  timeout/abstain; no replacement seat. Private roles remain private until GAME_OVER.
- Completed results persist winner/reason/progress/round/time. Candidate MVP
  individual scores are zero; there is no separate competitive scoring system.

These gameplay timers, actions and retrieval endpoints are documented targets,
not Phase 1 implementations. Phase 1 creates the storage needed for later work.
Public deployment still requires a reviewed expiry/rate-limit/retention policy.

## Required agreement record

| Member | Rulebook agreement | Evidence |
|---|---|---|
| Jiya Gorasiya | Pending explicit rule approval | Implementation request is not rule sign-off |
| Priyanshi Sitlani | Pending | No recorded approval |
| Gabriella Luciani | Pending | No recorded approval |
| Michael Garcia | Pending | No recorded approval |

Record a person's own dated GitHub review/comment link before changing their row.
If the team changes a candidate policy, update SPECIFICATION.md and API.md together.
