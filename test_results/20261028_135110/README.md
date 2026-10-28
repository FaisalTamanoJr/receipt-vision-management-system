# Test Run 20261028_135110

Results of running `CPECAPS_TestPlanv1_Group3.xlsx` (TC-01 to TC-10) on 2026-10-28, code at commit `c8af4bb`.

Made by `scripts/run_test_plan.py`. To run it again (PowerShell, from the repo root with the venv active):

```powershell
python scripts\run_test_plan.py
```

Each run makes a new `test_results\<YYYYMMDD_HHMMSS>\` folder.

## Results

| Test | Type | Result | Measured | Threshold |
|---|---|---|---|---|
| TC-01 Original image stored/displayed | FR | PASS | byte-identical copy, decodes 1920x1080 px | stored = original |
| TC-02 Text extracted and saved with record | FR | **FAIL** | 40 lines extracted | text saved _with the record_ |
| TC-03 Search by year/month/day | FR | PASS | 6/6 queries correct | all levels correct |
| TC-04 Image + text shown for same record | FR | **FAIL** | image yes, text not in record | both in the same record |
| TC-05 Unauthorized access blocked | NFR | **FAIL** | 13/14 checks | 14/14 |
| TC-06 No external transmission | NFR | PASS | 0 external connections | 0 |
| TC-07 OCR accuracy | NFR | **FAIL** | 80.37 % | ≥ 90 % _(provisional)_ |
| TC-08 Date search response time (p95) | NFR | PASS | 33.89 ms | ≤ 1000 ms _(provisional)_ |
| TC-09 Open + render record (p95) | NFR | PASS | 18.86 ms | ≤ 2000 ms _(provisional)_ |
| TC-10 Storage capacity | NFR | PASS | 29.07 GB free | ≥ 10 GB _(provisional)_ |

## Files

Names follow the test plan’s Data Capture sheet. `CR-0004` is the receipt ID and `2025-05-14` its purchase date.

| File | Contents |
|---|---|
| `raw_data.csv` | Every measurement, one row each (328 rows) |
| `summary.csv` | One PASS/FAIL row per test case |
| `validation/CR-0004_2025-05-14_validation.csv` | OCR accuracy per receipt field (TC-07) |
| `validation/TC-03_date_filter_results.csv` | Each date filter, expected vs. returned receipts |
| `access/TC-05_CR-0004_access.csv` | Each access attempt and its outcome |
| `network/TC-06_network_log.csv` | Socket events and 100 ms socket samples during processing |
| `calibration/environment.csv` | OS, hardware, storage, software and OCR model versions |
| `calibration/ocr_calibration.csv` | Known-sample OCR check on printed text, run before testing |
| `calibration/access_matrix.csv` | Pages each role may open, checked before TC-05 |
| `screenshots/setup_0*.png` | Workstation, software versions, summary, file list (taken with `freeze`) |

## Fields

All timestamps are ISO 8601 local time with milliseconds and UTC offset (e.g. `2026-10-28T13:51:12.086+08:00`).

**raw_data.csv**

| Field | Meaning |
|---|---|
| `timestamp` | When the value was recorded |
| `test_case` | `TC-01`…`TC-10`, or `CAL` for calibration |
| `receipt_id` | Receipt the value belongs to (blank if none) |
| `iteration` | Repeat number for repeated measurements (blank if measured once) |
| `measurement` | What was measured, e.g. `search_time:year_month` |
| `value` | The measured value |
| `unit` | Unit of `value` (see below) |
| `notes` | Extra context, e.g. result counts or filter criteria |

**summary.csv**: `timestamp`, `test_case`, `type` (FR/NFR), `result` (PASS/FAIL), `measured_value`, `unit`, `threshold`, `notes`.

**validation CSV (TC-07)** and **ocr_calibration.csv**: `kind` (handwritten/printed), `field`, `edit_distance_chars` (characters wrong), `ground_truth_chars`, `char_accuracy_pct` (= 1 − edit distance ÷ length, %), `exact_match` (1/0). Text is compared uppercase, letters and digits only.

**TC-05 access CSV**: `user`, `action`, `expected` / `observed` (allowed/blocked), `result` (PASS/FAIL), `detail` (exception or returned data).

**TC-06 network log**: `source` (`audit_hook` = Python socket calls, `ss` = OS socket table), `event`, `detail`. Rows with `open_sockets` give the socket count at that moment.

### Units

| Unit | Meaning |
|---|---|
| `ms` | milliseconds (wall clock, `time.perf_counter`) |
| `%` | percent, 0–100 |
| `bool` | 1 = yes/true, 0 = no/false |
| `pass=1` | 1 = check passed, 0 = failed |
| `bytes`, `GB` | file/disk size (GB = 10⁹ bytes) |
| `px` | pixels |
| `0-1` | OCR engine confidence score |
| `EXIF code` | EXIF orientation tag, 1 = upright, 8 = rotated 90° |
| `lines`, `chars`, `receipts`, `events`, `sockets`, `samples` | counts |

## Setup

+ Workstation: CachyOS Linux, i7-12700H (20 threads), 15.4 GB RAM, 29 GB free on a 146 GB drive. Python 3.11.15.
+ OCR: RapidOCR 1.4.4 (onnxruntime 1.31.0, PP-OCRv4 models), offline, on CPU.
+ Database: a new SQLite file per run (`test.db`). The real `receipts.db` was not used.
+ Accounts: `admin` (Admin, authorized), `staff` (Staff, not authorized for receipt pages), `former` (deactivated).
+ Receipt set: 1 real receipt (`CR-0004`) + 3 receipts with known dates from `seed.py` + 5,000 generated receipts for TC-08 (random seed 42, dates 2023–2026).
+ Repeats: 50 timed runs per search (after 3 warm-ups), 50 for rendering, 3 for OCR.
