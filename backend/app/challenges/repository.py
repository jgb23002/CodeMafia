"""Challenge persistence contract. Answer keys never leave the server side."""

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backend.app.sessions.repository import SessionTransaction


@dataclass(frozen=True)
class ChallengeRecord:
    challenge_id: str
    kind: str
    round: int
    prompt: str
    answer_key: dict


class ChallengeTransaction(SessionTransaction, Protocol):
    """Session operations plus challenge state, inside one room-locked unit of work."""

    def round_challenges(self, round_number: int) -> Sequence[ChallengeRecord]:
        """Return the round's challenges ordered CODING first, then ESCAPE."""
        ...

    def get_challenge(self, challenge_id: str) -> ChallengeRecord | None: ...

    def completed_challenges(self, session_id: str) -> set[str]:
        """Challenge IDs this match has solved, across all rounds."""
        ...

    def attempt_counts(self, session_id: str, player_id: str) -> dict[str, int]:
        """Challenge ID -> number of answers this player has submitted."""
        ...

    def get_deadline(self, session_id: str, round_number: int) -> datetime | None: ...

    def set_deadline(
        self, session_id: str, round_number: int, deadline: datetime
    ) -> None:
        """Insert or replace the round's shared deadline. Requires the exclusive lock."""
        ...

    def record_attempt(
        self,
        attempt_id: str,
        session_id: str,
        player_id: str,
        challenge_id: str,
        answer: str,
        is_correct: bool,
    ) -> None: ...

    def complete_challenge(
        self, session_id: str, challenge_id: str, player_id: str
    ) -> None:
        """Record a unique solve. A second solve of the same challenge is a StateConflict."""
        ...

    def get_winner(self, session_id: str) -> str | None: ...

    def finish_escape(
        self, session_id: str, solved_count: int, rounds_played: int
    ) -> None:
        """Store the NON_MAFIA result and move the room to GAME_OVER atomically."""
        ...


class ChallengeRepository(Protocol):
    def transaction(self) -> AbstractContextManager[ChallengeTransaction]: ...
