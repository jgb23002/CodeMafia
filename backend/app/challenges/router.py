"""Challenge routes. Reuses the session error envelope so clients see one format."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from backend.app.sessions.router import SessionRoute

from .schemas import AnswerInput, AnswerResult, ChallengeBoard
from .service import ChallengeService


def create_challenge_router(
    service_dependency: Callable[..., ChallengeService],
) -> APIRouter:
    router = APIRouter(
        prefix="/api/sessions", tags=["challenges"], route_class=SessionRoute
    )

    @router.get("/{code}/challenges", response_model=ChallengeBoard)
    def get_challenges(
        code: str,
        service: Annotated[ChallengeService, Depends(service_dependency)],
        authorization: Annotated[str | None, Header()] = None,
    ):
        return service.board(code, authorization)

    @router.post("/{code}/answers", response_model=AnswerResult)
    def submit_answer(
        code: str,
        body: AnswerInput,
        service: Annotated[ChallengeService, Depends(service_dependency)],
        authorization: Annotated[str | None, Header()] = None,
    ):
        return service.answer(code, authorization, body.challenge_id, body.answer)

    return router
