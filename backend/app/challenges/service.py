"""Server-owned challenge rules: serve each round's pair, check answers, track escape.

Candidate policy from API.md section 6: answers are trimmed and compared exactly
(case-sensitive), each player has three attempts per challenge, a wrong answer
takes 15 seconds off the round's shared deadline, and eight unique solves end the
match with a NON_MAFIA escape. Answer keys and submitted answers are never returned.
"""

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.db.seeds import answer_matches
from backend.app.matches import ESCAPE_TARGET, Winner
from backend.app.sessions.repository import (
    Phase,
    Player,
    RepositoryError,
    Room,
    StateConflict,
)
from backend.app.sessions.service import SessionError, bearer_hash, validate_code

from .repository import ChallengeRecord, ChallengeRepository, ChallengeTransaction

CHALLENGE_SECONDS = 120
WRONG_ANSWER_PENALTY_SECONDS = 15
MAX_ATTEMPTS = 3
TOTAL_CHALLENGES = 10
MAX_ANSWER_LENGTH = 2000
ESCAPE_WINNER = Winner.NON_MAFIA.value


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChallengeService:
    def __init__(
        self,
        repository: ChallengeRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
        challenge_seconds: int = CHALLENGE_SECONDS,
    ):
        self.repository = repository
        self.clock = clock
        self.challenge_seconds = challenge_seconds

    # ---- shared checks -------------------------------------------------

    @contextmanager
    def _transaction(self) -> Iterator[ChallengeTransaction]:
        try:
            with self.repository.transaction() as transaction:
                yield transaction
        except StateConflict:
            raise SessionError(
                409, "STATE_CONFLICT", "The room state changed. Refresh and retry."
            ) from None
        except RepositoryError:
            raise SessionError(
                500, "PERSISTENCE_ERROR", "Unable to persist the challenge operation."
            ) from None

    @staticmethod
    def _room_and_player(
        tx: ChallengeTransaction, code: str, digest: str
    ) -> tuple[Room, Player]:
        player = tx.find_player_by_token_hash(digest)
        if player is None:
            raise SessionError(401, "UNAUTHORIZED", "A valid player token is required.")
        # Exclusive: the round timer may be created or shortened in this request.
        room = tx.get_room(code, lock="exclusive")
        if room is None:
            raise SessionError(404, "ROOM_NOT_FOUND", "Room not found.")
        if player.session_id != room.session_id:
            raise SessionError(
                403, "NOT_ROOM_MEMBER", "This player does not belong to the room."
            )
        if room.phase == Phase.WAITING:
            raise SessionError(409, "GAME_NOT_STARTED", "The game has not started yet.")
        return room, player

    def _deadline(self, tx: ChallengeTransaction, room: Room) -> datetime | None:
        """The round's shared deadline, started on first use in the CHALLENGE phase."""
        deadline = tx.get_deadline(room.session_id, room.round)
        if deadline is None and room.phase == Phase.CHALLENGE:
            deadline = self.clock() + timedelta(seconds=self.challenge_seconds)
            tx.set_deadline(room.session_id, room.round, deadline)
        return deadline

    def _seconds_left(self, deadline: datetime | None) -> int | None:
        if deadline is None:
            return None
        return max(0, math.ceil((deadline - self.clock()).total_seconds()))

    # ---- public operations ---------------------------------------------

    def board(self, code: str, authorization: str | None) -> dict:
        digest = bearer_hash(authorization)
        validate_code(code)
        with self._transaction() as tx:
            room, player = self._room_and_player(tx, code, digest)
            deadline = self._deadline(tx, room)
            seconds_left = self._seconds_left(deadline)
            completed = tx.completed_challenges(room.session_id)
            attempts = tx.attempt_counts(room.session_id, player.player_id)
            accepting = (
                room.phase == Phase.CHALLENGE
                and seconds_left is not None
                and seconds_left > 0
            )
            challenges = [
                {
                    "challenge_id": challenge.challenge_id,
                    "type": challenge.kind,
                    "prompt": challenge.prompt,
                    "status": (
                        "SOLVED"
                        if challenge.challenge_id in completed
                        else "OPEN"
                        if accepting
                        else "CLOSED"
                    ),
                    "attempts_left": max(
                        0, MAX_ATTEMPTS - attempts.get(challenge.challenge_id, 0)
                    ),
                }
                for challenge in tx.round_challenges(room.round)
            ]
            response = {
                "room_code": room.room_code,
                "phase": room.phase.value,
                "round": room.round,
                "solved_count": len(completed),
                "escape_target": ESCAPE_TARGET,
                "total_challenges": TOTAL_CHALLENGES,
                "deadline": deadline.isoformat() if deadline else None,
                "seconds_remaining": seconds_left,
                "challenges": challenges,
                "winner": (
                    tx.get_winner(room.session_id)
                    if room.phase == Phase.GAME_OVER
                    else None
                ),
            }
        return response

    def answer(
        self,
        code: str,
        authorization: str | None,
        challenge_id: str,
        answer: str,
    ) -> dict:
        digest = bearer_hash(authorization)
        validate_code(code)
        submitted = answer.strip()
        if not 1 <= len(submitted) <= MAX_ANSWER_LENGTH:
            raise SessionError(
                422, "INVALID_ANSWER", "Answers must contain 1 to 2000 characters."
            )
        with self._transaction() as tx:
            room, player = self._room_and_player(tx, code, digest)
            if room.phase != Phase.CHALLENGE:
                raise SessionError(
                    409,
                    "WRONG_PHASE",
                    "Answers are only accepted in the challenge phase.",
                )
            if not player.is_active:
                raise SessionError(
                    403, "PLAYER_ELIMINATED", "Eliminated players cannot answer."
                )
            challenge = tx.get_challenge(challenge_id)
            if challenge is None or challenge.round != room.round:
                raise SessionError(
                    404, "CHALLENGE_NOT_FOUND", "That challenge is not in this round."
                )
            completed = tx.completed_challenges(room.session_id)
            if challenge.challenge_id in completed:
                raise SessionError(
                    409, "CHALLENGE_RESOLVED", "This challenge is already solved."
                )
            deadline = self._deadline(tx, room)
            if deadline is None or self._seconds_left(deadline) == 0:
                raise SessionError(
                    409, "TIME_EXPIRED", "Time is up for this round's challenges."
                )
            used = tx.attempt_counts(room.session_id, player.player_id).get(
                challenge.challenge_id, 0
            )
            if used >= MAX_ATTEMPTS:
                raise SessionError(
                    409, "ATTEMPT_LIMIT", "No attempts left for this challenge."
                )
            correct = self._check(challenge, submitted)
            tx.record_attempt(
                str(uuid4()),
                room.session_id,
                player.player_id,
                challenge.challenge_id,
                submitted,
                correct,
            )
            penalty = 0
            phase = room.phase
            winner = None
            if correct:
                tx.complete_challenge(
                    room.session_id, challenge.challenge_id, player.player_id
                )
                completed = completed | {challenge.challenge_id}
                if len(completed) >= ESCAPE_TARGET:
                    tx.finish_escape(room.session_id, len(completed), room.round)
                    phase, winner = Phase.GAME_OVER, ESCAPE_WINNER
            else:
                penalty = WRONG_ANSWER_PENALTY_SECONDS
                deadline = max(self.clock(), deadline - timedelta(seconds=penalty))
                tx.set_deadline(room.session_id, room.round, deadline)
            response = {
                "challenge_id": challenge.challenge_id,
                "correct": correct,
                "solved_count": len(completed),
                "escape_target": ESCAPE_TARGET,
                "attempts_left": MAX_ATTEMPTS - used - 1,
                "penalty_seconds": penalty,
                "deadline": deadline.isoformat(),
                "seconds_remaining": self._seconds_left(deadline),
                "phase": phase.value,
                "winner": winner,
            }
        return response

    @staticmethod
    def _check(challenge: ChallengeRecord, submitted: str) -> bool:
        """Compare text only; submitted code is never executed."""
        return answer_matches(challenge.answer_key, submitted)
