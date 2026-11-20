"""Challenge flow through the real application and PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.challenges import ChallengeService
from backend.app.challenges.postgres import PostgresChallengeRepository
from backend.app.db.seeds import seed_challenges
from backend.app.sessions.service import SessionError

pytestmark = pytest.mark.postgres

ANSWERS = {
    "CM01": "12",
    "CM02": "HELLO",
    "CM03": "3",
    "CM04": "42",
    "CM05": "45",
    "CM06": "264",
    "CM07": "16",
    "CM08": "2K7A",
}


@pytest.fixture
def started(pg_client, pg_database):
    seed_challenges(pg_database)
    host = pg_client.post("/api/sessions", json={"display_name": "Host"}).json()
    code = host["room_code"]
    players = [host] + [
        pg_client.post(
            f"/api/sessions/{code}/join", json={"display_name": f"Guest {i}"}
        ).json()
        for i in range(3)
    ]
    auth = {"Authorization": f"Bearer {host['player_token']}"}
    assert (
        pg_client.post(f"/api/sessions/{code}/start", json={}, headers=auth).status_code
        == 200
    )

    def set_round(round_number):
        # The phase engine is a separate feature; tests move the room directly.
        with pg_database.connect() as connection:
            connection.execute(
                "UPDATE sessions SET phase = 'CHALLENGE', round = %s WHERE room_code = %s",
                (round_number, code),
            )

    set_round(1)
    return code, players, set_round


def bearer(player):
    return {"Authorization": f"Bearer {player['player_token']}"}


def answer(client, code, player, challenge_id, text):
    return client.post(
        f"/api/sessions/{code}/answers",
        json={"challenge_id": challenge_id, "answer": text},
        headers=bearer(player),
    )


def test_board_persists_shared_timer_and_hides_keys(pg_client, started):
    code, players, _ = started
    first = pg_client.get(
        f"/api/sessions/{code}/challenges", headers=bearer(players[0])
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert [c["challenge_id"] for c in body["challenges"]] == ["CM01", "CM02"]
    assert body["deadline"] is not None and "accepted" not in first.text
    second = pg_client.get(
        f"/api/sessions/{code}/challenges", headers=bearer(players[1])
    )
    assert second.json()["deadline"] == body["deadline"]


def test_wrong_answer_penalty_attempt_limit_and_unique_solve(
    pg_client, pg_database, started
):
    code, players, _ = started
    first = answer(pg_client, code, players[0], "CM01", "13").json()
    assert first["correct"] is False and first["penalty_seconds"] == 15
    for _ in range(2):
        answer(pg_client, code, players[0], "CM01", "13")
    limited = answer(pg_client, code, players[0], "CM01", "12")
    assert limited.json()["error"]["code"] == "ATTEMPT_LIMIT"
    assert answer(pg_client, code, players[1], "CM01", "12").json()["correct"] is True
    resolved = answer(pg_client, code, players[2], "CM01", "12")
    assert resolved.json()["error"]["code"] == "CHALLENGE_RESOLVED"
    with pg_database.connect() as connection:
        rows = connection.execute(
            "SELECT count(*) AS n FROM challenge_completions"
        ).fetchone()
        assert rows["n"] == 1


def test_simultaneous_correct_answers_count_once(pg_client, pg_database, started):
    code, players, _ = started
    service = ChallengeService(PostgresChallengeRepository(pg_database))

    def submit(player):
        try:
            service.answer(code, f"Bearer {player['player_token']}", "CM02", "HELLO")
            return 200
        except SessionError as error:
            return error.status

    with ThreadPoolExecutor(4) as pool:
        statuses = sorted(pool.map(submit, players))
    assert statuses == [200, 409, 409, 409]
    board = pg_client.get(
        f"/api/sessions/{code}/challenges", headers=bearer(players[0])
    )
    assert board.json()["solved_count"] == 1


def test_eight_solves_record_team_escape(pg_client, pg_database, started):
    code, players, set_round = started
    ids = list(ANSWERS)
    final = None
    for index, challenge_id in enumerate(ids):
        set_round(index // 2 + 1)
        final = answer(
            pg_client, code, players[index % 4], challenge_id, ANSWERS[challenge_id]
        )
        assert final.status_code == 200, final.text
    body = final.json()
    assert body["solved_count"] == 8
    assert body["winner"] == "NON_MAFIA" and body["phase"] == "GAME_OVER"
    with pg_database.connect() as connection:
        result = connection.execute(
            "SELECT winner, solved_count, rounds_played FROM results"
        ).fetchone()
        room = connection.execute("SELECT phase, status FROM sessions").fetchone()
    assert result == {"winner": "NON_MAFIA", "solved_count": 8, "rounds_played": 4}
    assert room == {"phase": "GAME_OVER", "status": "finished"}
