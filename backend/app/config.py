"""Environment configuration. Never include the database URL in diagnostics."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    max_body_bytes: int = 16384

    def __post_init__(self):
        if not self.database_url:
            raise ValueError("CODEMAFIA_DATABASE_URL is required.")
        if not 1024 <= self.max_body_bytes <= 1048576:
            raise ValueError(
                "CODEMAFIA_MAX_BODY_BYTES must be between 1024 and 1048576."
            )
        if "*" in self.cors_origins:
            raise ValueError("Configure explicit frontend origins instead of '*'.")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        return cls(
            database_url=os.environ.get("CODEMAFIA_DATABASE_URL", ""),
            cors_origins=tuple(
                origin.strip()
                for origin in os.environ.get(
                    "CODEMAFIA_CORS_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173",
                ).split(",")
                if origin.strip()
            ),
            max_body_bytes=int(os.environ.get("CODEMAFIA_MAX_BODY_BYTES", "16384")),
        )
