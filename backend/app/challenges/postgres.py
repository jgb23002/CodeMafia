"""PostgreSQL challenge adapter, layered on the session adapter's room/player queries."""

from contextlib import contextmanager
from datetime import datetime

import psycopg

from backend.app.database import Database
from backend.app.matches import Winner, WinReason
from backend.app.sessions.postgres import PostgresTransaction
from backend.app.sessions.repository import RepositoryError, StateConflict

from .repository import ChallengeRecord


class PostgresChallengeRepository:
    def __init__(self, database: Database):
        self.database = database

    @contextmanager
    def transaction(self):
        try:
            with self.database.connect() as connection:
                yield PostgresChallengeTransaction(connection)
        except psycopg.errors.UniqueViolation as error:
            if error.diag.constraint_name == "challenge_completions_pkey":
                raise StateConflict() from None
            raise RepositoryError() from None
        except psycopg.Error:
            raise RepositoryError() from None


class PostgresChallengeTransaction(PostgresTransaction):
    @staticmethod
    def _challenge(row) -> ChallengeRecord:
        return ChallengeRecord(
            row["id"], row["kind"], row["round"], row["prompt"], row["answer_key"]
        )

    def _require_exclusive(self, session_id: str) -> None:
        if session_id not in self.exclusive_locks:
            raise RepositoryError()

    def round_challenges(self, round_number: int) -> list[ChallengeRecord]:
        rows = self.connection.execute(
            """SELECT id, kind, round, prompt, answer_key FROM challenges
               WHERE round = %s ORDER BY kind, id""",
            (round_number,),
        )
        return [self._challenge(row) for row in rows]

    def get_challenge(self, challenge_id: str) -> ChallengeRecord | None:
        row = self.connection.execute(
            "SELECT id, kind, round, prompt, answer_key FROM challenges WHERE id = %s",
            (challenge_id,),
        ).fetchone()
        return self._challenge(row) if row else None

    def completed_challenges(self, session_id: str) -> set[str]:
        rows = self.connection.execute(
            "SELECT challenge_id FROM challenge_completions WHERE session_id = %s",
            (session_id,),
        )
        return {row["challenge_id"] for row in rows}

    def attempt_counts(self, session_id: str, player_id: str) -> dict[str, int]:
        rows = self.connection.execute(
            """SELECT challenge_id, count(*) AS attempts FROM attempts
               WHERE session_id = %s AND player_id = %s GROUP BY challenge_id""",
            (session_id, player_id),
        )
        return {row["challenge_id"]: row["attempts"] for row in rows}

    def get_deadline(self, session_id: str, round_number: int) -> datetime | None:
        row = self.connection.execute(
            "SELECT deadline FROM challenge_timers WHERE session_id = %s AND round = %s",
            (session_id, round_number),
        ).fetchone()
        return row["deadline"] if row else None

    def set_deadline(
        self, session_id: str, round_number: int, deadline: datetime
    ) -> None:
        self._require_exclusive(session_id)
        self.connection.execute(
            """INSERT INTO challenge_timers (session_id, round, deadline)
               VALUES (%s, %s, %s)
               ON CONFLICT (session_id, round) DO UPDATE SET deadline = EXCLUDED.deadline""",
            (session_id, round_number, deadline),
        )

    def record_attempt(
        self,
        attempt_id: str,
        session_id: str,
        player_id: str,
        challenge_id: str,
        answer: str,
        is_correct: bool,
    ) -> None:
        self._require_exclusive(session_id)
        self.connection.execute(
            """INSERT INTO attempts
               (id, session_id, player_id, challenge_id, submitted_answer, is_correct)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (attempt_id, session_id, player_id, challenge_id, answer, is_correct),
        )

    def complete_challenge(
        self, session_id: str, challenge_id: str, player_id: str
    ) -> None:
        self._require_exclusive(session_id)
        row = self.connection.execute(
            """INSERT INTO challenge_completions (session_id, challenge_id, completed_by)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING challenge_id""",
            (session_id, challenge_id, player_id),
        ).fetchone()
        if row is None:
            raise StateConflict()

    def get_winner(self, session_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT winner FROM results WHERE session_id = %s", (session_id,)
        ).fetchone()
        return row["winner"] if row else None

    def finish_escape(
        self, session_id: str, solved_count: int, rounds_played: int
    ) -> None:
        self._require_exclusive(session_id)
        updated = self.connection.execute(
            """UPDATE sessions
               SET phase = 'GAME_OVER', status = 'finished', completed_at = now()
               WHERE id = %s AND status = 'active' AND round = %s
               RETURNING id""",
            (session_id, rounds_played),
        ).fetchone()
        if updated is None:
            raise StateConflict()
        self.connection.execute(
            """INSERT INTO results (session_id, winner, reason, solved_count, rounds_played)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                session_id,
                Winner.NON_MAFIA.value,
                WinReason.ESCAPED.value,
                solved_count,
                rounds_played,
            ),
        )
