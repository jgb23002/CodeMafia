"""Validated transport models and explicit response allowlists."""

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from .repository import Phase, Role


class PlayerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    display_name: str

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 40:
            raise ValueError("Display name must contain 1 to 40 characters.")
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError(
                "Display name must not contain control or format characters."
            )
        return value


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Registration(BaseModel):
    session_id: str
    room_code: str
    player_id: str
    player_token: str
    is_host: bool
    phase: Literal[Phase.WAITING]
    player_count: int


class LobbyPlayer(BaseModel):
    player_id: str
    display_name: str
    is_host: bool
    is_active: bool


class Lobby(BaseModel):
    room_code: str
    phase: Phase
    host_player_id: str
    players: list[LobbyPlayer]
    player_count: int
    capacity: Literal[4]


class StartedGame(BaseModel):
    room_code: str
    phase: Literal[Phase.SABOTAGE]
    round: Literal[1]
    player_count: Literal[4]
    my_role: Role
