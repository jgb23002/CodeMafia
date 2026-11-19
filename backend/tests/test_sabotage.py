import pytest

from backend.app.sabotage import (
    SabotageAction,
    SabotageError,
    SabotageValidation,
    validate_sabotage,
)
from backend.app.sessions.repository import Phase, Role


def validate(
    action=SabotageAction.HIDE_CLUE,
    role=Role.MAFIA,
    active=True,
    phase=Phase.SABOTAGE,
    used=0,
    used_this_round=False,
):
    return validate_sabotage(action, role, active, phase, used, used_this_round)


@pytest.mark.parametrize("action", list(SabotageAction))
def test_active_mafia_can_use_each_supported_sabotage(action):
    assert validate(action=action) == SabotageValidation(
        action=action, sabotages_used=1, remaining_sabotages=2
    )


@pytest.mark.parametrize("role", [Role.DETECTIVE, Role.HACKER, Role.CIVILIAN])
def test_non_mafia_roles_cannot_sabotage(role):
    with pytest.raises(SabotageError) as failure:
        validate(role=role)
    assert (failure.value.status, failure.value.code) == (403, "MAFIA_ONLY")


def test_inactive_mafia_cannot_sabotage():
    with pytest.raises(SabotageError) as failure:
        validate(active=False)
    assert (failure.value.status, failure.value.code) == (403, "PLAYER_ELIMINATED")


@pytest.mark.parametrize("phase", [phase for phase in Phase if phase != Phase.SABOTAGE])
def test_sabotage_is_rejected_outside_sabotage_phase(phase):
    with pytest.raises(SabotageError) as failure:
        validate(phase=phase)
    assert (failure.value.status, failure.value.code) == (409, "WRONG_PHASE")


def test_first_sabotage_is_accepted():
    result = validate()
    assert result.sabotages_used == 1
    assert result.remaining_sabotages == 2


def test_second_sabotage_in_same_round_is_rejected():
    with pytest.raises(SabotageError) as failure:
        validate(used=1, used_this_round=True)
    assert (failure.value.status, failure.value.code) == (409, "SABOTAGE_LIMIT")


def test_third_sabotage_across_separate_rounds_is_accepted():
    assert validate(used=2, used_this_round=False) == SabotageValidation(
        action=SabotageAction.HIDE_CLUE,
        sabotages_used=3,
        remaining_sabotages=0,
    )


def test_fourth_sabotage_is_rejected():
    with pytest.raises(SabotageError) as failure:
        validate(used=3, used_this_round=False)
    assert (failure.value.status, failure.value.code) == (409, "SABOTAGE_LIMIT")


@pytest.mark.parametrize("action", ["", "DELETE_CLUE", "hide_clue", None, 1])
def test_invalid_sabotage_action_is_rejected(action):
    with pytest.raises(SabotageError) as failure:
        validate(action=action)
    assert (failure.value.status, failure.value.code) == (422, "INVALID_SABOTAGE")


@pytest.mark.parametrize(
    "used,used_this_round",
    [(-1, False), (4, False), (True, False), (1.5, False), (0, True), (1, "yes")],
)
def test_invalid_or_inconsistent_usage_state_is_rejected(used, used_this_round):
    with pytest.raises(SabotageError) as failure:
        validate(used=used, used_this_round=used_this_round)
    assert (failure.value.status, failure.value.code) == (
        422,
        "INVALID_SABOTAGE_STATE",
    )
