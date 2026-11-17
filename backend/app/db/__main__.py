"""Run from the repository root: python -m backend.app.db migrate up."""

import argparse
import json

import psycopg

from backend.app.config import Settings
from backend.app.database import Database
from backend.app.db.migrations import current_version, migrate
from backend.app.db.seeds import seed_challenges


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeMafia database management")
    commands = parser.add_subparsers(dest="command", required=True)
    migrations = commands.add_parser("migrate")
    migrations.add_argument("direction", choices=["up", "down", "status"])
    migrations.add_argument("--allow-data-loss", action="store_true")
    commands.add_parser("seed")
    commands.add_parser("check")
    args = parser.parse_args()
    if (
        args.command == "migrate"
        and args.direction == "down"
        and not args.allow_data_loss
    ):
        parser.error(
            "down drops application data; pass --allow-data-loss only for a disposable database"
        )
    try:
        database = Database(Settings.from_env().database_url)
        if args.command == "seed":
            print(json.dumps({"inserted": seed_challenges(database)}))
        elif args.command == "check":
            database.check()
            print(
                json.dumps(
                    {"database": "ok", "schema_version": current_version(database)}
                )
            )
        else:
            changed = []
            if args.direction != "status":
                changed = migrate(database, down=args.direction == "down")
            print(
                json.dumps(
                    {"changed": changed, "schema_version": current_version(database)}
                )
            )
    except (psycopg.Error, ValueError, RuntimeError):
        # Connection errors can contain credentials. Deliberately omit their text.
        parser.exit(
            1,
            "Database command failed. Verify configuration, availability, schema, and seed consistency.\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
