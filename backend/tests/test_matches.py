import pytest

from backend.app.matches import MatchOutcome, Winner, WinReason, evaluate_winner


@pytest.mark.parametrize("solved_count", [8, 10])
def test_escape_target_or_more_is_a_non_mafia_win(solved_count):
    assert evaluate_winner(solved_count, True, 3, 2, False) == MatchOutcome(
        Winner.NON_MAFIA, WinReason.ESCAPED
    )


def test_seven_solved_challenges_has_no_winner():
    assert evaluate_winner(7, True, 3, 2, False) is None


def test_mafia_elimination_is_a_non_mafia_win():
    assert evaluate_winner(0, False, 3, 3, False) == MatchOutcome(
        Winner.NON_MAFIA, WinReason.MAFIA_ELIMINATED
    )


@pytest.mark.parametrize("active_non_mafia_count", [1, 0])
def test_at_most_one_active_non_mafia_is_a_mafia_win(active_non_mafia_count):
    assert evaluate_winner(0, True, active_non_mafia_count, 3, False) == MatchOutcome(
        Winner.MAFIA, WinReason.MAFIA_PARITY
    )


def test_final_round_in_progress_does_not_trigger_round_limit():
    assert evaluate_winner(0, True, 3, 5, False) is None


def test_resolved_final_round_is_a_mafia_win():
    assert evaluate_winner(0, True, 3, 5, True) == MatchOutcome(
        Winner.MAFIA, WinReason.ROUND_LIMIT
    )


def test_escape_precedes_mafia_parity():
    assert evaluate_winner(8, True, 1, 3, False) == MatchOutcome(
        Winner.NON_MAFIA, WinReason.ESCAPED
    )


def test_mafia_elimination_precedes_parity():
    assert evaluate_winner(0, False, 1, 3, False) == MatchOutcome(
        Winner.NON_MAFIA, WinReason.MAFIA_ELIMINATED
    )


def test_escape_temporarily_precedes_mafia_elimination_pending_team_approval():
    assert evaluate_winner(8, False, 3, 3, False) == MatchOutcome(
        Winner.NON_MAFIA, WinReason.ESCAPED
    )


def test_earlier_round_without_terminal_conditions_has_no_winner():
    assert evaluate_winner(0, True, 3, 4, False) is None
