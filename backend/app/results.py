"""Authenticated read-only projection of completed match results."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from backend.app.matches import MatchRepository, Winner, WinReason
from backend.app.sessions.repository import (
    Phase,
    RepositoryError,
    Role,
    SessionRepository,
)
from backend.app.sessions.router import SessionRoute
from backend.app.sessions.service import (
    CAPACITY,
    SessionError,
    bearer_hash,
    validate_code,
)


class PlayerResult(BaseModel):
    player_id: str
    role: Role
    score: Literal[0] = 0


class ResultsResponse(BaseModel):
    session_id: str
    winner: Winner
    reason: WinReason
    solved_count: int
    final_round: int
    completed_at: datetime
    players: list[PlayerResult]


class ResultsService:
    def __init__(
        self, session_repository: SessionRepository, match_repository: MatchRepository
    ):
        self.session_repository = session_repository
        self.match_repository = match_repository

    def results(self, code: str, authorization: str | None) -> ResultsResponse:
        digest = bearer_hash(authorization)
        validate_code(code)
        try:
            with self.session_repository.transaction() as transaction:
                caller = transaction.find_player_by_token_hash(digest)
                if caller is None:
                    raise SessionError(
                        401, "UNAUTHORIZED", "A valid player token is required."
                    )
                room = transaction.get_room(code, lock="shared")
                if room is None:
                    raise SessionError(404, "ROOM_NOT_FOUND", "Room not found.")
                if caller.session_id != room.session_id:
                    raise SessionError(
                        403,
                        "NOT_ROOM_MEMBER",
                        "This player does not belong to the room.",
                    )
                if room.phase != Phase.GAME_OVER:
                    raise SessionError(
                        409, "GAME_NOT_OVER", "Match results are not available yet."
                    )
                players = transaction.list_players(room.session_id)
                roles = transaction.get_roles(room.session_id)
        except RepositoryError:
            raise SessionError(
                500, "PERSISTENCE_ERROR", "Unable to retrieve match results."
            ) from None

        try:
            stored = self.match_repository.read_result(room.session_id)
        except RepositoryError:
            raise SessionError(
                500, "PERSISTENCE_ERROR", "Unable to retrieve match results."
            ) from None
        if (
            stored is None
            or len(players) != CAPACITY
            or set(roles) != {player.player_id for player in players}
        ):
            raise SessionError(
                500, "PERSISTENCE_ERROR", "Unable to retrieve match results."
            )
        return ResultsResponse(
            session_id=stored.session_id,
            winner=stored.winner,
            reason=stored.reason,
            solved_count=stored.solved_count,
            final_round=stored.rounds_played,
            completed_at=stored.completed_at,
            players=[
                PlayerResult(player_id=player.player_id, role=roles[player.player_id])
                for player in players
            ],
        )


def create_results_router(
    service_dependency: Callable[..., ResultsService],
) -> APIRouter:
    router = APIRouter(
        prefix="/api/sessions", tags=["results"], route_class=SessionRoute
    )

    @router.get("/{code}/results", response_model=ResultsResponse)
    def get_results(
        code: str,
        service: Annotated[ResultsService, Depends(service_dependency)],
        authorization: Annotated[str | None, Header()] = None,
    ):
        return service.results(code, authorization)

    return router
