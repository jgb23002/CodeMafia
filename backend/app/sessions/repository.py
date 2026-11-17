"""Production persistence contract. No storage implementation or schema lives here.

An adapter must implement these semantics across processes, not merely satisfy
the type signatures. See docs/SESSION_INTEGRATION.md for PostgreSQL requirements.
"""

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol


class Role(str, Enum):
    MAFIA = "MAFIA"
    DETECTIVE = "DETECTIVE"
    HACKER = "HACKER"
    CIVILIAN = "CIVILIAN"


class Phase(str, Enum):
    WAITING = "WAITING"
    SABOTAGE = "SABOTAGE"
    CHALLENGE = "CHALLENGE"
    DISCUSSION = "DISCUSSION"
    VOTING = "VOTING"
    ROUND_RESULTS = "ROUND_RESULTS"
    GAME_OVER = "GAME_OVER"


@dataclass(frozen=True)
class Room:
    session_id: str
    room_code: str
    host_player_id: str
    phase: Phase = Phase.WAITING
    round: int = 0


@dataclass(frozen=True)
class Player:
    player_id: str
    session_id: str
    display_name: str
    token_hash: str
    is_active: bool = True


class RepositoryError(Exception):
    """Persistence failure; internal exception contents must never reach clients."""


class RoomCodeCollision(RepositoryError):
    """Only the room-code unique constraint conflicted; transaction must roll back."""


class IdentityCollision(RepositoryError):
    """A generated player/session UUID or token hash conflicted; roll back."""


class StateConflict(RepositoryError):
    """A conditional update failed; roll back without replacing existing state."""


class SessionTransaction(Protocol):
    def create_room(self, room: Room, host: Player) -> None:
        """Insert room and host in this transaction, with uniqueness/membership.

        Raise RoomCodeCollision or IdentityCollision only for their corresponding
        uniqueness constraints. Any other storage failure is RepositoryError.
        """
        ...

    def get_room(
        self, code: str, *, lock: Literal["shared", "exclusive"]
    ) -> Room | None:
        """Acquire the room row lock until transaction exit, then read fresh state.

        Shared locks stabilize lobby snapshots. Exclusive locks serialize ALL
        membership/phase writers, including future features, on the same row.
        """
        ...

    def find_player_by_token_hash(self, digest: str) -> Player | None:
        """Look up a globally unique digest; never accept raw credentials."""
        ...

    def list_players(self, session_id: str) -> Sequence[Player]:
        """Return all identities in stable order, including inactive players."""
        ...

    def add_player(self, player: Player) -> None:
        """Insert after holding the room's exclusive lock; enforce uniqueness."""
        ...

    def get_roles(self, session_id: str) -> Mapping[str, Role]:
        """Return private player-ID -> role assignments for server-side use only."""
        ...

    def start_game(self, session_id: str, assignments: Mapping[str, Role]) -> None:
        """Persist four roles + SABOTAGE/round 1/lifecycle status in this transaction.

        Require the exclusive room lock and a conditional WAITING transition.
        Reject preexisting assignments. Never commit internally. A failure after
        any assignment/update must roll back every change at transaction exit.
        """
        ...


class SessionRepository(Protocol):
    def transaction(self) -> AbstractContextManager[SessionTransaction]:
        """Fresh unit of work: commit on success, roll back on every failure.

        Commit errors must propagate BEFORE the context exits successfully.
        Close/release connections and locks on all exit paths. A repository
        instance is shared; individual transaction/connection objects are not.
        """
        ...
