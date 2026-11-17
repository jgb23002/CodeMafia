"""Run with uvicorn backend.app.main:create_app --factory --env-file .env."""

from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.db.migrations import current_version
from backend.app.errors import (
    error_response,
    http_error,
    unexpected_error,
    validation_error,
)
from backend.app.middleware import RequestLimitsMiddleware
from backend.app.sessions import SessionService, create_session_router
from backend.app.sessions.postgres import PostgresRepository


def create_app(
    settings: Settings | None = None, *, database: Database | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    database = database or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(database.check)
            if await run_in_threadpool(current_version, database) != 1:
                raise RuntimeError("Schema version mismatch.")
        except (psycopg.Error, RuntimeError):
            raise RuntimeError(
                "Database is unavailable or migrations are missing. Run the documented database setup."
            ) from None
        yield

    app = FastAPI(title="CodeMafia", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    service = SessionService(PostgresRepository(database))
    app.include_router(create_session_router(lambda: service))
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(Exception, unexpected_error)
    app.add_middleware(RequestLimitsMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["operations"])
    def health():
        try:
            database.check()
            version = current_version(database)
            if version != 1:
                raise RuntimeError("Schema version mismatch.")
        except (psycopg.Error, RuntimeError):
            return error_response(503, "SERVICE_UNAVAILABLE", "Database is not ready.")
        return {"status": "ok", "database": "ok", "schema_version": version}

    return app
