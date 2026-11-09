"""Router factory only. Michael owns the FastAPI application and shared handlers."""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from .schemas import Lobby, PlayerInput, Registration, StartedGame, StartInput
from .service import SessionError, SessionService

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, *, details=None, headers=None):
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {"code": code, "message": message, "details": details or {}},
        },
    )


class SessionRoute(APIRoute):
    """Temporary feature-scoped envelope; no application/global settings replaced."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                response = await original(request)
            except SessionError as exc:
                response = error_response(
                    exc.status,
                    exc.code,
                    exc.message,
                    headers=(
                        {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
                    ),
                )
            except RequestValidationError as exc:
                response = error_response(
                    422,
                    "INVALID_REQUEST",
                    "Invalid request fields.",
                    details={
                        "fields": [
                            {"location": list(e["loc"]), "type": e["type"]}
                            for e in exc.errors()
                        ],
                    },
                )
            except HTTPException as exc:
                response = error_response(
                    exc.status_code, "HTTP_ERROR", "Unable to process the request."
                )
            except Exception as exc:  # noqa: BLE001 -- sanitize unexpected failures at the public boundary
                # Do not log exceptions/SQL parameters/request bodies: they can
                # include credentials, private assignments, or answer keys.
                logger.error(
                    "session_request_failed", extra={"error_type": type(exc).__name__}
                )
                response = error_response(
                    500, "INTERNAL_ERROR", "Unable to complete the request."
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return handler


def create_session_router(
    service_dependency: Callable[..., SessionService],
) -> APIRouter:
    router = APIRouter(
        prefix="/api/sessions", tags=["sessions"], route_class=SessionRoute
    )

    @router.post("", status_code=201, response_model=Registration)
    def create_room(
        body: PlayerInput,
        service: Annotated[SessionService, Depends(service_dependency)],
    ):
        return service.create(body.display_name)

    @router.post("/{code}/join", status_code=201, response_model=Registration)
    def join_room(
        code: str,
        body: PlayerInput,
        service: Annotated[SessionService, Depends(service_dependency)],
    ):
        return service.join(code, body.display_name)

    @router.get("/{code}", response_model=Lobby)
    def get_room(
        code: str,
        service: Annotated[SessionService, Depends(service_dependency)],
        authorization: Annotated[str | None, Header()] = None,
    ):
        return service.lobby(code, authorization)

    @router.post("/{code}/start", response_model=StartedGame)
    def start_game(
        code: str,
        body: StartInput,
        service: Annotated[SessionService, Depends(service_dependency)],
        authorization: Annotated[str | None, Header()] = None,
    ):
        return service.start(code, authorization)

    return router
