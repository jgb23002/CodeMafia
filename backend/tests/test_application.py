import json

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.main import create_app

pytestmark = pytest.mark.postgres


def test_health_verifies_real_database_and_schema(pg_client):
    response = pg_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "schema_version": 2}
    assert response.headers["cache-control"] == "no-store"


def test_real_application_create_join_start_contract(pg_client):
    created = pg_client.post("/api/sessions", json={"display_name": "Host"})
    assert created.status_code == 201
    host = created.json()
    base = f"/api/sessions/{host['room_code']}"
    headers = {"Authorization": f"Bearer {host['player_token']}"}
    assert pg_client.post(base + "/start", json={}, headers=headers).status_code == 409
    guests = []
    for index in range(3):
        joined = pg_client.post(base + "/join", json={"display_name": f"Guest {index}"})
        assert joined.status_code == 201
        guests.append(joined.json())
    assert (
        pg_client.post(base + "/join", json={"display_name": "Fifth"}).status_code
        == 409
    )
    assert (
        pg_client.post(
            base + "/start",
            json={},
            headers={"Authorization": f"Bearer {guests[0]['player_token']}"},
        ).status_code
        == 403
    )
    started = pg_client.post(base + "/start", json={}, headers=headers)
    assert started.status_code == 200
    assert started.json()["phase"] == "SABOTAGE"
    lobby = pg_client.get(base, headers=headers)
    assert lobby.json()["player_count"] == 4
    assert "role" not in lobby.text and "token" not in lobby.text
    schema = pg_client.get("/openapi.json").json()
    assert set(schema["paths"]) == {
        "/health",
        "/api/sessions",
        "/api/sessions/{code}",
        "/api/sessions/{code}/join",
        "/api/sessions/{code}/start",
    }
    assert "answer_key" not in json.dumps(schema)


@pytest.mark.parametrize(
    "method,path,status", [("GET", "/missing", 404), ("PUT", "/health", 405)]
)
def test_global_errors_use_shared_envelope(pg_client, method, path, status):
    response = pg_client.request(method, path)
    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": "HTTP_ERROR",
            "message": "Unable to process the request.",
            "details": {},
        }
    }


def test_validation_errors_never_echo_private_input(pg_client):
    response = pg_client.post(
        "/api/sessions", json={"display_name": "Host", "token": "private-input"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "private-input" not in response.text


def test_request_size_limit_precedes_validation(pg_client):
    response = pg_client.post("/api/sessions", json={"display_name": "a" * 20000})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_cors_allows_configured_frontend_and_rejects_other_origins(pg_client):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    allowed = pg_client.options("/api/sessions", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    rejected = pg_client.options(
        "/api/sessions", headers={**headers, "Origin": "https://unconfigured.example"}
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


def test_health_becomes_unavailable_without_leaking_database_errors(
    pg_client, monkeypatch
):
    def unavailable(database):
        raise psycopg.OperationalError("private-database-password")

    monkeypatch.setattr(Database, "check", unavailable)
    response = pg_client.get("/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "private-database-password" not in response.text


def test_startup_failure_is_sanitized(pg_database, monkeypatch):
    def unavailable(database):
        raise psycopg.OperationalError("private-database-password")

    monkeypatch.setattr(Database, "check", unavailable)
    app = create_app(Settings(database_url=pg_database.url), database=pg_database)
    with (
        pytest.raises(RuntimeError, match="Database is unavailable") as failure,
        TestClient(app),
    ):
        pass
    assert "private-database-password" not in str(failure.value)


def test_unexpected_application_errors_are_sanitized(pg_database, caplog):
    app = create_app(Settings(database_url=pg_database.url), database=pg_database)

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("private-error-value")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-failure")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-error-value" not in response.text + caplog.text
