"""Atomic, checksummed migrations serialized with a PostgreSQL advisory lock."""

import hashlib
from pathlib import Path

from backend.app.database import Database

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def migrate(database: Database, *, down: bool = False) -> list[int]:
    with database.connect() as connection:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"codemafia:migrations:{database.schema}",),
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version integer PRIMARY KEY,
                checksum text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )"""
        )
        applied = {
            row["version"]: row["checksum"]
            for row in connection.execute(
                "SELECT version, checksum FROM schema_migrations"
            )
        }
        files = sorted(MIGRATIONS.glob("*.up.sql"))
        available = {int(path.name.split("_")[0]): path for path in files}
        if set(applied) - set(available):
            raise RuntimeError("Database has a migration unknown to this checkout.")
        for version, checksum in applied.items():
            if hashlib.sha256(available[version].read_bytes()).hexdigest() != checksum:
                raise RuntimeError(
                    "An applied migration has changed; restore its original contents."
                )
        changed = []
        if down:
            if applied:
                version = max(applied)
                path = available[version].with_name(
                    available[version].name.replace(".up.sql", ".down.sql")
                )
                connection.execute(path.read_text(), prepare=False)
                connection.execute(
                    "DELETE FROM schema_migrations WHERE version = %s", (version,)
                )
                changed.append(version)
        else:
            for version, path in available.items():
                if version not in applied:
                    connection.execute(path.read_text(), prepare=False)
                    connection.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (version, hashlib.sha256(path.read_bytes()).hexdigest()),
                    )
                    changed.append(version)
    return changed


def current_version(database: Database) -> int:
    with database.connect() as connection:
        if (
            connection.execute(
                "SELECT to_regclass('schema_migrations') AS table_name"
            ).fetchone()["table_name"]
            is None
        ):
            return 0
        return connection.execute(
            "SELECT coalesce(max(version), 0) AS version FROM schema_migrations"
        ).fetchone()["version"]
