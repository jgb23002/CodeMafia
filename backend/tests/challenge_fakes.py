"""TEST ONLY: in-memory challenge storage layered on the session fake."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

from backend.app.challenges.repository import ChallengeRecord
from backend.app.db.seeds import load_challenges
from backend.app.sessions.repository import Phase, StateConflict
from backend.tests.fakes import FakeRepository, FakeTransaction


class FakeChallengeRepository(FakeRepository):
    def __init__(self):
        super().__init__()
        self.challenges = {
            row["id"]: ChallengeRecord(
                row["id"], row["kind"], row["round"], row["prompt"], row["answer_key"]
            )
            for row in load_challenges()
        }
        self.attempts: list[dict] = []
        self.completions: dict[str, dict[str, str]] = {}
        self.timers: dict[tuple[str, int], object] = {}
        self.results: dict[str, dict] = {}

    def _state(self):
        return (
            self.rooms,
            self.players,
            self.roles,
            self.attempts,
            self.completions,
            self.timers,
            self.results,
        )

    @contextmanager
    def transaction(self):
        with self.lock:
            self.transactions += 1
            before = deepcopy(self._state())
            try:
                self.fail("begin")
                yield FakeChallengeTransaction(self)
                self.fail("commit")
            except BaseException:
                (
                    self.rooms,
                    self.players,
                    self.roles,
                    self.attempts,
                    self.completions,
                    self.timers,
                    self.results,
                ) = before
                raise

    # Test helpers: the round/phase engine is a separate feature.
    def set_phase(self, code: str, phase: Phase, round_number: int | None = None):
        room = self.rooms[code]
        self.rooms[code] = replace(
            room,
            phase=phase,
            round=room.round if round_number is None else round_number,
        )


class FakeChallengeTransaction(FakeTransaction):
    def round_challenges(self, round_number):
        return sorted(
            (c for c in self.repo.challenges.values() if c.round == round_number),
            key=lambda c: (c.kind, c.challenge_id),
        )

    def get_challenge(self, challenge_id):
        return self.repo.challenges.get(challenge_id)

    def completed_challenges(self, session_id):
        return set(self.repo.completions.get(session_id, {}))

    def attempt_counts(self, session_id, player_id):
        counts: dict[str, int] = {}
        for row in self.repo.attempts:
            if row["session_id"] == session_id and row["player_id"] == player_id:
                counts[row["challenge_id"]] = counts.get(row["challenge_id"], 0) + 1
        return counts

    def get_deadline(self, session_id, round_number):
        return self.repo.timers.get((session_id, round_number))

    def set_deadline(self, session_id, round_number, deadline):
        self._require_lock(session_id, exclusive=True)
        self.repo.timers[(session_id, round_number)] = deadline

    def record_attempt(
        self, attempt_id, session_id, player_id, challenge_id, answer, is_correct
    ):
        self._require_lock(session_id, exclusive=True)
        self.repo.attempts.append(
            {
                "id": attempt_id,
                "session_id": session_id,
                "player_id": player_id,
                "challenge_id": challenge_id,
                "answer": answer,
                "is_correct": is_correct,
            }
        )
        self.repo.fail("after_attempt")

    def complete_challenge(self, session_id, challenge_id, player_id):
        self._require_lock(session_id, exclusive=True)
        solved = self.repo.completions.setdefault(session_id, {})
        if challenge_id in solved:
            raise StateConflict("duplicate completion")
        solved[challenge_id] = player_id

    def get_winner(self, session_id):
        result = self.repo.results.get(session_id)
        return result["winner"] if result else None

    def finish_escape(self, session_id, solved_count, rounds_played):
        self._require_lock(session_id, exclusive=True)
        room = next(r for r in self.repo.rooms.values() if r.session_id == session_id)
        if (
            room.phase in (Phase.WAITING, Phase.GAME_OVER)
            or room.round != rounds_played
        ):
            raise StateConflict("conditional finish failed")
        self.repo.rooms[room.room_code] = replace(room, phase=Phase.GAME_OVER)
        self.repo.fail("after_finish_update")
        self.repo.results[session_id] = {
            "winner": "NON_MAFIA",
            "reason": "ESCAPED",
            "solved_count": solved_count,
            "rounds_played": rounds_played,
        }
