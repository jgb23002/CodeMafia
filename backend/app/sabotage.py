"""Pure candidate sabotage rules; persistence, deadlines, and effects live elsewhere."""

from dataclasses import dataclass
from enum import Enum

from backend.app.sessions.repository import Phase, Role

MAX_SABOTAGES = 3


class SabotageAction(str, Enum):
    HIDE_CLUE = "HIDE_CLUE"
    REDUCE_TIME = "REDUCE_TIME"


class SabotageError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class SabotageValidation:
    action: SabotageAction
    sabotages_used: int
    remaining_sabotages: int


def validate_sabotage(
    action: SabotageAction | str,
    player_role: Role,
    player_is_active: bool,
    current_phase: Phase,
    sabotages_used: int,
    used_this_round: bool,
) -> SabotageValidation:
    """Validate supplied authoritative state without mutating or applying effects.

    The candidate 15-second deadline and action effects require the future persisted
    phase/deadline system and are intentionally not evaluated here.
    """
    if (
        isinstance(sabotages_used, bool)
        or not isinstance(sabotages_used, int)
        or not 0 <= sabotages_used <= MAX_SABOTAGES
        or not isinstance(used_this_round, bool)
        or (used_this_round and sabotages_used == 0)
    ):
        raise SabotageError(
            422,
            "INVALID_SABOTAGE_STATE",
            "Sabotage usage state is invalid.",
        )
    try:
        normalized_action = SabotageAction(action)
    except (TypeError, ValueError):
        raise SabotageError(
            422, "INVALID_SABOTAGE", "Unsupported sabotage action."
        ) from None
    if player_role != Role.MAFIA:
        raise SabotageError(403, "MAFIA_ONLY", "Only the Mafia player may sabotage.")
    if not player_is_active:
        raise SabotageError(
            403, "PLAYER_ELIMINATED", "Eliminated players cannot sabotage."
        )
    if current_phase != Phase.SABOTAGE:
        raise SabotageError(
            409, "WRONG_PHASE", "Sabotage is not allowed in the current phase."
        )
    if used_this_round or sabotages_used >= MAX_SABOTAGES:
        raise SabotageError(
            409, "SABOTAGE_LIMIT", "The sabotage limit has been reached."
        )
    updated_count = sabotages_used + 1
    return SabotageValidation(
        action=normalized_action,
        sabotages_used=updated_count,
        remaining_sabotages=MAX_SABOTAGES - updated_count,
    )
