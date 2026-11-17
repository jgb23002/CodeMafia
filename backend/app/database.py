"""Short-lived PostgreSQL connections; transactions are never shared by workers."""

import re
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class Database:
    url: str = field(repr=False)
    schema: str = "public"

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", self.schema):
            raise ValueError("Invalid database schema name.")

    def connect(self):
        connection = psycopg.connect(
            self.url,
            row_factory=dict_row,
            connect_timeout=5,
            application_name="CodeMafia",
            options=f"-csearch_path={self.schema}",
        )
        connection.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
        return connection

    def check(self) -> None:
        with self.connect() as connection:
            row = connection.execute("SELECT 1 AS healthy").fetchone()
            if row != {"healthy": 1}:
                raise RuntimeError("Database health check failed.")
