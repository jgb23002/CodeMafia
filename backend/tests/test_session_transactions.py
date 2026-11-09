"""Fake-storage contract tests; these are NOT PostgreSQL integration tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest

import backend.app.sessions.service as session_module
from backend.app.sessions.repository import Role, StateConflict
from backend.app.sessions.service import MAX_REGISTRATION_ATTEMPTS, SessionError
from backend.tests.fakes import FakeTransaction
from backend.tests.test_session_api import assert_error, auth


def test_room_code_collision_retries_in_fresh_transactions(
    client, service, repository, monkeypatch
):
    host = service.create("First")
    candidates = iter([host.room_code, host.room_code, "ZZZZZZ"])
    monkeypatch.setattr(session_module, "new_room_code", lambda: next(candidates))
    before = repository.transactions
    response = client.post("/api/sessions", json={"display_name": "Second"})
    assert response.status_code == 201 and response.json()["room_code"] == "ZZZZZZ"
    assert repository.transactions - before == 3
    assert len(repository.rooms) == len(repository.players) == 2
    assert repository.rooms[host.room_code].host_player_id == host.player_id


def test_room_code_retry_exhaustion_is_bounded(
    client, service, repository, monkeypatch
):
    host = service.create("Host")
    monkeypatch.setattr(session_module, "new_room_code", lambda: host.room_code)
    before, transactions = repository.snapshot(), repository.transactions
    assert_error(
        client.post("/api/sessions", json={"display_name": "Other"}),
        500,
        "ROOM_CREATION_FAILED",
    )
    assert repository.snapshot() == before
    assert repository.transactions - transactions == MAX_REGISTRATION_ATTEMPTS


@pytest.mark.parametrize("operation", ["create", "join"])
def test_token_collision_retries_without_duplicate_identity(
    client, service, repository, monkeypatch, operation
):
    host = service.create("Host")
    original = session_module.secrets.token_urlsafe
    attempts = []

    def token(size):
        assert size == 32
        attempts.append(1)
        return host.player_token if len(attempts) == 1 else original(size)

    monkeypatch.setattr(session_module.secrets, "token_urlsafe", token)
    path = (
        "/api/sessions"
        if operation == "create"
        else f"/api/sessions/{host.room_code}/join"
    )
    response = client.post(path, json={"display_name": "Other"})
    assert (
        response.status_code == 201
        and response.json()["player_token"] != host.player_token
    )
    assert len(attempts) == 2 and len(repository.players) == 2


@pytest.mark.parametrize("operation", ["create", "join"])
def test_identity_collision_exhaustion_rolls_back(
    client, service, repository, monkeypatch, operation
):
    host = service.create("Host")
    monkeypatch.setattr(
        session_module.secrets, "token_urlsafe", lambda size: host.player_token
    )
    before, transactions = repository.snapshot(), repository.transactions
    path = (
        "/api/sessions"
        if operation == "create"
        else f"/api/sessions/{host.room_code}/join"
    )
    assert_error(
        client.post(path, json={"display_name": "Other"}),
        500,
        "IDENTITY_CREATION_FAILED",
    )
    assert repository.snapshot() == before
    assert repository.transactions - transactions == MAX_REGISTRATION_ATTEMPTS


@pytest.mark.parametrize("failure", ["after_room", "after_host", "commit"])
def test_create_failure_is_atomic(client, repository, failure):
    repository.fail_at = failure
    response = client.post("/api/sessions", json={"display_name": "Host"})
    assert_error(response, 500, "PERSISTENCE_ERROR")
    assert repository.rooms == repository.players == repository.roles == {}


@pytest.mark.parametrize("failure", ["after_player", "commit"])
def test_join_failure_is_atomic(client, service, repository, failure):
    host = service.create("Host")
    before = repository.snapshot()
    repository.fail_at = failure
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/join", json={"display_name": "Guest"}
        ),
        500,
        "PERSISTENCE_ERROR",
    )
    assert repository.snapshot() == before


@pytest.mark.parametrize(
    "failure",
    [
        "after_role_1",
        "after_role_2",
        "after_role_3",
        "after_role_4",
        "after_start_update",
        "commit",
    ],
)
def test_partial_start_and_commit_failures_roll_back_everything(
    client, full_room, repository, failure
):
    host, _ = full_room
    before = repository.snapshot()
    repository.fail_at = failure
    response = client.post(
        f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
    )
    assert_error(response, 500, "PERSISTENCE_ERROR")
    assert repository.snapshot() == before
    assert all(
        secret not in response.text
        for secret in ("PRIVATE_TOKEN", "MAFIA", "ANSWER_KEY", "SQL")
    )
    repository.fail_at = None
    assert (
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ).status_code
        == 200
    )


@pytest.mark.parametrize("operation", ["create", "join", "lobby", "start"])
def test_unavailable_repository_has_safe_errors(
    client, full_room, repository, operation
):
    host, _ = full_room
    repository.fail_at = "begin"
    if operation == "create":
        response = client.post("/api/sessions", json={"display_name": "Other"})
    elif operation == "join":
        response = client.post(
            f"/api/sessions/{host.room_code}/join", json={"display_name": "Guest"}
        )
    elif operation == "lobby":
        response = client.get(f"/api/sessions/{host.room_code}", headers=auth(host))
    else:
        response = client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        )
    assert_error(response, 500, "PERSISTENCE_ERROR")
    assert response.json()["error"]["details"] == {}


def test_unexpected_failure_does_not_leak_to_response_or_logs(
    client, service, monkeypatch, caplog
):
    def fail(name):
        raise RuntimeError("PRIVATE_TOKEN ANSWER_KEY MAFIA diagnostic SQL")

    monkeypatch.setattr(service, "create", fail)
    response = client.post("/api/sessions", json={"display_name": "Host"})
    assert_error(response, 500, "INTERNAL_ERROR")
    for secret in ("PRIVATE_TOKEN", "ANSWER_KEY", "MAFIA", "SQL"):
        assert secret not in response.text and secret not in caplog.text


def test_adapter_state_conflict_is_atomic(client, full_room, repository, monkeypatch):
    host, _ = full_room
    before = repository.snapshot()

    def conflict(tx, session_id, assignments):
        tx.repo.roles[session_id] = {host.player_id: Role.MAFIA}
        raise StateConflict("private DB detail")

    monkeypatch.setattr(FakeTransaction, "start_game", conflict)
    assert_error(
        client.post(
            f"/api/sessions/{host.room_code}/start", json={}, headers=auth(host)
        ),
        409,
        "STATE_CONFLICT",
    )
    assert repository.snapshot() == before


def test_concurrent_joins_preserve_capacity_with_fake_transaction_lock(
    service, repository
):
    host = service.create("Host")
    barrier = Barrier(8)

    def join(index):
        barrier.wait(timeout=10)
        try:
            return service.join(host.room_code, str(index))
        except SessionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(join, range(8)))
    successes = [result for result in results if not isinstance(result, SessionError)]
    failures = [result for result in results if isinstance(result, SessionError)]
    assert len(successes) == 3 and len(failures) == 5
    assert sorted(result.player_count for result in successes) == [2, 3, 4]
    assert (
        len({result.player_id for result in successes})
        == len({result.player_token for result in successes})
        == 3
    )
    assert all(error.status == 409 and error.code == "ROOM_FULL" for error in failures)
    assert len(repository.players) == 4


def test_concurrent_starts_commit_once_with_fake_lock(service, full_room, repository):
    host, _ = full_room
    barrier = Barrier(5)

    def start(_):
        barrier.wait(timeout=10)
        try:
            return service.start(host.room_code, auth(host)["Authorization"])
        except SessionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(start, range(5)))
    failures = [result for result in results if isinstance(result, SessionError)]
    assert len(failures) == 4
    assert all(
        error.status == 409 and error.code == "GAME_ALREADY_STARTED"
        for error in failures
    )
    assert len(repository.roles[host.session_id]) == 4


def test_concurrent_creation_unique_code_collision(service, repository, monkeypatch):
    barrier, lock, attempts = Barrier(2), Lock(), []

    def code():
        with lock:
            attempts.append(1)
            first_candidate = len(attempts) <= 2
        if first_candidate:
            barrier.wait(timeout=10)
            return "AAAAAA"
        return "BBBBBB"

    monkeypatch.setattr(session_module, "new_room_code", code)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda index: service.create(str(index)), range(2)))
    assert {result.room_code for result in results} == {"AAAAAA", "BBBBBB"}
    assert len(repository.rooms) == len(repository.players) == 2


def test_concurrent_final_join_and_start_never_partially_start(service, repository):
    host = service.create("Host")
    service.join(host.room_code, "Second")
    service.join(host.room_code, "Third")
    barrier = Barrier(2)

    def join():
        barrier.wait(timeout=10)
        return service.join(host.room_code, "Fourth")

    def start():
        barrier.wait(timeout=10)
        try:
            return service.start(host.room_code, auth(host)["Authorization"])
        except SessionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        joined, started = pool.submit(join), pool.submit(start)
        assert joined.result(timeout=10).player_count == 4
        outcome = started.result(timeout=10)
    if isinstance(outcome, SessionError):
        assert outcome.code == "FOUR_PLAYERS_REQUIRED" and repository.roles == {}
    else:
        assert len(repository.roles[host.session_id]) == 4
    assert len(repository.players) == 4
