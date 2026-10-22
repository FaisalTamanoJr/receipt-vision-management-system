# Receipt Manager

An offline, single-device Windows application that digitizes physical receipts, extracts their details with OCR, organizes them by date and type, and lets staff query them through a local AI assistant.

Developed by **CPECAPS Group 3** for **Device for Spine and Brain Medical**.

> **Status:** Preliminary. Scope, stack, and structure are still being finalized (see [Open Questions](#open-questions)).

---

## Table of Contents

1. [Background](#background)
2. [Goals and Success Criteria](#goals-and-success-criteria)
3. [Features](#features)
4. [System Overview](#system-overview)
5. [Tech Stack](#tech-stack)
6. [Repository Structure](#repository-structure)
7. [Data Model](#data-model)
8. [Getting Started](#getting-started)
9. [Development Notes](#development-notes)
10. [Key Risks](#key-risks)
11. [Roadmap](#roadmap)
12. [Open Questions](#open-questions)

---

## Background

The client stores, organizes, searches, and reviews receipts manually, and reviews them monthly. This works at small scale but becomes a bottleneck as the business grows, because the effort scales with the number of receipts.

Problems with the current process:

- Human error and mismanagement
- No robust backup, so records can be lost
- No error or conflict detection
- No efficient way to migrate or transfer data
- No reliable authentication for authorized access
- Slow retrieval and sorting
- No accountability trail (who recorded, accessed, or modified a record, and when)

**Who benefits:** employees who handle the data (less workload), employees who analyze it (faster lookups), and clients who request receipts (their data is protected from loss and unauthorized access).

## Goals and Success Criteria

**Primary criterion: throughput.** The system must store, sort, search, and organize receipts faster than the current manual method. If it does not, it is not an appropriate solution.

Supporting goals:

- Accurate extraction of receipt data, with human review and correction
- Reliable date-based classification and retrieval
- Secure, role-based access to confidential records
- Dependable local backup and restore
- Full audit trail of record activity

## Features

**Planned**

- **Scan and digitize** receipts from a scanner or camera, or by importing image files
- **Image cleanup** (auto-crop, deskew, contrast) before OCR
- **OCR extraction** of receipt number, purchase date, total, payer details, payment method, and line items
- **Review screen** showing the original image beside the extracted text, with manual correction
- **Filter and sort** by date (year, month, day), type, merchant, and amount
- **Duplicate detection** on upload
- **Authentication and RBAC** (login, roles, permissions)
- **Encrypted local storage**
- **Audit log** of who created, viewed, or modified records
- **Backup and restore** (local ZIP and CSV export)
- **AI chatbot** that answers questions about stored receipts using a local model, with no internet connection

## System Overview

The application runs entirely on one Windows machine. No network features, cloud services, or telemetry.

```
Scanner / Camera / File import
        |
        v
  Ingestion service ──> Image preprocessing ──> OCR extraction
                                                     |
                                                     v
                              Field parsing + validation (dates, totals)
                                                     |
                                                     v
                         Review and correct (original image | extracted text)
                                                     |
                                                     v
                         Encrypted SQLite database + image store
                                                     |
                                   ┌─────────────────┴───────────────┐
                                   v                                 v
                          Filter / sort / search            Local AI chatbot
                                                       (safe, read-only query tools)
```

**Layers** (from the architecture diagram):

| Layer | Responsibility |
|---|---|
| Hardware | Camera or scanner, workstation |
| Firmware / drivers | Image sensor and USB drivers, TWAIN/WIA |
| Software | Ingestion, OCR/ML extraction, authentication (RBAC), encrypted database |
| User interface | Login, date search, split view of original image and extracted text |

**Chatbot design:** the model never receives the whole database. It calls a small set of validated, read-only tools (for example `get_spending(category, date_range)` or `find_receipts(merchant)`). SQL does the arithmetic and the model phrases the result.

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| UI | PySide6 (Qt) |
| Image processing | `opencv-python-headless` |
| OCR | `rapidocr-onnxruntime` (primary), Tesseract (alternative) |
| Database | SQLite (FTS5 for search), `sqlcipher3` for encryption |
| Local LLM | `llama-cpp-python` with a quantized `.gguf` model |
| Date parsing | `dateparser` |
| Scanning (Windows) | NAPS2 CLI, or WIA/TWAIN via `pywin32` / `pytwain` |
| Paths | `platformdirs` |
| Tooling | `pytest`, `ruff` |
| Packaging | PyInstaller (or Nuitka) plus Inno Setup or NSIS |

## Repository Structure

```
receipt-manager/
├── pyproject.toml
├── README.md
├── src/receipt_manager/
│   ├── app.py            # entry point and wiring
│   ├── core/             # models, interfaces, extraction and categorization rules
│   ├── scanning/         # Scanner interface, file import, NAPS2, WIA
│   ├── ocr/              # RapidOCR / Tesseract wrappers
│   ├── data/             # SQLite, migrations, repository, backup
│   ├── chat/             # local LLM runner, safe query tools, prompts
│   └── ui/               # PySide6 windows, views, viewmodels, resources
├── models/               # .gguf and OCR model files (not committed, see below)
├── tests/
├── sample_receipts/      # test images (authorized data only)
├── packaging/            # PyInstaller spec, installer script, bundled NAPS2
├── scripts/              # build and model-download helpers
└── docs/                 # architecture, ERD, DFD, risk register
```

**Design rule:** `core/` depends on nothing. `scanning/`, `ocr/`, `data/`, and `chat/` depend only on `core/` and are swappable behind interfaces. `ui/` contains screens only, with no business logic.

**Runtime data** (on the client machine, separate from the install folder):

```
%LOCALAPPDATA%\ReceiptManager\
├── receipts.db
├── images/            # originals, organized by year/month
├── thumbnails/
├── backups/
├── logs/
└── settings.json
```

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- A model file for the chatbot (`.gguf`) and OCR model files, placed in `models/`

### Setup

```bash
git clone <repo-url>
cd receipt-manager

python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

### Models

Large model files are not committed to git. Download them with:

```bash
python scripts/download_models.py
```

(or place them manually in `models/llm/` and `models/ocr/`).

### Run

```bash
python -m receipt_manager.app
```

### Test

```bash
pytest
ruff check .
```

## Development Notes

- **Cross-platform development:** the team develops on Linux and ships to Windows. Anything Windows-specific (scanner drivers, installer) sits behind an interface, with a file-import or fake implementation for Linux development.
- **Windows builds:** PyInstaller cannot cross-compile. Build the `.exe` on a Windows machine or a `windows-latest` CI runner and test it on a Windows VM or a PC matching the client's specs.
- **Dependencies:** `pyproject.toml` is the source of truth. Generate a lock file per platform and pin exact versions before release.
- **Responsiveness:** run OCR and LLM calls on worker threads (`QThread` / `QThreadPool`) so the UI never freezes.
- **Test data:** use only receipt samples authorized by the client, and never commit real receipts to a public repository.

## Key Risks

Top risks from the project risk register (exposure = likelihood x impact), reviewed weekly:

| # | Risk | Exposure | Main mitigation |
|---|---|---|---|
| 1 | Inaccurate OCR extraction | 20 | Test on varied formats, improve preprocessing, allow manual correction while keeping the original image |
| 2 | Incorrect receipt date classification | 16 | Date validation and verification before saving, manual reclassification |
| 3 | Slow processing and retrieval | 16 | Optimize queries, image handling, and search; benchmark against the manual process |
| 4 | Unauthorized access | 15 | Secure authentication, RBAC, encrypted storage |
| 5 | Loss or corruption of records | 15 | Automated backups with integrity checks, restore from the latest verified backup |

Other tracked risks: poor image quality, incomplete digitization, duplicate entries, downtime, and insufficient OCR test data. See `docs/` for the full register.

## Roadmap

1. **Spikes:** OCR accuracy on 20 to 30 real receipts; local LLM load time and speed on client-spec hardware
2. **Foundation:** core models and interfaces, database schema and migrations, authentication
3. **Pipeline:** scanning or import, preprocessing, OCR, parsing, validation, review screen
4. **Retrieval:** date and type filtering, sorting, full-text search, duplicate detection
5. **Chatbot:** local model integration with read-only query tools
6. **Hardening:** encryption, audit log, backup and restore, performance benchmarks against the manual process
7. **Packaging:** Windows installer, signed build, testing on target hardware

## Open Questions

These should be settled with the client and team before the structure is final:

1. **Offline vs. network.** The architecture diagram shows a website GUI talking to a backend over an HTTPS REST API on the local LAN, but the current requirement is a single-device app with no network features. Which is correct? (This README assumes a single-device desktop app.)
2. **Chatbot scope.** The problem statement and risk register do not mention the AI chatbot. Confirm it is in scope and what questions it should answer.
3. **Inventory scope.** The ERD includes `InventoryItem`, `StockLedger`, and `Supplier` (stock-out estimation, reorder thresholds), which goes beyond receipt storage. Is inventory tracking part of this project?
4. **Receipt types.** The data flow diagram refers to "collection receipts" with payer and payment details, while the ERD also models purchased items. Confirm which receipt types the client handles.
5. **Multi-user access.** RBAC implies several users. On a single device, will users share the machine with separate logins?
6. **Hardware.** What are the client's RAM, CPU, and GPU? This decides the model size and OCR engine.

## License

TBD.
