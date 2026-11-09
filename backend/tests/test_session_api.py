import hashlib
from dataclasses import replace
from uuid import UUID

import pytest

import backend.app.sessions.service as session_module
from backend.app.sessions.repository import Phase, Role


def auth(player):
    token = (
        player.player_token
        if hasattr(player, "player_token")
        else player["player_token"]
    )
    return {"Authorization": "Bearer " + token}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {
        "code",
        "message",
        "details",
    }
    assert body["error"]["code"] == code and isinstance(body["error"]["details"], dict)
    assert response.headers["Cache-Control"] == "no-store"


def test_create_room_and_private_credential_storage(client, repository):
    response = client.post("/api/sessions", json={"display_name": " Jiya "})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "session_id",
        "room_code",
        "player_id",
        "player_token",
        "is_host",
        "phase",
        "player_count",
    }
    assert UUID(body["session_id"]).version == UUID(body["player_id"]).version == 4
    assert (
        body["is_host"] is True
        and body["phase"] == "WAITING"
        and body["player_count"] == 1
    )
    assert len(body["room_code"]) == 6 and len(body["player_token"]) == 43
    player = repository.players[body["player_id"]]
    room = repository.rooms[body["room_code"]]
    assert (
        player.display_name == "Jiya"
        and player.session_id == room.session_id == body["session_id"]
    )
    assert room.host_player_id == player.player_id and room.round == 0
    assert (
        player.token_hash
        == hashlib.sha256(body["player_token"].encode("ascii")).hexdigest()
    )
    assert body["player_token"] not in repr(repository.snapshot())
    assert repository.roles == {}
    assert response.headers["Cache-Control"] == "no-store"


def test_join_returns_distinct_identity(client, service, repository):
    host = service.create("Jiya")
    response = client.post(
        f"/api/sessions/{host.room_code}/join", json={"display_name": "Priyanshi"}
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == set(host.model_dump())
    assert body["session_id"] == host.session_id and body["room_code"] == host.room_code
    assert (
        body["is_host"] is False
        and body["phase"] == "WAITING"
        and body["player_count"] == 2
    )
    assert (
        body["player_id"] != host.player_id
        and body["player_token"] != host.player_token
    )
    assert len(repository.players) == 2


def test_same_display_name_is_allowed_for_distinct_identities(client, service):
    host = service.create("Jiya")
    response = client.post(
        f"/api/sessions/{host.room_code}/join", json={"display_name": "Jiya"}
    )
    assert (
        response.status_code == 201 and response.json()["player_id"] != host.player_id
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"display_name": ""},
        {"display_name": " "},
        {"display_name": "x" * 41},
        {"display_name": None},
        {"display_name": 1},
        {"display_name": "a\nb"},
        {"display_name": "Jiya", "role": "MAFIA"},
        {"display_name": "Jiya", "is_host": True},
    ],
)
@pytest.mark.parametrize("operation", ["create", "join"])
def test_invalid_registration(client, service, repository, payload, operation):
    path = "/api/sessions"
    if operation == "join":
        path += f"/{service.create('Host').room_code}/join"
    before = repository.snapshot()
    assert_error(client.post(path, json=payload), 422, "INVALID_REQUEST")
    assert repository.snapshot() == before


@pytest.mark.parametrize(
    "code,status,error",
    [
        ("ABC", 422, "INVALID_ROOM_CODE"),
        ("abc123", 422, "INVALID_ROOM_CODE"),
        ("000000", 404, "ROOM_NOT_FOUND"),
    ],
)
@pytest.mark.parametrize("operation", ["join", "lobby", "start"])
def test_invalid_or_unknown_room(client, service, code, status, error, operation):
    host = service.create("Host")
    if operation == "join":
        response = client.post(
            f"/api/sessions/{code}/join", json={"display_name": "Guest"}
        )
    elif operation == "lobby":
        response = client.get(f"/api/sessions/{code}", headers=auth(host))
    else:
        response = client.post(
            f"/api/sessions/{code}/start", json={}, headers=auth(host)
        )
    assert_error(response, status, error)


def test_fifth_player_rejected(client, repository, full_room):
    host, _ = full_room
    before = repository.snapshot()
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/join", json={"display_name": "Fifth"}
        ),
        409,
        "ROOM_FULL",
    )
    assert repository.snapshot() == before


def test_lobby_allows_all_members_and_only_public_fields(client, full_room):
    host, players = full_room
    for player in players:
        response = client.get(f"/api/sessions/{host.room_code}", headers=auth(player))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "room_code",
            "phase",
            "host_player_id",
            "players",
            "player_count",
            "capacity",
        }
        assert (
            body["host_player_id"] == host.player_id
            and body["player_count"] == body["capacity"] == 4
        )
        assert {p["player_id"] for p in body["players"]} == {
            p.player_id for p in players
        }
        for participant in body["players"]:
            assert set(participant) == {
                "player_id",
                "display_name",
                "is_host",
                "is_active",
            }
            assert participant["is_host"] == (
                participant["player_id"] == host.player_id
            )
            assert participant["is_active"] is True
        assert all(p.player_token not in response.text for p in players)


