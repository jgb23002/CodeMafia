"""Concurrency and failure tests use real connections and independent processes."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest

from backend.app.database import Database
from backend.app.matches import (
    MatchRepository,
    MatchResult,
    StoredMatchResult,
    Winner,
    WinReason,
)
from backend.app.sessions import SessionService
from backend.app.sessions.postgres import PostgresRepository, PostgresTransaction
from backend.app.sessions.repository import (
    Phase,
    Player,
    RepositoryError,
    Role,
    StateConflict,
)
from backend.app.sessions.service import SessionError, token_hash

pytestmark = pytest.mark.postgres


def auth(player):
    return f"Bearer {player.player_token}"


def test_session_state_and_private_roles_survive_a_new_adapter(
    pg_database, pg_service, pg_full_room
):
    host, players = pg_full_room
    started = pg_service.start(host.room_code, auth(host))
    restarted = SessionService(
        PostgresRepository(Database(pg_database.url, pg_database.schema))
    )
    lobby = restarted.lobby(host.room_code, auth(players[1]))
    assert started.phase == lobby.phase == Phase.SABOTAGE
    assert lobby.player_count == 4
    assert (
        "token" not in lobby.model_dump_json() and "role" not in lobby.model_dump_json()
    )
    with PostgresRepository(pg_database).transaction() as transaction:
        assert set(transaction.get_roles(host.session_id).values()) == set(Role)


def test_eight_simultaneous_joins_accept_exactly_three(pg_database, pg_service):
    host = pg_service.create("Host")

    def join(index):
        try:
            return pg_service.join(host.room_code, f"Guest {index}").player_id
        except SessionError as error:
            assert error.code == "ROOM_FULL"
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(join, range(8)))
    assert len([result for result in results if result]) == 3
    assert pg_service.lobby(host.room_code, auth(host)).player_count == 4


def test_concurrent_starts_assign_roles_exactly_once(
    pg_database, pg_service, pg_full_room
):
    host, _ = pg_full_room

    def start(_):
        try:
            pg_service.start(host.room_code, auth(host))
            return True
        except SessionError as error:
            assert error.code == "GAME_ALREADY_STARTED"
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(start, range(4))) == 1
    with PostgresRepository(pg_database).transaction() as transaction:
        assert len(transaction.get_roles(host.session_id)) == 4


def test_capacity_is_enforced_between_independent_python_processes(
    pg_database, pg_service
):
    host = pg_service.create("Host")
    script = """
import json,sys
from backend.app.database import Database
from backend.app.sessions import SessionService
from backend.app.sessions.postgres import PostgresRepository
from backend.app.sessions.service import SessionError
settings = json.loads(sys.stdin.read())
service = SessionService(PostgresRepository(Database(settings['url'], settings['schema'])))
try:
    service.join(settings['code'], settings['name'])
    print('joined')
except SessionError as error:
    print(error.code)
