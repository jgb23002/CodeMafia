"""Shared safe JSON errors. Never echo credentials, SQL, or validation inputs."""

import logging

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def error_response(status: int, code: str, message: str, *, details=None, headers=None):
    return JSONResponse(
        status_code=status,
        headers={"Cache-Control": "no-store", **(headers or {})},
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


async def http_error(request, error: HTTPException):
    return error_response(
        error.status_code,
        "HTTP_ERROR",
        "Unable to process the request.",
        headers=error.headers,
    )


async def validation_error(request, error: RequestValidationError):
    return error_response(
        422,
        "INVALID_REQUEST",
        "Invalid request fields.",
        details={
            "fields": [
                {"location": list(item["loc"]), "type": item["type"]}
                for item in error.errors()
            ]
        },
    )


async def unexpected_error(request, error: Exception):
    logger.error("request_failed", extra={"error_type": type(error).__name__})
    return error_response(500, "INTERNAL_ERROR", "Unable to complete the request.")
