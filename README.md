# Receipt Manager

An offline Windows desktop app that scans receipts, reads them with OCR, and lets staff sort, search, and ask questions about them.

## Where we are

| Part | Status |
|---|---|
| Database (tables, migrations, sample data) | Done |
| Repositories (add, get, update, delete, filter, sort) | Done |
| Login / roles | Not started |
| Scanning, OCR, review screen | Not started |
| UI (could be PySide6) | Not started |
| Chatbot | Not started |
| Backup, packaging | Not started |

## Setup

You need Python 3.11+ and Git.

In PowerShell:

```powershell
git clone git@github.com:FaisalTamanoJr/receipt-vision-management-system.git
cd receipt-vision-management-system

py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
python scripts\seed.py           # creates your local database with sample data
```

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
In Command Prompt, activate with `.venv\Scripts\activate.bat` instead.

On Linux, use `python3.11 -m venv .venv` and `source .venv/bin/activate` (fish: `.venv/bin/activate.fish`).

The database is not in git. Everyone gets their own copy at:

- Windows: `%LOCALAPPDATA%\ReceiptManager\receipts.db`
- Linux: `~/.local/share/ReceiptManager/receipts.db`

Sample logins from the seed: `admin` / `admin123` and `staff` / `staff123`.

## Using the database

Use the repositories, don't write SQLAlchemy queries in other parts of the app.
They take and return the plain dataclasses in `core/models.py`.

For a full example you can run, see `scripts/examples.py`. It uses a throwaway in-memory database, so your real one isn't touched:

```bash
python scripts/examples.py
```

**Add, get, update, delete**

```python
from datetime import date
from decimal import Decimal

from receipt_manager.core.models import Receipt, ReceiptItem
from receipt_manager.data.repository import ReceiptRepository

receipts = ReceiptRepository()

# add() returns a copy with the id filled in, the items are saved with the receipt
receipt = receipts.add(
    Receipt(
        user_id=1,
        receipt_number="OR-0100",
        original_image_path="sample_receipts/or-0100.jpg",
        purchase_date=date(2026, 10, 5),
        total_amount=Decimal("9000.00"),
        payer_name="The Medical City",
        items=[
            ReceiptItem(
                inventory_item_id=1,
                quantity=2,
                unit_price=Decimal("4500.00"),
                total_price=Decimal("9000.00"),
            )
        ],
    )
)

receipts.get(receipt.id)      # None if it doesn't exist

receipt.payer_name = "The Medical City - Ortigas"
receipts.update(receipt)      # items removed from receipt.items get deleted

receipts.delete(receipt.id)   # False if it didn't exist, its items are deleted too
```

**Filter, sort, page**

Every field in `ReceiptFilter` is optional. All the fields you fill in must match.

```python
from receipt_manager.data.repository import ReceiptFilter

september = ReceiptFilter(year=2026, month=9)
receipts.find(september)                                   # newest first by default
receipts.find(ReceiptFilter(text="luke", min_amount=Decimal(10000)))
receipts.find(sort_by="total_amount", descending=True, limit=20, offset=0)

receipts.count_matching(september)   # for "showing 20 of 134"
receipts.total_amount(september)     # sum, Decimal(0) if nothing matches
```

`sort_by` only accepts the columns in that repository's `_SORTABLE`. Anything else raises `ValueError`.

**Duplicates** (before saving a newly scanned receipt)

```python
matches = receipts.find_duplicates(scanned)   # same number, or same date + total + payer
if matches:
    ...  # let the review screen decide
```

**Other repositories**

```python
from receipt_manager.data.repository import InventoryItemRepository, UserRepository

UserRepository().get_by_username("admin")
InventoryItemRepository().find(product_type_id=1, sort_by="name")
InventoryItemRepository().name_exists("Pedicle Screw 6.5mm")   # names are unique, check before add()
```

`RoleRepository`, `ProductTypeRepository` and `SupplierRepository` have the same `get_by_name`, `name_exists` and `search_by_name` methods.

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
scripts/seed.py      # sample data
scripts/examples.py  # how to use the repositories
tests/               # (empty for now)
```

Planned folders: `scanning/`, `ocr/`, `chat/`, `ui/`.

## Before you push

```bash
ruff check .
```

## Some other reminders

- Never commit real receipts. Put test images in `sample_receipts/`, which git ignores.
- Keep Windows-only code (scanner drivers, installer) behind an interface, and build file paths with `pathlib` instead of hardcoding `\` or `/`. This is so that it there won't be issues with Linux and Windows development
- Run slow work (OCR, the chatbot) on a background thread so the UI doesn't freeze.
