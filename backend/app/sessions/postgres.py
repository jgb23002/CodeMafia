"""PostgreSQL session adapter. Every operation has its own connection/transaction."""

from collections.abc import Mapping
from contextlib import contextmanager

import psycopg

from backend.app.database import Database
from backend.app.sessions.repository import (
    IdentityCollision,
    Phase,
    Player,
    RepositoryError,
    Role,
    Room,
    RoomCodeCollision,
    StateConflict,
)


class PostgresRepository:
    def __init__(self, database: Database):
        self.database = database

    @contextmanager
    def transaction(self):
        try:
            with self.database.connect() as connection:
                yield PostgresTransaction(connection)
                # The connection context commits before returning success and
                # rolls back on domain errors, SQL errors, or failed commits.
        except psycopg.errors.UniqueViolation as error:
            constraint = error.diag.constraint_name
            if constraint == "sessions_room_code_key":
                raise RoomCodeCollision() from None
            if constraint in {
                "sessions_pkey",
                "players_pkey",
                "players_token_hash_key",
            }:
                raise IdentityCollision() from None
            raise RepositoryError() from None
        except psycopg.Error:
            raise RepositoryError() from None


class PostgresTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.exclusive_locks: set[str] = set()

    def create_room(self, room: Room, host: Player) -> None:
        if host.player_id != room.host_player_id or host.session_id != room.session_id:
            raise RepositoryError()
        self.connection.execute(
            "INSERT INTO sessions (id, room_code, host_player_id) VALUES (%s, %s, %s)",
            (room.session_id, room.room_code, room.host_player_id),
        )
        self._insert_player(host)

    def get_room(self, code: str, *, lock: str) -> Room | None:
        if lock not in {"shared", "exclusive"}:
            raise ValueError("Unknown lock mode.")
        suffix = "FOR UPDATE" if lock == "exclusive" else "FOR SHARE"
        row = self.connection.execute(
            "SELECT id, room_code, host_player_id, phase, round FROM sessions WHERE room_code = %s "
            + suffix,
            (code,),
        ).fetchone()
        if row is None:
            return None
        if lock == "exclusive":
            self.exclusive_locks.add(str(row["id"]))
        return Room(
            str(row["id"]),
            row["room_code"],
            str(row["host_player_id"]),
            Phase(row["phase"]),
            row["round"],
        )

    @staticmethod
    def _player(row) -> Player:
        return Player(
            str(row["id"]),
            str(row["session_id"]),
            row["display_name"],
            row["token_hash"],
            row["is_active"],
        )

    def find_player_by_token_hash(self, digest: str) -> Player | None:
        row = self.connection.execute(
            "SELECT id, session_id, display_name, token_hash, is_active FROM players WHERE token_hash = %s",
            (digest,),
        ).fetchone()
        return self._player(row) if row else None

    def list_players(self, session_id: str) -> list[Player]:
        rows = self.connection.execute(
            "SELECT id, session_id, display_name, token_hash, is_active FROM players WHERE session_id = %s ORDER BY created_at, id",
            (session_id,),
        )
        return [self._player(row) for row in rows]

    def _insert_player(self, player: Player) -> None:
        self.connection.execute(
            "INSERT INTO players (id, session_id, display_name, token_hash, is_active) VALUES (%s, %s, %s, %s, %s)",
            (
                player.player_id,
                player.session_id,
                player.display_name,
                player.token_hash,
                player.is_active,
            ),
        )

    def add_player(self, player: Player) -> None:
        if player.session_id not in self.exclusive_locks:
            raise RepositoryError()
        self._insert_player(player)

    def get_roles(self, session_id: str) -> dict[str, Role]:
        rows = self.connection.execute(
            "SELECT player_id, role FROM role_assignments WHERE session_id = %s",
            (session_id,),
        )
        return {str(row["player_id"]): Role(row["role"]) for row in rows}

    def _insert_assignment(self, session_id: str, player_id: str, role: Role) -> None:
        self.connection.execute(
            "INSERT INTO role_assignments (session_id, player_id, role) VALUES (%s, %s, %s)",
            (session_id, player_id, role.value),
        )

    def start_game(self, session_id: str, assignments: Mapping[str, Role]) -> None:
        if session_id not in self.exclusive_locks:
            raise RepositoryError()
        players = self.list_players(session_id)
        if (
            len(players) != 4
            or not all(player.is_active for player in players)
            or set(assignments) != {player.player_id for player in players}
            or set(assignments.values()) != set(Role)
            or self.get_roles(session_id)
        ):
            raise StateConflict()
        updated = self.connection.execute(
            """UPDATE sessions SET phase = 'SABOTAGE', round = 1, status = 'active', started_at = now()
               WHERE id = %s AND phase = 'WAITING' AND round = 0 AND status = 'waiting'
               RETURNING id""",
            (session_id,),
        ).fetchone()
        if updated is None:
            raise StateConflict()
        for player_id, role in assignments.items():
            self._insert_assignment(session_id, player_id, role)
