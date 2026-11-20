"""Challenge engine rules (GA-1) and edge cases (GA-3) against the in-memory fake."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.challenges.service import (
    CHALLENGE_SECONDS,
    ESCAPE_TARGET,
    MAX_ATTEMPTS,
    ChallengeService,
)
from backend.app.sessions.repository import Phase
from backend.app.sessions.service import SessionError, SessionService
from backend.tests.challenge_fakes import FakeChallengeRepository

ANSWERS = {
    "CM01": "12",
    "CM02": "HELLO",
    "CM03": "3",
    "CM04": "42",
    "CM05": "45",
    "CM06": "264",
    "CM07": "16",
    "CM08": "2K7A",
    "CM09": "1,2,4",
    "CM10": "BLUE",
}
ROUND_PAIRS = {
    1: ("CM01", "CM02"),
    2: ("CM03", "CM04"),
    3: ("CM05", "CM06"),
    4: ("CM07", "CM08"),
    5: ("CM09", "CM10"),
}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def bearer(registration):
    return "Bearer " + registration.player_token


@pytest.fixture
def challenge_repository():
    return FakeChallengeRepository()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def challenges(challenge_repository, clock):
    return ChallengeService(challenge_repository, clock=clock)


@pytest.fixture
def game(challenge_repository):
    """A started four-player game moved into round 1's CHALLENGE phase."""
    sessions = SessionService(challenge_repository)
    host = sessions.create("Jiya")
    players = [host] + [
        sessions.join(host.room_code, name)
        for name in ("Priyanshi", "Gabriella", "Michael")
    ]
    sessions.start(host.room_code, bearer(host))
    challenge_repository.set_phase(host.room_code, Phase.CHALLENGE, 1)
    return host.room_code, players


def expect_error(status, code, call, *args):
    with pytest.raises(SessionError) as error:
        call(*args)
    assert (error.value.status, error.value.code) == (status, code)


# ---- serving the round's pair --------------------------------------------


def test_board_serves_round_pair_without_answer_keys(challenges, game):
    code, players = game
    board = challenges.board(code, bearer(players[0]))
    assert board["round"] == 1 and board["phase"] == "CHALLENGE"
    assert [c["challenge_id"] for c in board["challenges"]] == ["CM01", "CM02"]
    assert [c["type"] for c in board["challenges"]] == ["CODING", "ESCAPE"]
    assert all(c["status"] == "OPEN" for c in board["challenges"])
    assert all(c["attempts_left"] == MAX_ATTEMPTS for c in board["challenges"])
    assert board["solved_count"] == 0 and board["escape_target"] == ESCAPE_TARGET
    assert board["seconds_remaining"] == CHALLENGE_SECONDS
    text = repr(board)
    assert "answer_key" not in text and "accepted" not in text
    assert "HELLO" not in text.replace("KHOOR", "")


def test_timer_starts_once_and_is_shared(challenges, game, clock):
    code, players = game
    first = challenges.board(code, bearer(players[0]))
    clock.advance(30)
    second = challenges.board(code, bearer(players[1]))
    assert first["deadline"] == second["deadline"]
    assert second["seconds_remaining"] == CHALLENGE_SECONDS - 30


def test_board_requires_started_game_and_membership(
    challenges, challenge_repository, game
):
    code, players = game
    sessions = SessionService(challenge_repository)
    other = sessions.create("Outsider")
    expect_error(
        409, "GAME_NOT_STARTED", challenges.board, other.room_code, bearer(other)
    )
    expect_error(403, "NOT_ROOM_MEMBER", challenges.board, code, bearer(other))
    expect_error(401, "UNAUTHORIZED", challenges.board, code, None)
    expect_error(404, "ROOM_NOT_FOUND", challenges.board, "ZZZZZZ", bearer(players[0]))


def test_board_outside_challenge_phase_is_closed(
    challenges, challenge_repository, game
):
    code, players = game
    challenge_repository.set_phase(code, Phase.SABOTAGE)
    board = challenges.board(code, bearer(players[0]))
    assert board["deadline"] is None and board["seconds_remaining"] is None
    assert all(c["status"] == "CLOSED" for c in board["challenges"])


# ---- answering -----------------------------------------------------------


def test_correct_answer_counts_and_is_trimmed(challenges, game):
    code, players = game
    result = challenges.answer(code, bearer(players[2]), "CM01", "  12\n")
    assert result["correct"] is True and result["solved_count"] == 1
    assert result["penalty_seconds"] == 0 and result["attempts_left"] == 2
    assert "12" not in {str(v) for k, v in result.items() if k != "solved_count"}
    board = challenges.board(code, bearer(players[0]))
    assert board["challenges"][0]["status"] == "SOLVED"


def test_answers_are_case_sensitive_per_api_contract(challenges, game):
    code, players = game
    assert (
        challenges.answer(code, bearer(players[0]), "CM02", "hello")["correct"] is False
    )
    assert (
        challenges.answer(code, bearer(players[0]), "CM02", "HELLO")["correct"] is True
    )


def test_wrong_answer_costs_fifteen_seconds_of_shared_time(challenges, game):
    code, players = game
    start = challenges.board(code, bearer(players[0]))["seconds_remaining"]
    result = challenges.answer(code, bearer(players[1]), "CM01", "13")
    assert result["correct"] is False and result["penalty_seconds"] == 15
    assert result["seconds_remaining"] == start - 15
    assert challenges.board(code, bearer(players[3]))["seconds_remaining"] == start - 15


