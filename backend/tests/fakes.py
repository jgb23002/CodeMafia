"""TEST ONLY: coarse in-process lock + snapshot rollback, never production storage.

This fake cannot prove PostgreSQL isolation, constraints, multi-worker locking,
durability, migrations, or driver exception mapping. It enforces lock requests
so tests catch services that omit the repository's concurrency contract.
"""

from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from threading import RLock

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


class FakeRepository:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.players: dict[str, Player] = {}
        self.roles: dict[str, dict[str, Role]] = {}
        self.lock = RLock()
        self.fail_at: str | None = None
        self.transactions = 0

    def fail(self, point):
        if self.fail_at == point:
            raise RepositoryError("PRIVATE_TOKEN / MAFIA / ANSWER_KEY / diagnostic SQL")

    def snapshot(self):
        with self.lock:
            return deepcopy((self.rooms, self.players, self.roles))

    @contextmanager
    def transaction(self):
        with self.lock:
            self.transactions += 1
            before = self.snapshot()
            try:
                self.fail("begin")
                yield FakeTransaction(self)
                self.fail("commit")
            except BaseException:
                self.rooms, self.players, self.roles = before
                raise


class FakeTransaction:
    def __init__(self, repository):
        self.repo = repository
        self.locks: dict[str, str] = {}

    def _require_lock(self, session_id, exclusive=False):
        mode = self.locks.get(session_id)
        if mode is None or (exclusive and mode != "exclusive"):
            raise AssertionError(
                "Service must acquire the appropriate room lock first."
            )

    def _check_identity(self, player):
        if player.player_id in self.repo.players or any(
            p.token_hash == player.token_hash for p in self.repo.players.values()
        ):
            raise IdentityCollision("player UUID or token hash collision")

    def create_room(self, room, host):
        if room.room_code in self.repo.rooms:
            raise RoomCodeCollision("room code collision")
        if any(r.session_id == room.session_id for r in self.repo.rooms.values()):
            raise IdentityCollision("session UUID collision")
        self._check_identity(host)
        assert (
            host.session_id == room.session_id and host.player_id == room.host_player_id
        )
        self.repo.rooms[room.room_code] = room
        self.repo.fail("after_room")
        self.repo.players[host.player_id] = host
        self.repo.fail("after_host")

    def get_room(self, code, *, lock):
        assert lock in ("shared", "exclusive")
        room = self.repo.rooms.get(code)
        if room:
            self.locks[room.session_id] = lock
        return room

    def find_player_by_token_hash(self, digest):
        return next(
            (p for p in self.repo.players.values() if p.token_hash == digest), None
        )

    def list_players(self, session_id):
        self._require_lock(session_id)
        return sorted(
            (p for p in self.repo.players.values() if p.session_id == session_id),
            key=lambda p: p.player_id,
        )

    def add_player(self, player):
        self._require_lock(player.session_id, exclusive=True)
        self._check_identity(player)
        self.repo.players[player.player_id] = player
        self.repo.fail("after_player")

    def get_roles(self, session_id):
        self._require_lock(session_id)
        return dict(self.repo.roles.get(session_id, {}))

    def start_game(self, session_id: str, assignments: Mapping[str, Role]):
        self._require_lock(session_id, exclusive=True)
        room = next(r for r in self.repo.rooms.values() if r.session_id == session_id)
        if room.phase != Phase.WAITING or self.repo.roles.get(session_id):
            raise StateConflict("conditional start failed")
        assert set(assignments) == {p.player_id for p in self.list_players(session_id)}
        assert len(assignments) == 4 and set(assignments.values()) == set(Role)
        self.repo.roles[session_id] = {}
        for index, (player_id, role) in enumerate(assignments.items(), 1):
            self.repo.roles[session_id][player_id] = role
            self.repo.fail(f"after_role_{index}")
        self.repo.rooms[room.room_code] = replace(room, phase=Phase.SABOTAGE, round=1)
        self.repo.fail("after_start_update")