"""

    def join(index):
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(
                {
                    "url": pg_database.url,
                    "schema": pg_database.schema,
                    "code": host.room_code,
                    "name": f"Process {index}",
                }
            ),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout.strip()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(join, range(8)))
    assert results.count("joined") == 3
    assert results.count("ROOM_FULL") == 5


def test_partial_assignment_failure_rolls_back_phase_and_every_role(
    pg_database, pg_service, pg_full_room, monkeypatch
):
    host, _ = pg_full_room
    original = PostgresTransaction._insert_assignment
    written = 0

    def fail_after_two(transaction, session_id, player_id, role):
        nonlocal written
        written += 1
        if written == 3:
            raise RepositoryError()
        original(transaction, session_id, player_id, role)

    monkeypatch.setattr(PostgresTransaction, "_insert_assignment", fail_after_two)
    with pytest.raises(SessionError, match="Unable to persist"):
        pg_service.start(host.room_code, auth(host))
    with PostgresRepository(pg_database).transaction() as transaction:
        assert (
            transaction.get_room(host.room_code, lock="shared").phase == Phase.WAITING
        )
        assert transaction.get_roles(host.session_id) == {}


def test_deferred_constraint_commit_failure_never_reports_success(
    pg_database, pg_service, monkeypatch
):
    monkeypatch.setattr(PostgresTransaction, "_insert_player", lambda *args: None)
    with pytest.raises(SessionError) as failure:
        pg_service.create("Host")
    assert failure.value.code == "PERSISTENCE_ERROR"
    with pg_database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) AS count FROM sessions").fetchone()[
                "count"
            ]
            == 0
        )


def test_room_code_collision_is_retried_after_rollback(
    pg_database, pg_service, monkeypatch
):
    from backend.app.sessions import service as session_module

    first = pg_service.create("First")
    candidates = iter([first.room_code, "ABC234"])
    monkeypatch.setattr(session_module, "new_room_code", lambda: next(candidates))
    second = pg_service.create("Second")
    assert second.room_code == "ABC234"
    assert pg_service.lobby(first.room_code, auth(first)).player_count == 1


def test_membership_write_without_room_lock_is_rejected(pg_database, pg_service):
    host = pg_service.create("Host")
    with (
        pytest.raises(RepositoryError),
        PostgresRepository(pg_database).transaction() as transaction,
    ):
        transaction.add_player(
            Player(str(uuid4()), host.session_id, "Guest", token_hash("a" * 43))
        )
    assert pg_service.lobby(host.room_code, auth(host)).player_count == 1


def test_shared_lobby_lock_blocks_membership_writer(pg_database, pg_service):
    host = pg_service.create("Host")
    attempting = Event()

    def join():
        attempting.set()
        return pg_service.join(host.room_code, "Guest")

    with ThreadPoolExecutor(max_workers=1) as executor:
        with PostgresRepository(pg_database).transaction() as transaction:
            transaction.get_room(host.room_code, lock="shared")
            future = executor.submit(join)
            assert attempting.wait(timeout=2)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.2)
            assert len(transaction.list_players(host.session_id)) == 1
        assert future.result(timeout=5).player_count == 2


def test_join_and_start_race_has_no_partial_game(pg_database, pg_service):
    host = pg_service.create("Host")
    for index in range(2):
        pg_service.join(host.room_code, f"Guest {index}")

    def start():
        try:
            return pg_service.start(host.room_code, auth(host))
        except SessionError as error:
            assert error.code == "FOUR_PLAYERS_REQUIRED"
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        joined = executor.submit(pg_service.join, host.room_code, "Last guest")
        started = executor.submit(start)
        assert joined.result(timeout=5).player_count == 4
        outcome = started.result(timeout=5)
    if outcome is None:
        pg_service.start(host.room_code, auth(host))
    with PostgresRepository(pg_database).transaction() as transaction:
        assert (
            transaction.get_room(host.room_code, lock="shared").phase == Phase.SABOTAGE
        )
        assert len(transaction.get_roles(host.session_id)) == 4


def test_result_write_read_and_new_connection_persistence(
    pg_database, pg_service, pg_full_room
):
    host, _ = pg_full_room
    pg_service.start(host.room_code, auth(host))
    result = MatchResult(host.session_id, Winner.NON_MAFIA, WinReason.ESCAPED, 8, 1)
    repository = MatchRepository(pg_database)
    repository.record_result(result)
    stored = repository.read_result(host.session_id)
    assert isinstance(stored, StoredMatchResult)
    assert stored.session_id == result.session_id
    assert stored.winner is Winner.NON_MAFIA
    assert stored.reason is WinReason.ESCAPED
    assert stored.solved_count == result.solved_count
    assert stored.rounds_played == result.rounds_played
    assert stored.completed_at.tzinfo is not None
    assert stored.completed_at.utcoffset() == timedelta(0)
    with pg_database.connect() as connection:
        persisted_at = connection.execute(
            "SELECT completed_at FROM results WHERE session_id = %s",
            (host.session_id,),
        ).fetchone()["completed_at"]
    assert stored.completed_at == persisted_at
    restarted = MatchRepository(Database(pg_database.url, pg_database.schema))
    assert restarted.read_result(host.session_id) == stored
    assert pg_service.lobby(host.room_code, auth(host)).phase == Phase.GAME_OVER
    with pytest.raises(StateConflict):
        restarted.record_result(result)


def test_invalid_result_rolls_back_and_leaves_game_active(
    pg_database, pg_service, pg_full_room
):
    host, _ = pg_full_room
    pg_service.start(host.room_code, auth(host))
    with pytest.raises(RepositoryError):
        MatchRepository(pg_database).record_result(
            MatchResult(host.session_id, "INVALID", "bad", 8, 1)
        )
    assert MatchRepository(pg_database).read_result(host.session_id) is None
    assert pg_service.lobby(host.room_code, auth(host)).phase == Phase.SABOTAGE
    with pg_database.connect() as connection:
        session = connection.execute(
            "SELECT status, completed_at FROM sessions WHERE id = %s",
            (host.session_id,),
        ).fetchone()
        result_count = connection.execute(
            "SELECT count(*) AS count FROM results WHERE session_id = %s",
            (host.session_id,),
        ).fetchone()["count"]
    assert session == {"status": "active", "completed_at": None}
    assert result_count == 0
