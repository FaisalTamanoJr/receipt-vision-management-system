"""
This is the engine that provides
the Connection/Session object. SQLAlchemy
objects rely on this to interact with the
database.

Helpful reference:
https://docs.sqlalchemy.org/en/20/tutorial/engine.html#tutorial-engine
https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support
"""

import sqlite3
from pathlib import Path

from platformdirs import user_data_dir
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# %LOCALAPPDATA%\ReceiptManager\ in Windows, ~/.local/share/ReceiptManager/ in Linux
# appauthor=False, otherwise Windows adds a second ReceiptManager\ folder for the "company"
data_dir = Path(user_data_dir("ReceiptManager", appauthor=False))
data_dir.mkdir(parents=True, exist_ok=True)


# SQLite ignores foreign keys unless this is turned on for every connection.
# Without it, deleting a Role or User that still has rows pointing at it would succeed.
# Listening on Engine (the class) also covers the test engines.
@event.listens_for(Engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# for testing
# engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
# for real
engine = create_engine(f"sqlite+pysqlite:///{data_dir / 'receipts.db'}")

# repositories open their sessions from this
SessionLocal = sessionmaker(engine)
