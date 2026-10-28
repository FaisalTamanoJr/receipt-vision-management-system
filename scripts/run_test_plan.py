"""
Runs CPECAPS_TestPlanv1_Group3.xlsx (TC-01 to TC-10) against the current code
and writes the raw data to test_results/<run_id>/. See the README.md written
in that folder for what each file and field means.

Uses its own throwaway database in the run folder, so your real receipts.db
is never touched. OCR uses RapidOCR (offline), never the Gemini backend,
since receipt images must not leave the machine.

Usage:
    python scripts/run_test_plan.py
    python scripts/run_test_plan.py --image sample_receipts/collection-receipt-0004.jpg

The image needs a hand-made ground truth next to it, e.g.
sample_receipts/collection-receipt-0004.truth.json (receipt_id, receipt_number,
purchase_date, record, handwritten and printed fields). It holds client details,
so it lives in sample_receipts/ (ignored by git), and the receipt text itself is
never written to the results, only the scores.
"""

import argparse
import csv
import hashlib
import importlib.metadata as md
import json
import os
import platform
import random
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # render without opening windows
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from receipt_manager.auth.permissions import ROLE_PAGES, Page, RoleName
from receipt_manager.auth.service import (
    AuthService,
    InvalidCredentials,
    PermissionDenied,
    create_user,
)
from receipt_manager.core.models import Receipt
from receipt_manager.data.orm_models import Base
from receipt_manager.data.repository import (
    ReceiptFilter,
    ReceiptRepository,
    RoleRepository,
    UserRepository,
)

ROOT = Path(__file__).resolve().parent.parent

# Provisional pass/fail thresholds. The test plan says to use the targets in the
# constraint matrix, but no numbers were given, so these are placeholders.
# Change them here once the real targets are agreed on.
THRESHOLDS = {
    "TC-07": (90.0, "%", ">=", "mean character accuracy of handwritten fields"),
    "TC-08": (1000.0, "ms", "<=", "p95 date-search response time"),
    "TC-09": (2000.0, "ms", "<=", "p95 time to open record + render image and text"),
    "TC-10": (10.0, "GB", ">=", "free space on the receipt storage drive"),
}

