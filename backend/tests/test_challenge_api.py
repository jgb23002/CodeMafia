"""HTTP contract for GET /challenges and POST /answers (fake storage)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.challenges import ChallengeService, create_challenge_router
from backend.app.sessions import SessionService, create_session_router
from backend.app.sessions.repository import Phase
from backend.tests.challenge_fakes import FakeChallengeRepository


@pytest.fixture
def setup():
    repository = FakeChallengeRepository()
    sessions = SessionService(repository)
    challenges = ChallengeService(repository)
    app = FastAPI()
    app.include_router(create_session_router(lambda: sessions))
    app.include_router(create_challenge_router(lambda: challenges))
    host = sessions.create("Jiya")
    players = [host] + [
        sessions.join(host.room_code, name)
        for name in ("Priyanshi", "Gabriella", "Michael")
    ]
    sessions.start(host.room_code, "Bearer " + host.player_token)
    repository.set_phase(host.room_code, Phase.CHALLENGE, 1)
    with TestClient(app) as client:
        yield client, repository, host.room_code, players


def headers(player):
    return {"Authorization": "Bearer " + player.player_token}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.headers["Cache-Control"] == "no-store"


def test_board_contract_has_no_private_fields(setup):
    client, _, code, players = setup
    response = client.get(
        f"/api/sessions/{code}/challenges", headers=headers(players[0])
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "room_code",
        "phase",
        "round",
        "solved_count",
        "escape_target",
        "total_challenges",
        "deadline",
        "seconds_remaining",
        "challenges",
        "winner",
    }
    assert all(
        set(c) == {"challenge_id", "type", "prompt", "status", "attempts_left"}
        for c in body["challenges"]
    )
    assert "accepted" not in response.text and "answer_key" not in response.text


def test_answer_contract_and_penalty(setup):
    client, _, code, players = setup
    url = f"/api/sessions/{code}/answers"
    wrong = client.post(
        url, json={"challenge_id": "CM01", "answer": "11"}, headers=headers(players[1])
    )
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False and wrong.json()["penalty_seconds"] == 15
    right = client.post(
        url, json={"challenge_id": "CM01", "answer": "12"}, headers=headers(players[2])
    )
    body = right.json()
    assert set(body) == {
        "challenge_id",
        "correct",
        "solved_count",
        "escape_target",
        "attempts_left",
        "penalty_seconds",
        "deadline",
        "seconds_remaining",
        "phase",
        "winner",
    }
    assert body["correct"] is True and body["solved_count"] == 1
    again = client.post(
        url, json={"challenge_id": "CM01", "answer": "12"}, headers=headers(players[3])
    )
    assert_error(again, 409, "CHALLENGE_RESOLVED")


def test_answer_errors_use_shared_envelope(setup):
    client, repository, code, players = setup
    url = f"/api/sessions/{code}/answers"
    assert_error(
        client.post(url, json={"challenge_id": "CM01", "answer": "12"}),
        401,
        "UNAUTHORIZED",
    )
    assert_error(
        client.post(url, json={"challenge_id": "CM01"}, headers=headers(players[0])),
        422,
        "INVALID_REQUEST",
    )
    assert_error(
        client.post(
            url,
            json={"challenge_id": "CM01", "answer": "12", "extra": 1},
            headers=headers(players[0]),
        ),
        422,
        "INVALID_REQUEST",
    )
    assert_error(
        client.post(
            url,
            json={"challenge_id": "CM01", "answer": " "},
            headers=headers(players[0]),
        ),
        422,
        "INVALID_ANSWER",
    )
    repository.set_phase(code, Phase.DISCUSSION)
    assert_error(
        client.post(
            url,
            json={"challenge_id": "CM01", "answer": "12"},
            headers=headers(players[0]),
        ),
        409,
        "WRONG_PHASE",
    )
