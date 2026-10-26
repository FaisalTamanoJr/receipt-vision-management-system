"""
Runs the Alembic migrations from Python, so the app can bring
the database up to date on startup without needing alembic.ini
(it isn't bundled with the packaged app).

From the app:
    from receipt_manager.data.migrate import upgrade
    upgrade()

From the terminal:
    python -m receipt_manager.data.migrate                      # upgrade to head
    python -m receipt_manager.data.migrate revision "add notes"  # autogenerate
    python -m receipt_manager.data.migrate downgrade -1
    python -m receipt_manager.data.migrate current
    python -m receipt_manager.data.migrate history

The plain alembic cli works too from the repo root, e.g.
    alembic revision --autogenerate -m "add notes"

Helpful reference:
https://alembic.sqlalchemy.org/en/latest/api/commands.html
"""

import argparse
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # same as alembic.ini, so files sort by date no matter which way they were made
    config.set_main_option(
        "file_template",
        "%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s",
    )
    return config


def upgrade(revision: str = "head") -> None:
    command.upgrade(_config(), revision)


def downgrade(revision: str = "-1") -> None:
    command.downgrade(_config(), revision)


# compares orm_models.py with the database and writes a new file in migrations/versions,
# always read it over before committing, autogenerate misses some changes (e.g. renames)
def revision(message: str, autogenerate: bool = True) -> None:
    command.revision(_config(), message=message, autogenerate=autogenerate)


def current() -> None:
    command.current(_config(), verbose=True)


def history() -> None:
    command.history(_config())


def main() -> None:
    parser = argparse.ArgumentParser(description="Database migrations")
    sub = parser.add_subparsers(dest="cmd")

    up = sub.add_parser("upgrade", help="upgrade to a revision (default: head)")
    up.add_argument("revision", nargs="?", default="head")

    down = sub.add_parser("downgrade", help="downgrade to a revision (default: -1)")
    down.add_argument("revision", nargs="?", default="-1")

    rev = sub.add_parser("revision", help="create a new revision")
    rev.add_argument("message")
    rev.add_argument("--empty", action="store_true", help="skip autogenerate")

    sub.add_parser("current", help="show the database's revision")
    sub.add_parser("history", help="list all revisions")

    args = parser.parse_args()
    # alembic prints its progress through logging, the app leaves this to its own setup
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s %(message)s")

    if args.cmd in (None, "upgrade"):
        upgrade(getattr(args, "revision", "head"))
    elif args.cmd == "downgrade":
        downgrade(args.revision)
    elif args.cmd == "revision":
        revision(args.message, autogenerate=not args.empty)
    elif args.cmd == "current":
        current()
    elif args.cmd == "history":
        history()


if __name__ == "__main__":
    main()
