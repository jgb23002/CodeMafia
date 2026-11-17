"""Durable match-result storage for the future server-owned resolution engine.

There is intentionally no public endpoint that lets a client declare a winner.
"""

from dataclasses import dataclass

import psycopg

from backend.app.database import Database
from backend.app.sessions.repository import RepositoryError, StateConflict


@dataclass(frozen=True)
class MatchResult:
    session_id: str
    winner: str
    reason: str
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
