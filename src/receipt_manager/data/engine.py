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
