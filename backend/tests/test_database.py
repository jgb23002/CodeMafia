import json
from uuid import uuid4

import psycopg
import pytest

from backend.app.db.migrations import current_version, migrate
from backend.app.db.seeds import (
    answer_matches,
    load_challenges,
    public_challenges,
    seed_challenges,
)


def test_ten_deterministic_challenges_have_known_answers():
    challenges = load_challenges()
    expected = ["12", "HELLO", "3", "42", "45", "264", "16", "2K7A", "1,2,4", "BLUE"]
    assert [row["answer_key"]["accepted"] for row in challenges] == [
        [answer] for answer in expected
    ]
    for row, answer in zip(challenges, expected, strict=True):
        assert answer_matches(row["answer_key"], f" {answer}\n")
        assert not answer_matches(row["answer_key"], "incorrect")


@pytest.mark.postgres
def test_migrations_upgrade_idempotently_and_rollback_cleanly(pg_database):
    assert current_version(pg_database) == 1
    assert migrate(pg_database) == []
    seed_challenges(pg_database)
    assert migrate(pg_database, down=True) == [1]
    assert current_version(pg_database) == 0
    with pg_database.connect() as connection:
        assert (
            connection.execute("SELECT to_regclass('sessions') AS name").fetchone()[
                "name"
            ]
            is None
        )
    assert migrate(pg_database) == [1]
    assert seed_challenges(pg_database) == 10


@pytest.mark.postgres
def test_seeds_are_repeatable_and_public_projection_has_no_answer_keys(pg_database):
    assert seed_challenges(pg_database) == 10
    assert seed_challenges(pg_database) == 0
    rows = public_challenges(pg_database)
    assert len(rows) == 10
    assert all(set(row) == {"id", "kind", "round", "prompt"} for row in rows)
    assert len([row for row in rows if row["kind"] == "CODING"]) == 5
    with pg_database.connect() as connection:
        rows = connection.execute(
            "SELECT answer_key FROM challenges ORDER BY id"
        ).fetchall()
        assert rows[0]["answer_key"] == {"accepted": ["12"]}


@pytest.mark.postgres
def test_seeding_rejects_silent_changes_to_existing_challenges(pg_database):
    seed_challenges(pg_database)
    with pg_database.connect() as connection:
        connection.execute("UPDATE challenges SET prompt = 'Changed' WHERE id = 'CM01'")
    with pytest.raises(RuntimeError, match="immutable seed"):
        seed_challenges(pg_database)


@pytest.mark.postgres
@pytest.mark.parametrize(
    "statement,parameters,error",
    [
        ("UPDATE sessions SET phase = 'NEXT_ROUND'", (), psycopg.errors.CheckViolation),
        ("UPDATE sessions SET round = 6", (), psycopg.errors.CheckViolation),
        (
            "UPDATE players SET token_hash = 'plaintext'",
            (),
            psycopg.errors.CheckViolation,
        ),
        ("UPDATE players SET display_name = ''", (), psycopg.errors.CheckViolation),
    ],
)
def test_schema_rejects_invalid_values(
    pg_database, pg_service, statement, parameters, error
):
    pg_service.create("Host")
    with pytest.raises(error), pg_database.connect() as connection:
        connection.execute(statement, parameters)


@pytest.mark.postgres
def test_schema_rejects_duplicate_credentials(pg_database, pg_service):
    first = pg_service.create("First")
    second = pg_service.create("Second")
    with (
        pytest.raises(psycopg.errors.UniqueViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            "UPDATE players SET token_hash = (SELECT token_hash FROM players WHERE id = %s) WHERE id = %s",
            (first.player_id, second.player_id),
        )


@pytest.mark.postgres
def test_host_must_belong_to_same_session_at_commit(pg_database, pg_service):
    first = pg_service.create("First")
    second = pg_service.create("Second")
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            "UPDATE sessions SET host_player_id = %s WHERE id = %s",
            (second.player_id, first.session_id),
        )


@pytest.mark.postgres
def test_role_assignment_cannot_reference_another_room(pg_database, pg_service):
    first = pg_service.create("First")
    second = pg_service.create("Second")
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            "INSERT INTO role_assignments (session_id, player_id, role) VALUES (%s, %s, 'MAFIA')",
            (first.session_id, second.player_id),
        )


@pytest.mark.postgres
def test_votes_have_unique_voters_and_same_room_targets(
    pg_database, pg_service, pg_full_room
):
    host, players = pg_full_room
    other = pg_service.create("Other room")
    statement = "INSERT INTO votes (session_id, round, voter_id, target_id) VALUES (%s, 1, %s, %s)"
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            statement, (host.session_id, host.player_id, other.player_id)
        )
    with pg_database.connect() as connection:
        connection.execute(
            statement, (host.session_id, host.player_id, players[1].player_id)
        )
    with (
        pytest.raises(psycopg.errors.UniqueViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            statement, (host.session_id, host.player_id, players[2].player_id)
        )


@pytest.mark.postgres
def test_attempts_persist_and_unique_completion_cannot_double_count(
    pg_database, pg_full_room
):
    host, _ = pg_full_room
    seed_challenges(pg_database)
    with pg_database.connect() as connection:
        connection.execute(
            """INSERT INTO attempts (id, session_id, player_id, challenge_id, submitted_answer, is_correct)
               VALUES (%s, %s, %s, 'CM01', '12', true)""",
            (str(uuid4()), host.session_id, host.player_id),
        )
        connection.execute(
            "INSERT INTO challenge_completions (session_id, challenge_id, completed_by) VALUES (%s, 'CM01', %s)",
            (host.session_id, host.player_id),
        )
    with pg_database.connect() as connection:
        assert connection.execute(
            "SELECT submitted_answer, is_correct FROM attempts"
        ).fetchone() == {"submitted_answer": "12", "is_correct": True}
    with (
        pytest.raises(psycopg.errors.UniqueViolation),
        pg_database.connect() as connection,
    ):
        connection.execute(
            "INSERT INTO challenge_completions (session_id, challenge_id, completed_by) VALUES (%s, 'CM01', %s)",
            (host.session_id, host.player_id),
        )


def test_seed_validator_rejects_missing_pair(tmp_path):
    from backend.app.db.seeds import SEED_FILE

    data = json.loads(SEED_FILE.read_text())
    data["challenges"][0]["kind"] = "ESCAPE"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="one coding and one escape"):
        load_challenges(path)
