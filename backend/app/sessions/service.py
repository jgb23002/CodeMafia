"""Session rules independent of application bootstrap and physical database models."""

import hashlib
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal
from uuid import uuid4

from .repository import (
    IdentityCollision,
    Phase,
    Player,
    RepositoryError,
    Role,
    Room,
    RoomCodeCollision,
    SessionRepository,
    SessionTransaction,
    StateConflict,
)
from .schemas import Lobby, LobbyPlayer, PlayerInput, Registration, StartedGame

CAPACITY = 4
ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_REGISTRATION_ATTEMPTS = 8
TOKEN_BYTES = 32


class SessionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def new_room_code() -> str:
    return "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def bearer_hash(authorization: str | None) -> str:
    if authorization:
        parts = authorization.split()
        if (
            len(parts) == 2
            and parts[0].lower() == "bearer"
            and re.fullmatch(r"[A-Za-z0-9_-]{43}", parts[1])
        ):
            return token_hash(parts[1])
    raise SessionError(401, "UNAUTHORIZED", "A valid player token is required.")


def validate_code(code: str) -> None:
    if not re.fullmatch(r"[A-Z0-9]{6}", code):
        raise SessionError(
            422,
            "INVALID_ROOM_CODE",
            "Room code must be six uppercase letters or digits.",
        )


def new_player(session_id: str, name: str) -> tuple[Player, str]:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return Player(str(uuid4()), session_id, name, token_hash(token)), token


class SessionService:
    def __init__(self, repository: SessionRepository):
        self.repository = repository

    @contextmanager
    def _transaction(self) -> Iterator[SessionTransaction]:
        try:
            with self.repository.transaction() as transaction:
                yield transaction
        except (RoomCodeCollision, IdentityCollision):
            raise  # Registration retries after the failed transaction has exited.
        except StateConflict:
            raise SessionError(
                409, "STATE_CONFLICT", "The room state changed. Refresh and retry."
            ) from None
        except RepositoryError:
            raise SessionError(
                500, "PERSISTENCE_ERROR", "Unable to persist the session operation."
            ) from None

    @staticmethod
    def _room(
        tx: SessionTransaction,
        code: str,
        *,
        lock: Literal["shared", "exclusive"] = "exclusive",
    ) -> Room:
        room = tx.get_room(code, lock=lock)
        if room is None:
            raise SessionError(404, "ROOM_NOT_FOUND", "Room not found.")
        return room

    @staticmethod
    def _authenticate(tx: SessionTransaction, digest: str) -> Player:
        player = tx.find_player_by_token_hash(digest)
        if player is None:
            raise SessionError(401, "UNAUTHORIZED", "A valid player token is required.")
        return player

    @staticmethod
    def _member(player: Player, room: Room) -> None:
        if player.session_id != room.session_id:
            raise SessionError(
                403, "NOT_ROOM_MEMBER", "This player does not belong to the room."
            )

    @staticmethod
    def _waiting(room: Room) -> None:
        if room.phase != Phase.WAITING or room.round != 0:
            raise SessionError(
                409,
                "GAME_ALREADY_STARTED",
                "The room is no longer waiting for players.",
            )

    @staticmethod
    def _registration(
        room: Room, player: Player, token: str, count: int
    ) -> Registration:
        return Registration(
            session_id=room.session_id,
            room_code=room.room_code,
            player_id=player.player_id,
            player_token=token,
            is_host=room.host_player_id == player.player_id,
            phase=Phase.WAITING,
            player_count=count,
        )

    def create(self, display_name: str) -> Registration:
        name = PlayerInput(display_name=display_name).display_name
        failure_code = "ROOM_CREATION_FAILED"
        for _ in range(MAX_REGISTRATION_ATTEMPTS):
            session_id = str(uuid4())
            host, token = new_player(session_id, name)
            room = Room(session_id, new_room_code(), host.player_id)
            try:
                with self._transaction() as tx:
                    tx.create_room(room, host)
                    response = self._registration(room, host, token, 1)
                return response  # Only after the adapter successfully commits.
            except RoomCodeCollision:
                failure_code = "ROOM_CREATION_FAILED"
            except IdentityCollision:
                failure_code = "IDENTITY_CREATION_FAILED"
        raise SessionError(500, failure_code, "Unable to create a room. Please retry.")

    def join(self, code: str, display_name: str) -> Registration:
        validate_code(code)
        name = PlayerInput(display_name=display_name).display_name
        for _ in range(MAX_REGISTRATION_ATTEMPTS):
            try:
                with self._transaction() as tx:
                    room = self._room(tx, code)
                    self._waiting(room)
                    count = len(tx.list_players(room.session_id))
                    if count >= CAPACITY:
                        raise SessionError(
                            409, "ROOM_FULL", "The room already has four players."
                        )
                    player, token = new_player(room.session_id, name)
                    tx.add_player(player)
                    response = self._registration(room, player, token, count + 1)
                return response
            except IdentityCollision:
                continue
        raise SessionError(
            500,
            "IDENTITY_CREATION_FAILED",
            "Unable to register a player. Please retry.",
        )

    def lobby(self, code: str, authorization: str | None) -> Lobby:
        digest = bearer_hash(authorization)
        validate_code(code)
        with self._transaction() as tx:
            player = self._authenticate(tx, digest)
            room = self._room(tx, code, lock="shared")
            self._member(player, room)
            players = tx.list_players(room.session_id)
            response = Lobby(
                room_code=room.room_code,
                phase=room.phase,
                host_player_id=room.host_player_id,
                players=[
                    LobbyPlayer(
                        player_id=p.player_id,
                        display_name=p.display_name,
                        is_host=p.player_id == room.host_player_id,
                        is_active=p.is_active,
                    )
                    for p in players
                ],
                player_count=len(players),
                capacity=CAPACITY,
            )
        return response

    def start(self, code: str, authorization: str | None) -> StartedGame:
        digest = bearer_hash(authorization)
        validate_code(code)
        with self._transaction() as tx:
            caller = self._authenticate(tx, digest)
            room = self._room(tx, code)
            self._member(caller, room)
            if caller.player_id != room.host_player_id:
                raise SessionError(
                    403, "HOST_ONLY", "Only the host can start the game."
                )
            self._waiting(room)
            players = tx.list_players(room.session_id)
            if len(players) != CAPACITY:
                raise SessionError(
                    409,
                    "FOUR_PLAYERS_REQUIRED",
                    "Exactly four players are required to start.",
                )
            if not all(player.is_active for player in players):
                raise SessionError(
                    409, "INACTIVE_PLAYERS", "All four players must be active to start."
                )
            if tx.get_roles(room.session_id):
                raise SessionError(
                    409, "ROLES_ALREADY_ASSIGNED", "Roles have already been assigned."
                )
            roles = list(Role)
            secrets.SystemRandom().shuffle(roles)
            assignments = {
                player.player_id: role
                for player, role in zip(players, roles, strict=True)
            }
            tx.start_game(room.session_id, assignments)
            response = StartedGame(
                room_code=code,
                phase=Phase.SABOTAGE,
                round=1,
                player_count=CAPACITY,
                my_role=assignments[caller.player_id],
            )
        return response
