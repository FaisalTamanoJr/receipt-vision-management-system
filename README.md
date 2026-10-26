# Receipt Manager

An offline Windows desktop app that scans receipts, reads them with OCR, and lets staff sort, search, and ask questions about them.

Developed by **CPECAPS Group 3** for **Device for Spine and Brain Medical**.

## Where we are

| Part | Status |
|---|---|
| Database (tables, migrations, sample data) | Done |
| Repositories (add, get, update, delete, filter, sort) | Done |
| Login / roles | Not started |
| Scanning, OCR, review screen | Not started |
| UI (PySide6) | Not started |
| Chatbot | Not started |
| Backup, packaging | Not started |

## Setup

You need Python 3.11+ and Git.

```bash
git clone git@github.com:FaisalTamanoJr/receipt-vision-management-system.git
cd receipt-vision-management-system

python3.11 -m venv .venv
source .venv/bin/activate        # fish: .venv/bin/activate.fish, Windows: .venv\Scripts\activate

pip install -e ".[dev]"
python scripts/seed.py           # creates your local database with sample data
```

The database is not in git. Everyone gets their own copy at:

- Linux: `~/.local/share/ReceiptManager/receipts.db`
- Windows: `%LOCALAPPDATA%\ReceiptManager\receipts.db`

Sample logins from the seed: `admin` / `admin123` and `staff` / `staff123`.

## Using the database

Use the repositories, don't write SQLAlchemy queries in other parts of the app.
They take and return the plain dataclasses in `core/models.py`.

```python
from receipt_manager.data.repository import ReceiptFilter, ReceiptRepository

receipts = ReceiptRepository()
september = receipts.find(ReceiptFilter(year=2026, month=9))
```

## Changing the tables

1. Edit `src/receipt_manager/data/orm_models.py` (and the matching dataclass in `core/models.py` and `data/mappers.py`).
2. Create a migration:
   ```bash
   python -m receipt_manager.data.migrate revision "what you changed"
   ```
3. Read the new file in `data/migrations/versions/` to check it, then apply it:
   ```bash
   python -m receipt_manager.data.migrate
   ```
4. Commit the model change and the migration together.

**After pulling**, run `python -m receipt_manager.data.migrate` (or `python scripts/seed.py`) to update your database.

If your database gets messed up, delete `receipts.db` and run `python scripts/seed.py` again.

## Project layout

```
src/receipt_manager/
├── core/          # dataclasses the rest of the app uses (no database code)
└── data/
    ├── orm_models.py   # database tables
    ├── mappers.py      # converts between tables and dataclasses
    ├── repository.py   # add, get, update, delete, filter, sort
    ├── engine.py       # database connection
    ├── migrate.py      # runs migrations
    └── migrations/     # migration files
scripts/seed.py    # sample data
tests/             # (empty for now)
```

Planned folders: `scanning/`, `ocr/`, `chat/`, `ui/`.

## Before you push

```bash
ruff check .
```

## Ground rules

- Never commit real receipts. Put test images in `sample_receipts/`, which git ignores.
- We develop on Linux but ship to Windows, so keep Windows-only code (scanner drivers, installer) behind an interface.
- Run slow work (OCR, the chatbot) on a background thread so the UI doesn't freeze.
