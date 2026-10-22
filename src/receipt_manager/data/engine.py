"""
This is the engine that provides
the Connection/Session object. SQLAlchemy
objects rely on this to interact with the
database.

Helpful reference:
https://docs.sqlalchemy.org/en/20/tutorial/engine.html#tutorial-engine
"""

from sqlalchemy import create_engine
from pathlib import Path
from platformdirs import user_data_dir

# %LOCALAPPDATA%\ReceiptManager\ in Windows, ~/.local/share/ReceiptManager/ in Linux
data_dir = Path(user_data_dir("ReceiptManager"))
data_dir.mkdir(parents=True, exist_ok=True)

# for testing
# engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
# for real
engine = create_engine(f"sqlite+pysqlite:///{data_dir / 'receipts.db'}")
