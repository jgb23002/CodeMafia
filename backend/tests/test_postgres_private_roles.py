from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.database import Database
from backend.app.sessions import SessionService
from backend.app.sessions.postgres import PostgresRepository
from backend.app.sessions.repository import Role
from backend.app.sessions.service import SessionError

pytestmark = pytest.mark.postgres


def test_four_private_roles_persist_and_rejoin_with_original_tokens(
    pg_database, pg_service, pg_full_room, pg_client
):
    host, players = pg_full_room
    pg_service.start(host.room_code, f"Bearer {host.player_token}")
    restarted = SessionService(
        PostgresRepository(Database(pg_database.url, pg_database.schema))
    )
    roles = []
    for player in players:
        headers = {"Authorization": f"Bearer {player.player_token}"}
        response = pg_client.get(
            f"/api/sessions/{host.room_code}/state", headers=headers
        )
        assert response.status_code == 200
        state = response.json()
        assert state["my_player_id"] == player.player_id
        assert set(state) == {"room_code", "phase", "round", "my_player_id", "my_role"}
        assert (
            restarted.private_state(
                host.room_code, headers["Authorization"]
            ).model_dump(mode="json")
            == state
        )
        for other in players:
            if other.player_id != player.player_id:
                assert other.player_id not in response.text
            assert other.player_token not in response.text
        roles.append(state["my_role"])
    assert len(roles) == 4 and set(roles) == set(Role)
    assert (
        pg_service.lobby(host.room_code, f"Bearer {host.player_token}").player_count
        == 4
    )


def test_concurrent_reads_and_start_never_observe_partial_assignment(
    pg_service, pg_full_room
):
    host, players = pg_full_room
    with ThreadPoolExecutor(max_workers=5) as executor:
        reads = [
            executor.submit(
                pg_service.private_state,
                host.room_code,
                f"Bearer {player.player_token}",
            )
            for player in players
        ]
        started = executor.submit(
            pg_service.start, host.room_code, f"Bearer {host.player_token}"
        )
        states = [future.result(timeout=10) for future in reads]
        started.result(timeout=10)
    for state in states:
        if state.phase == "WAITING":
            assert state.round == 0 and state.my_role is None
        else:
            assert (
                state.phase == "SABOTAGE" and state.round == 1 and state.my_role in Role
            )


def test_concurrent_authenticated_duplicate_joins_preserve_capacity_and_roles(
    pg_service, pg_full_room
):
    host, players = pg_full_room
    pg_service.start(host.room_code, f"Bearer {host.player_token}")
    before = [
        pg_service.private_state(host.room_code, f"Bearer {player.player_token}")
        for player in players
    ]

    def join(_):
        with pytest.raises(SessionError) as failure:
            pg_service.join(
                host.room_code, "Duplicate", f"Bearer {players[1].player_token}"
            )
        assert failure.value.code == "ALREADY_JOINED"

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(join, range(8)))
    assert [
        pg_service.private_state(host.room_code, f"Bearer {player.player_token}")
        for player in players
    ] == before
    assert (
        pg_service.lobby(host.room_code, f"Bearer {host.player_token}").player_count
        == 4
    )
