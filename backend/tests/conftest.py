"""A test-only FastAPI harness; not the teammate-owned production app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.sessions import SessionService, create_session_router
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
