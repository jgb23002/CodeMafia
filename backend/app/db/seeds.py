"""Immutable, repeatable challenge definitions. Answer keys stay server-side."""

import json
from pathlib import Path

from psycopg.types.json import Jsonb

from backend.app.database import Database

SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "challenges.json"


def load_challenges(path: Path = SEED_FILE) -> list[dict]:
    document = json.loads(path.read_text())
    if document.get("schema_version") != 1:
        raise ValueError("Unsupported challenge seed format.")
    challenges = document["challenges"]
    expected_pairs = {
        (round_number, kind)
        for round_number in range(1, 6)
        for kind in ("CODING", "ESCAPE")
    }
    if len(challenges) != 10 or len({row["id"] for row in challenges}) != 10:
        raise ValueError("Expected ten uniquely identified challenges.")
    if {(row["round"], row["kind"]) for row in challenges} != expected_pairs:
        raise ValueError("Expected one coding and one escape challenge per round.")
    for row in challenges:
        if set(row) != {"id", "kind", "round", "prompt", "answer_key"}:
            raise ValueError("Unexpected challenge fields.")
        answers = row["answer_key"].get("accepted")
        if not row["prompt"].strip() or not isinstance(answers, list) or not answers:
            raise ValueError("Every challenge needs a prompt and accepted answers.")
        if any(
            not isinstance(answer, str) or not answer or answer != answer.strip()
            for answer in answers
        ):
            raise ValueError("Answers must be nonempty normalized strings.")
    return challenges


def answer_matches(answer_key: dict, submitted: str) -> bool:
    """Exact text after outer whitespace trimming; never execute submitted code."""
    return submitted.strip() in answer_key["accepted"]


def seed_challenges(database: Database) -> int:
    inserted = 0
    with database.connect() as connection:
        for challenge in load_challenges():
            row = connection.execute(
                """INSERT INTO challenges (id, kind, round, prompt, answer_key)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING RETURNING id""",
                (
                    challenge["id"],
                    challenge["kind"],
                    challenge["round"],
                    challenge["prompt"],
                    Jsonb(challenge["answer_key"]),
                ),
            ).fetchone()
            if row:
                inserted += 1
            else:
                existing = connection.execute(
                    "SELECT id, kind, round, prompt, answer_key FROM challenges WHERE id = %s",
                    (challenge["id"],),
                ).fetchone()
                if existing != challenge:
                    raise RuntimeError(
                        "Existing challenges differ from the immutable seed. Add a migration instead."
                    )
    return inserted


def public_challenges(database: Database) -> list[dict]:
    with database.connect() as connection:
        return connection.execute(
            "SELECT id, kind, round, prompt FROM challenges ORDER BY round, kind"
        ).fetchall()
