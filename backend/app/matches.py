"""Durable match-result storage for the future server-owned resolution engine.

There is intentionally no public endpoint that lets a client declare a winner.
"""

from dataclasses import dataclass
from enum import Enum

import psycopg

from backend.app.database import Database
from backend.app.sessions.repository import RepositoryError, StateConflict

ESCAPE_TARGET = 8
FINAL_ROUND = 5


class Winner(str, Enum):
    NON_MAFIA = "NON_MAFIA"
    MAFIA = "MAFIA"


class WinReason(str, Enum):
    ESCAPED = "ESCAPED"
    MAFIA_ELIMINATED = "MAFIA_ELIMINATED"
    MAFIA_PARITY = "MAFIA_PARITY"
    ROUND_LIMIT = "ROUND_LIMIT"


@dataclass(frozen=True)
class MatchOutcome:
    winner: Winner
    reason: WinReason


def evaluate_winner(
    solved_count: int,
    mafia_is_active: bool,
    active_non_mafia_count: int,
    current_round: int,
    final_round_resolved: bool,
) -> MatchOutcome | None:
    """Return the candidate outcome for an authoritative match-state snapshot.

    Non-Mafia conditions intentionally precede Mafia conditions. When escape and
    Mafia elimination coincide, ESCAPED temporarily takes precedence pending
    explicit team approval of that reporting rule.
    """
    if solved_count >= ESCAPE_TARGET:
        return MatchOutcome(Winner.NON_MAFIA, WinReason.ESCAPED)
    if not mafia_is_active:
        return MatchOutcome(Winner.NON_MAFIA, WinReason.MAFIA_ELIMINATED)
    if active_non_mafia_count <= 1:
        return MatchOutcome(Winner.MAFIA, WinReason.MAFIA_PARITY)
    if current_round == FINAL_ROUND and final_round_resolved:
        return MatchOutcome(Winner.MAFIA, WinReason.ROUND_LIMIT)
    return None


@dataclass(frozen=True)
class MatchResult:
    session_id: str
    winner: Winner
    reason: WinReason
    solved_count: int
    rounds_played: int


class MatchRepository:
    def __init__(self, database: Database):
        self.database = database

    def record_result(self, result: MatchResult) -> None:
        try:
            with self.database.connect() as connection:
                room = connection.execute(
                    "SELECT status, round FROM sessions WHERE id = %s FOR UPDATE",
                    (result.session_id,),
                ).fetchone()
                if (
                    room is None
                    or room["status"] != "active"
                    or room["round"] != result.rounds_played
                ):
                    raise StateConflict()
                connection.execute(
                    """INSERT INTO results (session_id, winner, reason, solved_count, rounds_played)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        result.session_id,
                        result.winner,
                        result.reason,
                        result.solved_count,
                        result.rounds_played,
                    ),
                )
                connection.execute(
                    "UPDATE sessions SET phase = 'GAME_OVER', status = 'finished', completed_at = now() WHERE id = %s",
                    (result.session_id,),
                )
        except psycopg.Error:
            raise RepositoryError() from None

    def read_result(self, session_id: str) -> MatchResult | None:
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT session_id, winner, reason, solved_count, rounds_played FROM results WHERE session_id = %s",
                    (session_id,),
                ).fetchone()
                return (
                    MatchResult(**{**row, "session_id": str(row["session_id"])})
                    if row
                    else None
                )
        except psycopg.Error:
            raise RepositoryError() from None