@pytest.mark.parametrize(
    "authorization", [None, "Bearer bad", "Basic abc", "Bearer " + "x" * 43]
)
@pytest.mark.parametrize("operation", ["lobby", "start"])
def test_missing_malformed_unknown_tokens(client, service, authorization, operation):
    host = service.create("Host")
    headers = {} if authorization is None else {"Authorization": authorization}
    if operation == "lobby":
        response = client.get(f"/api/sessions/{host.room_code}", headers=headers)
    else:
        response = client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=headers
        )
    assert_error(response, 401, "UNAUTHORIZED")
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("operation", ["lobby", "start"])
def test_tampered_token_denied(client, full_room, operation):
    host, _ = full_room
    tampered = ("A" if host.player_token[0] != "A" else "B") + host.player_token[1:]
    headers = {"Authorization": "Bearer " + tampered}
    if operation == "lobby":
        response = client.get(f"/api/sessions/{host.room_code}", headers=headers)
    else:
        response = client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=headers
        )
    assert_error(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize("operation", ["lobby", "start"])
def test_other_session_token_forbidden(client, service, operation):
    first, second = service.create("First"), service.create("Second")
    if operation == "lobby":
        response = client.get(f"/api/sessions/{first.room_code}", headers=auth(second))
    else:
        response = client.post(
            f"/api/sessions/{first.room_code}/start", json={}, headers=auth(second)
        )
    assert_error(response, 403, "NOT_ROOM_MEMBER")


def test_host_start_exact_roles_private_response(
    client, repository, full_room, monkeypatch
):
    host, players = full_room
    calls = []

    def shuffle(self, roles):
        calls.append(tuple(roles))
        roles.reverse()

    monkeypatch.setattr(session_module.secrets.SystemRandom, "shuffle", shuffle)
    response = client.post(
        f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"room_code", "phase", "round", "player_count", "my_role"}
    assert (
        body["phase"] == "SABOTAGE" and body["round"] == 1 and body["player_count"] == 4
    )
    assert calls == [tuple(Role)]
    assignments = repository.roles[host.session_id]
    assert len(assignments) == 4 and set(assignments.values()) == set(Role)
    assert set(assignments) == {p.player_id for p in players}
    assert body["my_role"] == assignments[host.player_id]
    assert repository.rooms[host.room_code].phase == Phase.SABOTAGE
    assert repository.rooms[host.room_code].round == 1
    for player in players:
        snapshot = client.get(f"/api/sessions/{host.room_code}", headers=auth(player))
        assert snapshot.status_code == 200 and snapshot.json()["phase"] == "SABOTAGE"
        assert not any(role.value in snapshot.text for role in Role)
        assert all(
            secret not in snapshot.text
            for secret in ("token", "hash", "answer", "secret")
        )


@pytest.mark.parametrize("size", [1, 2, 3])
def test_start_requires_four_players(client, service, repository, size):
    host = service.create("Host")
    for index in range(size - 1):
        service.join(host.room_code, str(index))
    before = repository.snapshot()
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "FOUR_PLAYERS_REQUIRED",
    )
    assert repository.snapshot() == before


def test_only_host_can_start(client, full_room, repository):
    host, players = full_room
    before = repository.snapshot()
    for guest in players[1:]:
        assert_error(
            client.post(
                f"/api/sessions/{host.room_code}/start", json={}, headers=auth(guest)
            ),
            403,
            "HOST_ONLY",
        )
    assert repository.snapshot() == before


def test_duplicate_start_and_late_join_rejected(client, full_room, repository):
    host, _ = full_room
    assert (
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ).status_code
        == 200
    )
    before = repository.snapshot()
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "GAME_ALREADY_STARTED",
    )
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/join", json={"display_name": "Late"}
        ),
        409,
        "GAME_ALREADY_STARTED",
    )
    assert repository.snapshot() == before


@pytest.mark.parametrize("phase", list(Phase)[1:])
def test_all_nonwaiting_phases_reject_join_start(client, full_room, repository, phase):
    host, _ = full_room
    repository.rooms[host.room_code] = replace(
        repository.rooms[host.room_code], phase=phase, round=1
    )
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/join", json={"display_name": "Late"}
        ),
        409,
        "GAME_ALREADY_STARTED",
    )
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "GAME_ALREADY_STARTED",
    )


@pytest.mark.parametrize(
    "payload", [{"role": "MAFIA"}, {"phase": "CHALLENGE"}, {"is_host": True}, None, []]
)
def test_start_rejects_extra_fields_and_bad_body(client, full_room, payload):
    host, _ = full_room
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json=payload, headers=auth(host)
        ),
        422,
        "INVALID_REQUEST",
    )


def test_inactive_player_prevents_start(client, full_room, repository):
    host, players = full_room
    player = repository.players[players[1].player_id]
    repository.players[player.player_id] = replace(player, is_active=False)
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "INACTIVE_PLAYERS",
    )
    assert repository.roles == {}
    assert client.get(f"/api/sessions/{host.room_code}", headers=auth(host)).json()[
        "players"
    ]


def test_existing_roles_not_overwritten(client, full_room, repository):
    host, _ = full_room
    repository.roles[host.session_id] = {host.player_id: Role.MAFIA}
    before = repository.snapshot()
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "ROLES_ALREADY_ASSIGNED",
    )
    assert repository.snapshot() == before


def test_validation_error_does_not_echo_input(client):
    marker = "PRIVATE_TOKEN_DO_NOT_ECHO"
    response = client.post(
        "/api/sessions", json={"display_name": "Host", "player_token": marker}
    )
    assert_error(response, 422, "INVALID_REQUEST")
    assert marker not in response.text


def test_malformed_json(client):
    response = client.post(
        "/api/sessions",
        content='{"display_name":',
        headers={"Content-Type": "application/json"},
    )
    assert_error(response, 422, "INVALID_REQUEST")


def test_invalid_body_encoding_is_sanitized(client):
    response = client.post(
        "/api/sessions", content=b"\xff", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 400, "HTTP_ERROR")


def test_planned_gameplay_routes_are_absent(client):
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {
        "/api/sessions",
        "/api/sessions/{code}/join",
        "/api/sessions/{code}",
        "/api/sessions/{code}/start",
    }
