# Receipt Manager

An offline Windows desktop app that scans receipts, reads them with OCR, and lets staff sort, search, and ask questions about them.

## Where we are

| Part | Status |
|---|---|
| Database (tables, migrations, sample data) | Done |
| Repositories (add, get, update, delete, filter, sort) | Done |
| Login / roles | Done (login dialog, Admin and Staff roles, `auth/`) |
| OCR | In progress (Gemini test app in `ocr/`) |
| Scanning, review screen | Not started |
| UI: Home and Settings pages | Done (HTML pages in a PySide6 window) |
| UI: Receipts, Scan, Login, Receipt details pages | Not started |
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

Before Oct 28, 2026 the Windows copy was in `%LOCALAPPDATA%\ReceiptManager\ReceiptManager\` by mistake. If you have one there, run `python scripts\seed.py` to make a new one in the right place, then delete the old folder.

Sample logins from the seed: `admin` / `admin123` and `staff` / `staff123`.

To add your own account:

```powershell
python scripts\create_user.py
```

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

## UI

The screens are HTML/CSS/JS pages in `src/receipt_manager/ui/web/`, shown inside a PySide6 window (`ui/app.py`).
The pages get their data from Python through `ui/bridge.py`, so they never touch the database themselves.

Run the app (after the setup above):

```powershell
python -m receipt_manager.ui.app
```

You can also double-click `home.html` to open it in a browser while working on the design. It uses sample data there, since there's no Python behind it.

**Adding a page** (e.g. `receipts.html`)

1. Put it in `ui/web/`. In its `<head>` add, in this order:
   ```html
   <link rel="stylesheet" href="css/styles.css">
   <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
   <script src="js/common.js"></script>
   ```
   `common.js` gives you dark mode, the icons (`<use href="#i-file"/>`), `App.toast()` and `App.peso()`.
2. Put its script in `ui/web/js/`. Load libraries from `ui/web/vendor/`, not from a CDN, because the app has to work offline.
3. If it needs data, add a `@Slot` method to `Bridge` in `ui/bridge.py` that calls a repository and returns JSON. Call it from JS with:
   ```js
   const stats = await App.api('getStats');           // null when opened in a plain browser
   const proj  = await App.api('getProjection', 12);  // arguments are passed through
   ```

The nav links already point to `receipts.html` and `scan.html`. Still to do (marked `TODO` in `js/settings.js`): moving files when the storage folder changes, and deleting scanned image files. These wait on scanning.

## Login and roles

The app opens a login dialog (`ui/login_dialog.py`) before the main window. Signing out from the Home page shows it again.

`auth/service.py` has `AuthService`, which the window keeps for the whole session:

```python
from receipt_manager.auth.permissions import Page

auth.current_user            # the User dataclass, None when logged out
auth.current_role            # RoleName.ADMIN or RoleName.STAFF
auth.can_access(Page.SEARCH) # use this to decide whether to show a page
auth.require(Page.SEARCH)    # raises PermissionDenied, use it before changing data
```

Which role can open which page is in `ROLE_PAGES` in `auth/permissions.py`. Admin can open everything, Staff only the upload page.
Clearing all receipts (Settings > Data Management) needs `Page.DATA_MANAGEMENT`, so only Admin can do it.

To stop someone from logging in without deleting them (their receipts still point to them), set `is_active` to `False`:

```python
user = UserRepository().get_by_username("staff")
user.is_active = False
UserRepository().update(user)
```
The pages can ask for the logged in user with `await App.api('getCurrentUser')`, which returns the username, full name, role and allowed pages.

Passwords are hashed with argon2 (`auth/security.py`). Databases seeded before this still work, their old hashes are upgraded on the next login.

Settings are saved to `settings.json` next to the database.

## OCR (work in progress)

`src/receipt_manager/ocr/receipt_extractor.py` is a standalone Tkinter app for testing OCR on handwritten Philippine collection receipts. It isn't hooked into the main app yet: it sends images to Google Gemini (online), while the real app is meant to be offline.

Workflow: upload image(s), the fields get filled in, fix anything wrong, **Save Record** (appends to `receipts.csv`), and the next image loads.

Its packages are installed by the normal setup. Set your own Gemini key (free at https://aistudio.google.com/apikey) and run it. In PowerShell:

```powershell
$env:GEMINI_API_KEY = "your_key"
python -m receipt_manager.ocr.receipt_extractor
```

In Command Prompt use `set GEMINI_API_KEY=your_key`. On Linux, `export GEMINI_API_KEY=your_key` (fish: `set -x GEMINI_API_KEY your_key`).

- Don't put the key in the code. Each person uses their own.
- On Gemini's free tier, Google may use the images to improve its models, so names and TINs leave your computer. Use test receipts.
- There's also a local Ollama option (`pip install ollama`, `ollama pull qwen2.5vl:7b`, then set `OCR_BACKEND=ollama`). It works offline but is slower and less accurate, and isn't fully built out.
- `receipts.csv` is written to the folder you run it from and is ignored by git.

## Project layout

```
src/receipt_manager/
├── core/          # dataclasses the rest of the app uses (no database code)
├── auth/          # login, password hashing, which role can open which page
├── ocr/           # OCR (WIP: Gemini test app)
├── ui/
│   ├── app.py          # main window, run with python -m receipt_manager.ui.app
│   ├── bridge.py       # what the pages can ask Python for
│   ├── login_dialog.py # shown before the main window
│   └── web/            # the pages: *.html, css/, js/, vendor/ (Chart.js)
└── data/
    ├── orm_models.py   # database tables
    ├── mappers.py      # converts between tables and dataclasses
    ├── repository.py   # add, get, update, delete, filter, sort
    ├── engine.py       # database connection
    ├── migrate.py      # runs migrations
    └── migrations/     # migration files
scripts/seed.py      # sample data
scripts/create_user.py  # add an admin or staff account
scripts/examples.py  # how to use the repositories
tests/               # (empty for now)
```

Planned folders: `scanning/`, `chat/`.

## Before you push

```bash
ruff check .
```

## Some other reminders

- Never commit real receipts. Put test images in `sample_receipts/`, which git ignores.
- Keep Windows-only code (scanner drivers, installer) behind an interface, and build file paths with `pathlib` instead of hardcoding `\` or `/`. This is so that it there won't be issues with Linux and Windows development
- Run slow work (OCR, the chatbot) on a background thread so the UI doesn't freeze.
