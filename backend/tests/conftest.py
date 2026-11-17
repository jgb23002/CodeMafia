"""Unit harness plus isolated real-PostgreSQL/application fixtures."""

import os
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.db.migrations import migrate
from backend.app.main import create_app
from backend.app.sessions import SessionService, create_session_router
from backend.app.sessions.postgres import PostgresRepository
from backend.tests.fakes import FakeRepository


@pytest.fixture
def repository():
    return FakeRepository()


@pytest.fixture
def service(repository):
    return SessionService(repository)


@pytest.fixture
def app(service):
    app = FastAPI()
    app.include_router(create_session_router(lambda: service))
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def full_room(service):
    host = service.create("Jiya")
    players = [host] + [
        service.join(host.room_code, name)
        for name in (
            "Priyanshi",
            "Gabriella",
            "Michael",
        )
    ]
    return host, players


@pytest.fixture
def pg_database():
    url = os.environ.get("CODEMAFIA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set CODEMAFIA_TEST_DATABASE_URL to run real PostgreSQL tests.")
    if not conninfo_to_dict(url).get("dbname", "").endswith("_test"):
        pytest.fail("Refusing database tests: database name must end in _test.")
    schema = "phase1_" + uuid4().hex
    with psycopg.connect(url, autocommit=True, connect_timeout=5) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    database = Database(url, schema=schema)
    try:
        migrate(database)
        yield database
    finally:
        with psycopg.connect(url, autocommit=True, connect_timeout=5) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.fixture
def pg_service(pg_database):
    return SessionService(PostgresRepository(pg_database))


@pytest.fixture
def pg_full_room(pg_service):
    host = pg_service.create("Host")
    players = [host] + [
        pg_service.join(host.room_code, f"Guest {index}") for index in range(3)
    ]
    return host, players


@pytest.fixture
def pg_client(pg_database):
    app = create_app(Settings(database_url=pg_database.url), database=pg_database)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