# receipts with known dates for TC-03 (the 3 from scripts/seed.py plus the sample image)
KNOWN_RECEIPTS = [
    ("OR-0001", date(2026, 9, 3), "St. Luke's Medical Center", "33400.00"),
    ("OR-0002", date(2026, 9, 17), "The Medical City", "27960.00"),
    ("OR-0003", date(2026, 10, 2), "St. Luke's Medical Center", "4200.00"),
]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class Recorder:
    """Appends every measurement to raw_data.csv as it is taken."""

    COLUMNS: ClassVar[list[str]] = [
        "timestamp",
        "test_case",
        "receipt_id",
        "iteration",
        "measurement",
        "value",
        "unit",
        "notes",
    ]

    def __init__(self, path: Path) -> None:
        self._file = path.open("w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._file)
        self._csv.writerow(self.COLUMNS)

    def __call__(self, tc, measurement, value, unit, *, receipt_id="", iteration="", notes=""):
        self._csv.writerow([now(), tc, receipt_id, iteration, measurement, value, unit, notes])
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def normalize(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


def best_match_distance(needle: str, haystack: str) -> int:
    """Smallest edit distance between needle and any substring of haystack."""
    prev = [0] * (len(haystack) + 1)
    for i in range(1, len(needle) + 1):
        cur = [i] + [0] * len(haystack)
        for j in range(1, len(haystack) + 1):
            cost = needle[i - 1] != haystack[j - 1]
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return min(prev)


def score_fields(fields: dict[str, str], lines: list[str]) -> list[dict]:
    rows = []
    for name, truth in fields.items():
        gt = normalize(truth)
        # match against each line so a field can't be pieced together from unrelated text
        dist = min(best_match_distance(gt, normalize(line)) for line in lines)
        accuracy = max(0.0, 1 - dist / len(gt)) * 100
        rows.append(
            {
                "field": name,
                "edit_distance_chars": dist,
                "ground_truth_chars": len(gt),
                "char_accuracy_pct": round(accuracy, 2),
                "exact_match": int(dist == 0),
            }
        )
    return rows


def run_ocr(engine, image: Path) -> tuple[list[str], list[float], float]:
    start = time.perf_counter()
    result, _ = engine(str(image))
    elapsed = (time.perf_counter() - start) * 1000
    result = result or []
    return [r[1] for r in result], [float(r[2]) for r in result], elapsed


# Environment / calibration


def environment_rows(storage_dir: Path) -> list[dict]:
    def version(pkg):
        try:
            return md.version(pkg)
        except md.PackageNotFoundError:
            return "not installed"

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        ).stdout.strip()
    except OSError:
        commit, dirty = "unknown", ""

    usage = shutil.disk_usage(storage_dir)
    mem_gb = ""
    if Path("/proc/meminfo").exists():
        kb = int(Path("/proc/meminfo").read_text().split("\n")[0].split()[1])
        mem_gb = round(kb / 1024**2, 2)

    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break

    rows = [
        ("os", platform.platform(), ""),
        ("hostname_hash", hashlib.sha256(socket.gethostname().encode()).hexdigest()[:12], ""),
        ("cpu", cpu, ""),
        ("cpu_logical_cores", os.cpu_count(), "count"),
        ("ram_total", mem_gb, "GB"),
        ("storage_dir", str(storage_dir), ""),
        ("storage_total", round(usage.total / 1e9, 2), "GB"),
        ("storage_free", round(usage.free / 1e9, 2), "GB"),
        ("python", platform.python_version(), ""),
        ("git_commit", commit + (" (uncommitted changes)" if dirty else ""), ""),
        ("ocr_engine", "rapidocr-onnxruntime " + version("rapidocr-onnxruntime"), ""),
        ("onnxruntime", version("onnxruntime"), ""),
        ("pyside6", version("pyside6"), ""),
        ("sqlalchemy", version("sqlalchemy"), ""),
        ("sqlite", __import__("sqlite3").sqlite_version, ""),
        ("argon2-cffi", version("argon2-cffi"), ""),
        ("network_setup", "workstation online; app has no network features; OCR offline", ""),
    ]
    import rapidocr_onnxruntime

    model_dir = Path(rapidocr_onnxruntime.__file__).parent / "models"
    for model in sorted(model_dir.glob("*.onnx")):
        rows.append((f"ocr_model:{model.name}", sha256(model)[:16], "sha256 prefix"))
    return [{"timestamp": now(), "item": k, "value": v, "unit": u} for k, v, u in rows]


# Network monitor for TC-06


class NetworkMonitor:
    """Logs every socket event this process makes (audit hook) and samples its
    open connections with `ss` while the workflow runs."""

    WATCHED: ClassVar[set[str]] = {"socket.connect", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
               "socket.bind", "urllib.Request", "http.client.connect"}

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.samples: list[dict] = []
        self.active = False
        self._stop = threading.Event()
        sys.addaudithook(self._hook)

    def _hook(self, event, args) -> None:
        if self.active and event in self.WATCHED:
            self.events.append({"timestamp": now(), "source": "audit_hook",
                                "event": event, "detail": repr(args)[:200]})

    def _sample(self) -> None:
        pid = str(os.getpid())
        while not self._stop.is_set():
            out = subprocess.run(["ss", "-tunap"], capture_output=True, text=True, check=False).stdout
            mine = [line for line in out.splitlines() if f"pid={pid}," in line]
            self.samples.append({"timestamp": now(), "source": "ss",
                                 "event": "open_sockets", "detail": len(mine)})
            for line in mine:
                self.events.append({"timestamp": now(), "source": "ss",
                                    "event": "socket", "detail": " ".join(line.split())})
            self._stop.wait(0.1)

    def __enter__(self):
        self.active = True
        self._thread = None
        if shutil.which("ss"):
            self._thread = threading.Thread(target=self._sample, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.active = False


def is_external(event: dict) -> bool:
    detail = str(event["detail"])
    local = ("127.0.0.1", "::1", "localhost", "/tmp", "@", "AF_UNIX", "u_str", "nl ")
    if event["event"] in {"socket.getaddrinfo", "socket.connect", "socket.sendto",
                          "socket.sendmsg", "http.client.connect", "urllib.Request", "socket"}:
        return not any(tok in detail for tok in local)
    return False


# Main


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path,
                        default=ROOT / "sample_receipts" / "collection-receipt-0004.jpg")
    parser.add_argument("--synthetic", type=int, default=5000,
                        help="extra receipts added for the TC-08 search timing")
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "test_results" / run_id
    for sub in ("images", "extracted", "validation", "access", "calibration", "network",
                "screenshots"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    record = Recorder(out / "raw_data.csv")
    summary: list[dict] = []

    def result(tc, kind, passed, measured, unit, threshold, notes):
        summary.append({"timestamp": now(), "test_case": tc, "type": kind,
                        "result": "PASS" if passed else "FAIL", "measured_value": measured,
                        "unit": unit, "threshold": threshold, "notes": notes})
        print(f"{tc}: {'PASS' if passed else 'FAIL'}  {measured} {unit}  {notes}")

    gt = json.loads(args.image.with_suffix(".truth.json").read_text(encoding="utf-8"))
    rid, pdate = gt["receipt_id"], gt["purchase_date"]
    stem = f"{rid}_{pdate}"

    # isolated database for this run
    engine = create_engine(f"sqlite+pysqlite:///{out / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    receipts = ReceiptRepository(factory)
    users, roles = UserRepository(factory), RoleRepository(factory)

    image_store = out / "images"

    # Calibration (Environment sheet)
    write_csv(out / "calibration" / "environment.csv", environment_rows(image_store))

    monitor = NetworkMonitor()  # hook has to be installed before the OCR import

    from rapidocr_onnxruntime import RapidOCR

    t = time.perf_counter()
    ocr = RapidOCR()
    record("CAL", "ocr_model_load_time", round((time.perf_counter() - t) * 1000, 1), "ms")

    lines, scores, elapsed = run_ocr(ocr, args.image)
    printed = score_fields(gt["printed"], lines)
    for row in printed:
        record("CAL", f"printed_char_accuracy:{row['field']}", row["char_accuracy_pct"], "%",
               receipt_id=rid)
    cal_acc = statistics.mean(r["char_accuracy_pct"] for r in printed)
    record("CAL", "printed_char_accuracy_mean", round(cal_acc, 2), "%", receipt_id=rid)
    record("CAL", "ocr_time", round(elapsed, 1), "ms", receipt_id=rid)
    write_csv(out / "calibration" / "ocr_calibration.csv",
              [{"timestamp": now(), **r} for r in printed])

    # accounts, verified against ROLE_PAGES before the security test
    create_user("admin", "admin123", RoleName.ADMIN, fullname="Test Admin",
                users=users, roles=roles)
    create_user("staff", "staff123", RoleName.STAFF, fullname="Test Staff",
                users=users, roles=roles)
    inactive = create_user("former", "former123", RoleName.STAFF, users=users, roles=roles)
    inactive.is_active = False
    users.update(inactive)
    admin_id = users.get_by_username("admin").id
    write_csv(out / "calibration" / "access_matrix.csv", [
        {"role": role.value, "page": page.value, "allowed": int(page in ROLE_PAGES[role])}
        for role in RoleName for page in Page
    ])

    # TC-01 and TC-06: import the image, run OCR, save the record, with network monitoring
    stored = image_store / f"{stem}_original{args.image.suffix.lower()}"
    with monitor:
        shutil.copy2(args.image, stored)
        lines, scores, elapsed = run_ocr(ocr, args.image)
        text_path = out / "extracted" / f"{stem}_extracted.txt"
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        sample = receipts.add(Receipt(
            user_id=admin_id, receipt_number=gt["receipt_number"],
            original_image_path=str(stored.relative_to(out)),
            purchase_date=date.fromisoformat(pdate),
            total_amount=Decimal(gt["record"]["total_amount"]),
            payer_name=gt["record"]["payer_name"], payer_address=gt["record"]["payer_address"],
        ))
    record("TC-02", "ocr_time", round(elapsed, 1), "ms", receipt_id=rid)
    record("TC-02", "text_lines_extracted", len(lines), "lines", receipt_id=rid)
    record("TC-02", "chars_extracted", sum(len(x) for x in lines), "chars", receipt_id=rid)
    record("TC-02", "mean_line_confidence", round(statistics.mean(scores), 4), "0-1",
           receipt_id=rid)

    # TC-01: stored original can be retrieved and displayed
    from PIL import Image
    from PySide6.QtGui import QImageReader, QPixmap

    def load_image(p: Path):
        # phone photos are often stored sideways with an EXIF rotation tag;
        # browsers (the web UI) apply it, plain QImage doesn't unless asked
        reader = QImageReader(str(p))
        reader.setAutoTransform(True)
        return reader.read()

    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    opened = receipts.get(sample.id)
    path = out / opened.original_image_path
    same_hash = path.exists() and sha256(path) == sha256(args.image)
    qimg = load_image(path)
    orientation = Image.open(path).getexif().get(274, 1)
    record("TC-01", "file_size", path.stat().st_size, "bytes", receipt_id=rid)
    record("TC-01", "sha256_matches_original", int(same_hash), "bool", receipt_id=rid)
    record("TC-01", "image_decodes", int(not qimg.isNull()), "bool", receipt_id=rid)
    record("TC-01", "image_width", qimg.width(), "px", receipt_id=rid)
    record("TC-01", "image_height", qimg.height(), "px", receipt_id=rid)
    record("TC-01", "exif_orientation", orientation, "EXIF code (1=upright)", receipt_id=rid,
           notes="displayed with EXIF rotation applied" if orientation != 1 else "")
    ok = same_hash and not qimg.isNull()
    result("TC-01", "FR", ok, int(ok), "bool", "stored == original and displayable",
           f"stored as images/{stored.name}; byte-identical copy, decodes at "
           f"{qimg.width()}x{qimg.height()} px"
           + (f" after applying EXIF orientation {orientation}" if orientation != 1 else ""))

    # TC-02: text produced, but the Receipt table has no column for it
    has_text_field = any("text" in f for f in Receipt.__dataclass_fields__)
    record("TC-02", "receipt_record_has_text_field", int(has_text_field), "bool",
           receipt_id=rid)
    result("TC-02", "FR", bool(lines) and has_text_field, len(lines), "lines",
           "text produced AND saved with the receipt record",
           "text was extracted, but the app has no place to store it with the record "
           "(no extracted-text column in receipt_table and OCR isn't wired into the app); "
           f"the test saved it next to the record as extracted/{text_path.name}")

    # TC-03: year / month / day search on receipts with known dates
    known = {"CR-0004": sample.id}
    for number, d, payer, total in KNOWN_RECEIPTS:
        known[number] = receipts.add(Receipt(
            user_id=admin_id, receipt_number=number, original_image_path="",
            purchase_date=d, total_amount=Decimal(total), payer_name=payer)).id
    queries = [
        ("year", ReceiptFilter(year=2026), {"OR-0001", "OR-0002", "OR-0003"}),
        ("year", ReceiptFilter(year=2025), {"CR-0004"}),
        ("month", ReceiptFilter(year=2026, month=9), {"OR-0001", "OR-0002"}),
        ("month", ReceiptFilter(month=5), {"CR-0004"}),
        ("day", ReceiptFilter(year=2026, month=9, day=17), {"OR-0002"}),
        ("day", ReceiptFilter(day=14), {"CR-0004"}),
    ]
    tc03_ok = True
    rows = []
    for level, flt, expected in queries:
        got = {r.receipt_number if r.receipt_number != "0004" else "CR-0004"
               for r in receipts.find(flt)}
        match = got == expected
        tc03_ok &= match
        crit = {k: v for k, v in vars(flt).items() if v is not None}
        record("TC-03", f"filter_{level}_correct", int(match), "bool",
               notes=f"{crit} expected={sorted(expected)} got={sorted(got)}")
        rows.append({"timestamp": now(), "level": level, "criteria": json.dumps(crit),
                     "expected": ";".join(sorted(expected)), "returned": ";".join(sorted(got)),
                     "match": int(match)})
    reopened = receipts.get(known["OR-0002"])
    opened_ok = reopened is not None and reopened.purchase_date == date(2026, 9, 17)
    record("TC-03", "open_returned_receipt", int(opened_ok), "bool", receipt_id="OR-0002")
    write_csv(out / "validation" / "TC-03_date_filter_results.csv", rows)
    result("TC-03", "FR", tc03_ok and opened_ok, sum(r["match"] for r in rows), "queries correct",
           f"{len(rows)}/{len(rows)}", "year, month and day filters each tested twice")

    # TC-04: image and text for the same record
    text_for_record = (out / "extracted" / f"{stem}_extracted.txt").exists()
    record("TC-04", "image_available", int(ok), "bool", receipt_id=rid)
    record("TC-04", "extracted_text_in_record", int(has_text_field), "bool", receipt_id=rid)
    record("TC-04", "extracted_text_file_by_naming", int(text_for_record), "bool",
           receipt_id=rid)
    result("TC-04", "FR", ok and has_text_field, int(ok and has_text_field), "bool",
           "image AND text shown for the same record",
           "image is linked to the record; extracted text is only linked by filename "
           "because the record can't hold it, and the Receipt details page isn't built yet")

    # TC-05: access control
    from receipt_manager.ui.bridge import Bridge

    access_rows = []

    def attempt(user, action, expected_allowed, fn):
        try:
            outcome = fn()
            allowed = outcome is not False
            detail = "" if outcome in (True, None) else str(outcome)[:120]
        except (InvalidCredentials, PermissionDenied) as e:
            allowed, detail = False, type(e).__name__
        row = {"timestamp": now(), "user": user, "action": action,
               "expected": "allowed" if expected_allowed else "blocked",
               "observed": "allowed" if allowed else "blocked",
               "result": "PASS" if allowed == expected_allowed else "FAIL", "detail": detail}
        access_rows.append(row)
        record("TC-05", f"{user}:{action}", int(allowed == expected_allowed), "pass=1",
               receipt_id=rid, notes=f"expected {row['expected']}, observed {row['observed']}")

    def role_checks(user: str, password: str, authorized: bool) -> None:
        auth = AuthService(users, roles)
        attempt(user, "login", True, lambda: bool(auth.login(user, password)))
        attempt(user, "open_search_page", authorized, lambda: auth.can_access(Page.SEARCH))
        attempt(user, "require_search", authorized, lambda: auth.require(Page.SEARCH))
        attempt(user, "require_data_management", authorized,
                lambda: auth.require(Page.DATA_MANAGEMENT))
        bridge = Bridge(auth, receipts)
        if not authorized:
            attempt(user, "bridge_clearReceipts", False,
                    lambda: "error" not in json.loads(bridge.clearReceipts()))
        attempt(user, "bridge_getStats_receipt_totals", authorized,
                lambda: json.loads(bridge.getStats()))

    role_checks("admin", "admin123", authorized=True)
    role_checks("staff", "staff123", authorized=False)
    attempt("staff", "login_wrong_password", False,
            lambda: bool(AuthService(users, roles).login("staff", "wrong")))
    attempt("former", "login_deactivated", False,
            lambda: bool(AuthService(users, roles).login("former", "former123")))
    nobody = AuthService(users, roles)
    attempt("not_logged_in", "open_search_page", False, lambda: nobody.can_access(Page.SEARCH))
    write_csv(out / "access" / f"TC-05_{rid}_access.csv", access_rows)
    failed = [f"{r['user']}:{r['action']}" for r in access_rows if r["result"] == "FAIL"]
    result("TC-05", "NFR", not failed, len(access_rows) - len(failed), "checks passed",
           f"{len(access_rows)}/{len(access_rows)}",
           "page-level role checks work; " + (
               f"failed: {', '.join(failed)} (Home page stats like total receipt count and "
               "amount are returned to any logged-in role without a permission check)"
               if failed else "no unauthorized access observed"))

    # TC-06: network activity during the workflow
    external = [e for e in monitor.events if is_external(e)]
    record("TC-06", "socket_events_total", len(monitor.events), "events")
    record("TC-06", "external_transmissions", len(external), "events")
    record("TC-06", "ss_samples", len(monitor.samples), "samples",
           notes="open sockets of this process sampled every 100 ms")
    record("TC-06", "max_open_sockets",
           max((s["detail"] for s in monitor.samples), default=0), "sockets")
    net_rows = monitor.samples + monitor.events
    write_csv(out / "network" / "TC-06_network_log.csv",
              sorted(net_rows, key=lambda r: r["timestamp"]) or
              [{"timestamp": now(), "source": "", "event": "none", "detail": ""}])
    result("TC-06", "NFR", not external, len(external), "external transmissions", "0",
           "covers import -> OCR (RapidOCR) -> save; the Gemini test app in ocr/ was NOT "
           "run and would send images to Google")

    # TC-07: OCR accuracy against ground truth
    t07 = []
    for i in range(1, 4):
        lines_i, _, ms = run_ocr(ocr, args.image)
        record("TC-07", "ocr_time", round(ms, 1), "ms", receipt_id=rid, iteration=i)
        fields = score_fields(gt["handwritten"], lines_i)
        acc = statistics.mean(f["char_accuracy_pct"] for f in fields)
        exact = 100 * statistics.mean(f["exact_match"] for f in fields)
        record("TC-07", "handwritten_char_accuracy_mean", round(acc, 2), "%",
               receipt_id=rid, iteration=i)
        record("TC-07", "handwritten_field_exact_match_rate", round(exact, 2), "%",
               receipt_id=rid, iteration=i)
        t07.append(acc)
    for f in fields:
        record("TC-07", f"char_accuracy:{f['field']}", f["char_accuracy_pct"], "%",
               receipt_id=rid)
    write_csv(out / "validation" / f"{stem}_validation.csv",
              [{"timestamp": now(), "receipt_id": rid, "kind": "handwritten", **f}
               for f in fields] +
              [{"timestamp": now(), "receipt_id": rid, "kind": "printed", **f}
               for f in printed])
    acc = round(statistics.mean(t07), 2)
    target, unit, _, desc = THRESHOLDS["TC-07"]
    result("TC-07", "NFR", acc >= target, acc, unit, f">= {target} (provisional)",
           f"{desc}; batch of 1 receipt, exact field match {exact:.1f}%, "
           f"printed text {cal_acc:.1f}%")

    # TC-08: date search response time on a representative set
    rng = random.Random(42)  # same synthetic data every run
    start_day = date(2023, 1, 1)
    batch = [Receipt(user_id=admin_id, receipt_number=f"SYN-{i:05d}", original_image_path="",
                     purchase_date=start_day + timedelta(days=rng.randrange(0, 1400)),
                     total_amount=Decimal(rng.randrange(100, 200000)),
                     payer_name=f"Synthetic Payer {i % 40}")
             for i in range(args.synthetic)]
    t = time.perf_counter()
    with factory.begin() as session:
        from receipt_manager.data import mappers
        session.add_all(mappers.receipt_to_row(r) for r in batch)
    record("TC-08", "dataset_receipts", receipts.count(), "receipts",
           notes=f"{args.synthetic} synthetic (seed 42) + 4 known; insert took "
                 f"{(time.perf_counter() - t) * 1000:.0f} ms")
    all_dates = [r.purchase_date for r in receipts.list_all()]
    searches = [
        ("year", ReceiptFilter(year=2025), lambda d: d.year == 2025),
        ("year_month", ReceiptFilter(year=2025, month=5), lambda d: (d.year, d.month) == (2025, 5)),
        ("year_month_day", ReceiptFilter(year=2025, month=5, day=14),
         lambda d: d == date(2025, 5, 14)),
        ("date_range", ReceiptFilter(date_from=date(2024, 1, 1), date_to=date(2024, 3, 31)),
         lambda d: date(2024, 1, 1) <= d <= date(2024, 3, 31)),
    ]
    all_ms = []
    for name, flt, pred in searches:
        expected = sum(pred(d) for d in all_dates)
        for _ in range(3):  # warm-up, not recorded
            receipts.find(flt)
        for i in range(1, args.iterations + 1):
            t = time.perf_counter()
            found = receipts.find(flt)
            ms = (time.perf_counter() - t) * 1000
            all_ms.append(ms)
            record("TC-08", f"search_time:{name}", round(ms, 3), "ms", iteration=i,
                   notes=f"{len(found)} results, expected {expected}")
        record("TC-08", f"result_count_correct:{name}", int(len(found) == expected), "bool")
    target, unit, _, desc = THRESHOLDS["TC-08"]
    value = round(p95(all_ms), 2)
    record("TC-08", "search_time_p95", value, "ms")
    record("TC-08", "search_time_mean", round(statistics.mean(all_ms), 2), "ms")
    result("TC-08", "NFR", value <= target, value, unit, f"<= {target} (provisional)",
           f"{desc}; {len(all_ms)} searches over {receipts.count()} receipts, "
           f"max {max(all_ms):.1f} ms")

    # TC-09: open a record and render the image and text side by side (Qt, offscreen)
    text = text_path.read_text(encoding="utf-8")
    render_ms = []
    for i in range(1, args.iterations + 1):
        t = time.perf_counter()
        rec = receipts.get(sample.id)
        view = QWidget()
        layout = QHBoxLayout(view)
        picture = QLabel()
        picture.setPixmap(QPixmap.fromImage(load_image(out / rec.original_image_path))
                          .scaledToWidth(900))
        body = QPlainTextEdit()
        body.setPlainText(text)
        layout.addWidget(picture)
        layout.addWidget(body)
        view.resize(1400, 600)
        view.show()
        app.processEvents()
        shot = view.grab()  # forces a full paint
        ms = (time.perf_counter() - t) * 1000
        render_ms.append(ms)
        record("TC-09", "open_and_render_time", round(ms, 2), "ms", receipt_id=rid, iteration=i)
        if i == 1:
            shot.save(str(out / "screenshots" / "TC-09_rendered_record_view.png"))
        view.close()
        view.deleteLater()
    target, unit, _, desc = THRESHOLDS["TC-09"]
    value = round(p95(render_ms), 2)
    record("TC-09", "open_and_render_time_p95", value, "ms", receipt_id=rid)
    result("TC-09", "NFR", value <= target, value, unit, f"<= {target} (provisional)",
           f"{desc}; Qt split view stand-in since the Receipt details page isn't built, "
           f"mean {statistics.mean(render_ms):.1f} ms")

    # TC-10: storage capacity
    usage = shutil.disk_usage(image_store)
    free_gb = round(usage.free / 1e9, 2)
    avg_image = stored.stat().st_size
    record("TC-10", "storage_total", round(usage.total / 1e9, 2), "GB")
    record("TC-10", "storage_used", round(usage.used / 1e9, 2), "GB")
    record("TC-10", "storage_free", free_gb, "GB")
    record("TC-10", "image_size_per_receipt", avg_image, "bytes", receipt_id=rid)
    record("TC-10", "estimated_receipt_capacity", usage.free // avg_image, "receipts",
           notes="free space / size of the sample image")
    target, unit, _, desc = THRESHOLDS["TC-10"]
    result("TC-10", "NFR", free_gb >= target, free_gb, unit, f">= {target} (provisional)",
           f"{desc}; about {usage.free // avg_image:,} receipts at {avg_image / 1e3:.0f} KB each; "
           "no space is reserved/allocated for the app")

    record.close()
    write_csv(out / "summary.csv", summary)
    print(f"\nresults in {out}")


if __name__ == "__main__":
    main()
