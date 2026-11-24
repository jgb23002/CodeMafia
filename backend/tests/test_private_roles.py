"""CM-12-JI-1/3: caller-only roles and credential-preserving rejoin boundaries."""

from dataclasses import replace

import pytest

from backend.app.sessions.repository import Phase, Role
from backend.tests.fakes import FakeTransaction


def auth(player):
    return {"Authorization": f"Bearer {player.player_token}"}


def test_waiting_player_has_no_role_even_with_uncommitted_assignment_data(
    client, service, repository
):
    host = service.create("Host")
    repository.roles[host.session_id] = {host.player_id: Role.MAFIA}
    response = client.get(f"/api/sessions/{host.room_code}/state", headers=auth(host))
    assert response.status_code == 200
    assert response.json() == {
        "room_code": host.room_code,
        "phase": "WAITING",
        "round": 0,
        "my_player_id": host.player_id,
        "my_role": None,
    }


def test_each_player_reads_only_their_own_role_without_loading_the_assignment_map(
    client, service, repository, full_room, monkeypatch
):
    host, players = full_room
    service.start(host.room_code, auth(host)["Authorization"])

    def no_roster(*args):
        raise AssertionError("A private-role request must not load every assignment")

    monkeypatch.setattr(FakeTransaction, "get_roles", no_roster)
    found = []
    for player in players:
        response = client.get(
            f"/api/sessions/{host.room_code}/state", headers=auth(player)
        )
        assert response.status_code == 200
        assert set(response.json()) == {
            "room_code",
            "phase",
            "round",
            "my_player_id",
            "my_role",
        }
        assert response.json()["my_player_id"] == player.player_id
        assert (
            response.json()["my_role"]
            == repository.roles[host.session_id][player.player_id]
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Authorization"
        assert response.headers["pragma"] == "no-cache"
        for other in players:
            assert other.player_token not in response.text
            if other.player_id != player.player_id:
                assert other.player_id not in response.text
        found.append(response.json()["my_role"])
    assert set(found) == set(Role) and len(found) == 4


@pytest.mark.parametrize(
    "credential",
    [None, "", "Bearer invalid", "Bearer " + "x" * 43, "Basic " + "x" * 43],
)
def test_private_state_requires_the_players_credential(client, full_room, credential):
    host, _ = full_room
    headers = {} if credential is None else {"Authorization": credential}
    response = client.get(f"/api/sessions/{host.room_code}/state", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert set(response.json()) == {"error"}


def test_another_rooms_token_cannot_read_a_role(client, service, full_room):
    host, _ = full_room
    outsider = service.create("Outsider")
    service.start(host.room_code, auth(host)["Authorization"])
    response = client.get(
        f"/api/sessions/{host.room_code}/state", headers=auth(outsider)
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_ROOM_MEMBER"
    assert "my_role" not in response.text


def test_client_supplied_player_id_does_not_select_another_role(
    client, service, full_room, repository
):
    host, players = full_room
    service.start(host.room_code, auth(host)["Authorization"])
    response = client.get(
        f"/api/sessions/{host.room_code}/state?player_id={players[1].player_id}&role=MAFIA",
        headers={**auth(host), "X-Player-ID": players[1].player_id},
    )
    assert response.status_code == 200
    assert response.json()["my_player_id"] == host.player_id
    assert (
        response.json()["my_role"] == repository.roles[host.session_id][host.player_id]
    )
    assert players[1].player_id not in response.text


def test_refresh_and_rejoin_read_same_identity_without_reassigning(
    client, service, full_room, repository
):
    host, players = full_room
    service.start(host.room_code, auth(host)["Authorization"])
    before = repository.snapshot()
    for player in players:
        first = client.get(
            f"/api/sessions/{host.room_code}/state", headers=auth(player)
        )
        for _ in range(3):
            refreshed = client.get(
                f"/api/sessions/{host.room_code}/state", headers=auth(player)
            )
            assert refreshed.json() == first.json()
        assert (
            client.get(f"/api/sessions/{host.room_code}", headers=auth(player)).json()[
                "player_count"
            ]
            == 4
        )
    assert repository.snapshot() == before


@pytest.mark.parametrize("started", [False, True])
def test_authenticated_duplicate_join_never_creates_another_identity(
    client, service, full_room, repository, started
):
    host, players = full_room
    if started:
        service.start(host.room_code, auth(host)["Authorization"])
    before = repository.snapshot()
    for player in players:
        response = client.post(
            f"/api/sessions/{host.room_code}/join",
            json={"display_name": "Changed name"},
            headers=auth(player),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ALREADY_JOINED"
    assert repository.snapshot() == before


@pytest.mark.parametrize(
    "credential,expected",
    [("Bearer invalid", 401), ("", 401), ("Bearer " + "x" * 43, 401)],
)
def test_invalid_duplicate_join_credentials_do_not_fall_back_to_anonymous_join(
    client, service, repository, credential, expected
):
    host = service.create("Host")
    response = client.post(
        f"/api/sessions/{host.room_code}/join",
        json={"display_name": "Guest"},
        headers={"Authorization": credential},
    )
    assert response.status_code == expected
    assert len(repository.players) == 1


def test_cross_room_duplicate_join_is_forbidden(client, service, repository):
    host = service.create("Host")
    outsider = service.create("Other host")
    response = client.post(
        f"/api/sessions/{host.room_code}/join",
        json={"display_name": "New name"},
        headers=auth(outsider),
    )
    assert response.status_code == 403
    assert len(repository.players) == 2


def test_failed_or_duplicate_start_does_not_reveal_or_shuffle_roles(
    client, full_room, repository
):
    host, players = full_room
    base = f"/api/sessions/{host.room_code}"
    forbidden = client.post(base + "/start", json={}, headers=auth(players[1]))
    assert forbidden.status_code == 403 and "my_role" not in forbidden.text
    assert repository.roles == {}
    started = client.post(base + "/start", json={}, headers=auth(host))
    assert started.status_code == 200
    before = repository.snapshot()
    duplicate = client.post(base + "/start", json={}, headers=auth(host))
    assert duplicate.status_code == 409 and "my_role" not in duplicate.text
    assert repository.snapshot() == before


@pytest.mark.parametrize("failure", ["read_role", "commit"])
def test_private_role_storage_failures_never_leak_data(
    client, service, full_room, repository, caplog, failure
):
    host, _ = full_room
    service.start(host.room_code, auth(host)["Authorization"])
    repository.fail_at = failure
    response = client.get(f"/api/sessions/{host.room_code}/state", headers=auth(host))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "PERSISTENCE_ERROR"
    for secret in [
        host.player_token,
        "PRIVATE_TOKEN",
        "MAFIA",
        "ANSWER_KEY",
        "diagnostic SQL",
    ]:
        assert secret not in response.text + caplog.text


def test_missing_own_assignment_does_not_fall_back_to_another_players_role(
    client, service, full_room, repository
):
    host, _ = full_room
    service.start(host.room_code, auth(host)["Authorization"])
    del repository.roles[host.session_id][host.player_id]
    response = client.get(f"/api/sessions/{host.room_code}/state", headers=auth(host))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ROLE_UNAVAILABLE"
    assert "my_role" not in response.text


def test_game_over_does_not_expand_private_role_visibility(
    client, service, full_room, repository
):
    host, _ = full_room
    service.start(host.room_code, auth(host)["Authorization"])
    repository.rooms[host.room_code] = replace(
        repository.rooms[host.room_code], phase=Phase.GAME_OVER
    )
    state = client.get(
        f"/api/sessions/{host.room_code}/state", headers=auth(host)
    ).json()
    assert state["phase"] == "GAME_OVER" and state["my_player_id"] == host.player_id
    assert set(state) == {"room_code", "phase", "round", "my_player_id", "my_role"}