def test_penalty_never_moves_deadline_into_the_past(challenges, game, clock):
    code, players = game
    challenges.board(code, bearer(players[0]))
    clock.advance(CHALLENGE_SECONDS - 5)
    result = challenges.answer(code, bearer(players[0]), "CM01", "wrong")
    assert result["seconds_remaining"] == 0
    expect_error(
        409, "TIME_EXPIRED", challenges.answer, code, bearer(players[1]), "CM01", "12"
    )


def test_answers_after_timeout_are_rejected(challenges, game, clock):
    code, players = game
    challenges.board(code, bearer(players[0]))
    clock.advance(CHALLENGE_SECONDS)
    expect_error(
        409, "TIME_EXPIRED", challenges.answer, code, bearer(players[0]), "CM01", "12"
    )
    board = challenges.board(code, bearer(players[0]))
    assert all(c["status"] == "CLOSED" for c in board["challenges"])


def test_three_attempts_per_player_per_challenge(challenges, game):
    code, players = game
    for left in (2, 1, 0):
        result = challenges.answer(code, bearer(players[0]), "CM01", "nope")
        assert result["attempts_left"] == left
    expect_error(
        409, "ATTEMPT_LIMIT", challenges.answer, code, bearer(players[0]), "CM01", "12"
    )
    # Another player still has their own attempts.
    assert challenges.answer(code, bearer(players[1]), "CM01", "12")["correct"]


def test_solved_challenge_counts_once(challenges, challenge_repository, game):
    code, players = game
    challenges.answer(code, bearer(players[0]), "CM01", "12")
    expect_error(
        409,
        "CHALLENGE_RESOLVED",
        challenges.answer,
        code,
        bearer(players[1]),
        "CM01",
        "12",
    )
    session_id = challenge_repository.rooms[code].session_id
    assert challenge_repository.completions[session_id] == {
        "CM01": players[0].player_id
    }


def test_rejects_wrong_phase_other_rounds_unknown_ids_and_bad_input(
    challenges, challenge_repository, game
):
    code, players = game
    token = bearer(players[0])
    expect_error(
        404, "CHALLENGE_NOT_FOUND", challenges.answer, code, token, "CM03", "3"
    )
    expect_error(404, "CHALLENGE_NOT_FOUND", challenges.answer, code, token, "XX", "3")
    expect_error(422, "INVALID_ANSWER", challenges.answer, code, token, "CM01", "   ")
    expect_error(
        422, "INVALID_ANSWER", challenges.answer, code, token, "CM01", "9" * 2001
    )
    challenge_repository.set_phase(code, Phase.VOTING)
    expect_error(409, "WRONG_PHASE", challenges.answer, code, token, "CM01", "12")


def test_eliminated_players_cannot_answer(challenges, challenge_repository, game):
    code, players = game
    player = challenge_repository.players[players[3].player_id]
    challenge_repository.players[player.player_id] = replace(player, is_active=False)
    expect_error(
        403,
        "PLAYER_ELIMINATED",
        challenges.answer,
        code,
        bearer(players[3]),
        "CM01",
        "12",
    )


def test_mafia_may_answer_to_keep_cover(challenges, challenge_repository, game):
    code, players = game
    session_id = challenge_repository.rooms[code].session_id
    mafia_id = next(
        pid
        for pid, role in challenge_repository.roles[session_id].items()
        if role.value == "MAFIA"
    )
    mafia = next(p for p in players if p.player_id == mafia_id)
    assert challenges.answer(code, bearer(mafia), "CM01", "12")["correct"] is True


def test_failed_write_rolls_back_attempt(challenges, challenge_repository, game):
    code, players = game
    challenge_repository.fail_at = "commit"
    expect_error(
        500,
        "PERSISTENCE_ERROR",
        challenges.answer,
        code,
        bearer(players[0]),
        "CM01",
        "12",
    )
    challenge_repository.fail_at = None
    assert (
        challenge_repository.attempts == [] and challenge_repository.completions == {}
    )


# ---- the 8-of-10 escape ----------------------------------------------------


def solve_round(challenges, repository, code, token, round_number, ids=None):
    repository.set_phase(code, Phase.CHALLENGE, round_number)
    results = []
    for challenge_id in ids or ROUND_PAIRS[round_number]:
        results.append(
            challenges.answer(code, token, challenge_id, ANSWERS[challenge_id])
        )
    return results


def test_seven_solves_do_not_end_the_game(challenges, challenge_repository, game):
    code, players = game
    token = bearer(players[0])
    for round_number in (1, 2, 3):
        solve_round(challenges, challenge_repository, code, token, round_number)
    last = solve_round(challenges, challenge_repository, code, token, 4, ["CM07"])[-1]
    assert last["solved_count"] == 7 and last["winner"] is None
    assert last["phase"] == "CHALLENGE"
    assert challenge_repository.rooms[code].phase == Phase.CHALLENGE


def test_eighth_solve_ends_game_with_team_escape(
    challenges, challenge_repository, game
):
    code, players = game
    token = bearer(players[1])
    for round_number in (1, 2, 3):
        solve_round(challenges, challenge_repository, code, token, round_number)
    final = solve_round(challenges, challenge_repository, code, token, 4)[-1]
    assert final["solved_count"] == ESCAPE_TARGET
    assert final["winner"] == "NON_MAFIA" and final["phase"] == "GAME_OVER"
    session_id = challenge_repository.rooms[code].session_id
    assert challenge_repository.rooms[code].phase == Phase.GAME_OVER
    assert challenge_repository.results[session_id]["solved_count"] == 8
    assert challenge_repository.results[session_id]["rounds_played"] == 4
    board = challenges.board(code, token)
    assert board["winner"] == "NON_MAFIA" and board["phase"] == "GAME_OVER"
    expect_error(409, "WRONG_PHASE", challenges.answer, code, token, "CM07", "16")
