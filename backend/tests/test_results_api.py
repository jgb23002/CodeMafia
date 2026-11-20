from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.main import create_app
from backend.app.matches import (
    MatchRepository,
    MatchResult,
    StoredMatchResult,
    Winner,
    WinReason,
)
from backend.app.results import ResultsService, create_results_router
from backend.app.sessions import SessionService
from backend.app.sessions.repository import Phase, Role
from backend.tests.fakes import FakeRepository


class FakeMatchRepository:
    def __init__(self):
        self.results = {}

    def read_result(self, session_id):
        return self.results.get(session_id)


@pytest.fixture
def results_setup():
    repository = FakeRepository()
    session_service = SessionService(repository)
    host = session_service.create("Host")
    players = [host] + [
        session_service.join(host.room_code, f"Guest {index}") for index in range(3)
    ]
    session_service.start(host.room_code, f"Bearer {host.player_token}")
    match_repository = FakeMatchRepository()
    results_service = ResultsService(repository, match_repository)
    app = FastAPI()
    app.include_router(create_results_router(lambda: results_service))
    with TestClient(app) as client:
        yield client, repository, match_repository, host, players


def auth(player):
    return {"Authorization": f"Bearer {player.player_token}"}


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


def finish(repository, match_repository, host):
    repository.rooms[host.room_code] = replace(
        repository.rooms[host.room_code], phase=Phase.GAME_OVER, round=4
    )
    match_repository.results[host.session_id] = StoredMatchResult(
        session_id=host.session_id,
        winner=Winner.NON_MAFIA,
        reason=WinReason.ESCAPED,
        solved_count=8,
        rounds_played=4,
        completed_at=datetime(2026, 11, 9, 20, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    "authorization",
    [None, "not-a-bearer-token", f"Bearer {'x' * 43}"],
)
def test_results_require_valid_bearer_token(results_setup, authorization):
    client, _, _, host, _ = results_setup
    headers = {"Authorization": authorization} if authorization else {}
    response = client.get(f"/api/sessions/{host.room_code}/results", headers=headers)
    assert_error(response, 401, "UNAUTHORIZED")
    assert response.headers["www-authenticate"] == "Bearer"


def test_results_reject_token_from_another_session(results_setup):
    client, repository, match_repository, host, _ = results_setup
    finish(repository, match_repository, host)
    other = SessionService(repository).create("Other")
    assert_error(
        client.get(f"/api/sessions/{host.room_code}/results", headers=auth(other)),
        403,
        "NOT_ROOM_MEMBER",
    )


def test_results_reject_unknown_and_invalid_room_codes(results_setup):
    client, _, _, host, _ = results_setup
    assert_error(
        client.get("/api/sessions/000000/results", headers=auth(host)),
        404,
        "ROOM_NOT_FOUND",
    )
    assert_error(
        client.get("/api/sessions/bad/results", headers=auth(host)),
        422,
        "INVALID_ROOM_CODE",
    )


def test_results_are_unavailable_before_game_over(results_setup):
    client, _, _, host, _ = results_setup
    assert_error(
        client.get(f"/api/sessions/{host.room_code}/results", headers=auth(host)),
        409,
        "GAME_NOT_OVER",
    )


def test_completed_results_reveal_roles_and_zero_scores_to_members(results_setup):
    client, repository, match_repository, host, players = results_setup
    finish(repository, match_repository, host)

    response = client.get(
        f"/api/sessions/{host.room_code}/results", headers=auth(players[1])
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["session_id"] == host.session_id
    assert body["winner"] == "NON_MAFIA"
    assert body["reason"] == "ESCAPED"
    assert body["solved_count"] == 8
    assert body["final_round"] == 4
    assert body["completed_at"] == "2026-11-09T20:00:00Z"
    assert len(body["players"]) == 4
    assert {row["player_id"]: row["role"] for row in body["players"]} == {
        player_id: role.value
        for player_id, role in repository.roles[host.session_id].items()
    }
    assert all(row["score"] == 0 for row in body["players"])
    private_values = [player.player_token for player in players]
    assert all(value not in response.text for value in private_values)
    assert all(
        word not in response.text.lower() for word in ("token", "hash", "answer")
    )


def test_results_openapi_exposes_get_only(results_setup):
    client, _, _, _, _ = results_setup
    schema = client.get("/openapi.json").json()
    operations = schema["paths"]["/api/sessions/{code}/results"]
    assert "get" in operations
    assert "post" not in operations


@pytest.mark.postgres
def test_completed_results_survive_a_new_application_connection(
    pg_database, pg_service, pg_full_room
):
    host, players = pg_full_room
    pg_service.start(host.room_code, f"Bearer {host.player_token}")
    MatchRepository(pg_database).record_result(
        MatchResult(host.session_id, Winner.NON_MAFIA, WinReason.ESCAPED, 8, 1)
    )
    restarted_database = Database(pg_database.url, pg_database.schema)
    app = create_app(
        settings=Settings(database_url=pg_database.url),
        database=restarted_database,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/sessions/{host.room_code}/results", headers=auth(players[2])
        )
    assert response.status_code == 200
    body = response.json()
    assert body["winner"] == "NON_MAFIA"
    assert body["reason"] == "ESCAPED"
    assert body["solved_count"] == 8
    assert body["final_round"] == 1
    assert body["completed_at"].endswith("Z")
    assert len(body["players"]) == 4
    assert {row["role"] for row in body["players"]} == {role.value for role in Role}
    assert all(row["score"] == 0 for row in body["players"])
