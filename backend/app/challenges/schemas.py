"""Validated transport models and explicit response allowlists for challenges."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.sessions.repository import Phase

ChallengeType = Literal["CODING", "ESCAPE"]
ChallengeStatus = Literal["OPEN", "SOLVED", "CLOSED"]
Winner = Literal["NON_MAFIA", "MAFIA"]


class AnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    challenge_id: str = Field(min_length=1, max_length=20)
    # Length is checked after trimming in the service (INVALID_ANSWER).
    answer: str = Field(max_length=4000)


class PublicChallenge(BaseModel):
    challenge_id: str
    type: ChallengeType
    prompt: str
    status: ChallengeStatus
    attempts_left: int


class ChallengeBoard(BaseModel):
    room_code: str
    phase: Phase
    round: int
    solved_count: int
    escape_target: int
    total_challenges: int
    deadline: str | None
    seconds_remaining: int | None
    challenges: list[PublicChallenge]
    winner: Winner | None


class AnswerResult(BaseModel):
    challenge_id: str
    correct: bool
    solved_count: int
    escape_target: int
    attempts_left: int
    penalty_seconds: int
    deadline: str | None
    seconds_remaining: int | None
    phase: Phase
    winner: Winner | None
