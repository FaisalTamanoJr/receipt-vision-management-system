"""
The object the HTML pages talk to. It is exposed to JavaScript
through QWebChannel as `bridge`, see js/common.js for the JS side.

Every slot returns a JSON string, because QWebChannel only passes
simple types. Keep database work in the repositories, this file
only shapes their results for the pages.

Helpful reference:
https://doc.qt.io/qtforpython-6/PySide6/QtWebChannel/QWebChannel.html
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from receipt_manager.auth.permissions import Page
from receipt_manager.auth.service import (
    AuthService,
    InvalidCredentials,
    PermissionDenied,
    UsernameTaken,
)
from receipt_manager.data.engine import data_dir
from receipt_manager.data.repository import ReceiptFilter, ReceiptRepository

SETTINGS_FILE = data_dir / "settings.json"

# same keys as the defaults in js/common.js
DEFAULT_SETTINGS = {
    "username": "User",
    "darkMode": False,
    "dateFormat": "MMM DD, YYYY",
    "passwordChanged": None,
    "autoSignOut": "30",
    "llmEnabled": True,
    "llmModel": "claude-sonnet-5-5",
    "storagePath": str(data_dir / "receipts"),
    "notifyScan": True,
    "notifyReview": True,
    "notifyStorage": False,
}


def load_settings() -> dict:
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {**DEFAULT_SETTINGS, **saved}


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _folder_size(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def _human_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + n
    return total // 12, total % 12 + 1


class Bridge(QObject):
    # emitted after save_settings() so the window can refresh the injected settings
    settingsChanged = Signal(str)
    # emitted when the page asks to sign out, the window shows the login dialog again
    signedOut = Signal()

    def __init__(
        self, auth: AuthService, receipts: ReceiptRepository | None = None
    ) -> None:
        super().__init__()
        self._auth = auth
        self._receipts = receipts or ReceiptRepository()

    def _month_total(self, year: int, month: int) -> Decimal:
        return self._receipts.total_amount(ReceiptFilter(year=year, month=month))

    # totals for days 1-7, 8-14, 15-21 and 22 to the end of the month
    def _weekly_totals(self, year: int, month: int) -> list[float]:
        weeks = [Decimal(0)] * 4
        for r in self._receipts.find(ReceiptFilter(year=year, month=month)):
            weeks[min((r.purchase_date.day - 1) // 7, 3)] += r.total_amount
        return [float(w) for w in weeks]

    @Slot(result=str)
    def getStats(self) -> str:
        today = date.today()
        storage = _folder_size(data_dir)
        storage_path = Path(load_settings()["storagePath"])
        if not storage_path.is_relative_to(data_dir):
            storage += _folder_size(storage_path)
        return json.dumps(
            {
                "total": self._receipts.count(),
                "month": self._receipts.count_matching(
                    ReceiptFilter(year=today.year, month=today.month)
                ),
                "amount": float(self._receipts.total_amount()),
                "storage": _human_size(storage),
            }
        )

    @Slot(result=str)
    def getMonthlyComparison(self) -> str:
        today = date.today()
        last = _previous_month(today.year, today.month)
        this_total = self._month_total(today.year, today.month)
        last_total = self._month_total(*last)
        growth = (
            float((this_total - last_total) / last_total * 100) if last_total else None
        )
        return json.dumps(
            {
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "lastMonth": self._weekly_totals(*last),
                "thisMonth": self._weekly_totals(today.year, today.month),
                "growth": growth,
            }
        )

    # the last 6 months of actual totals, then `months` months projected
    # with a straight line fitted through those 6 months
    @Slot(int, result=str)
    def getProjection(self, months: int) -> str:
        today = date.today()
        history = [_add_months(today.year, today.month, -i) for i in range(5, -1, -1)]
        actual = [float(self._month_total(y, m)) for y, m in history]

        n = len(actual)
        mean_x = (n - 1) / 2
        mean_y = sum(actual) / n
        slope = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(actual)) / sum(
            (x - mean_x) ** 2 for x in range(n)
        )
        projected = [
            max(0.0, mean_y + slope * (n - 1 + i - mean_x))
            for i in range(1, months + 1)
        ]
        future = [_add_months(today.year, today.month, i) for i in range(1, months + 1)]

        def label(y: int, m: int) -> str:
            return date(y, m, 1).strftime("%b %Y")

        return json.dumps(
            {
                "labels": [label(*ym) for ym in history]
                + [label(*ym) for ym in future],
                # the projection starts at the last actual point so the lines connect
                "actual": actual + [None] * months,
                "projected": [None] * (n - 1) + [actual[-1]] + projected,
            }
        )

    @Slot(result=str)
    def getSettings(self) -> str:
        return json.dumps(load_settings())

    @Slot(str, result=str)
    def saveSettings(self, settings_json: str) -> str:
        settings = {**load_settings(), **json.loads(settings_json)}
        save_settings(settings)
        text = json.dumps(settings)
        self.settingsChanged.emit(text)
        return text

    # deletes every receipt record, the scanned image files are left alone for now
    @Slot(result=str)
    def clearReceipts(self) -> str:
        try:
            self._auth.require(Page.DATA_MANAGEMENT)
        except PermissionDenied:
            return json.dumps({"error": "Only an admin can clear the receipts."})
        deleted = 0
        for r in self._receipts.list_all():
            deleted += self._receipts.delete(r.id)
        return json.dumps({"deleted": deleted})

    @Slot(result=str)
    def getCurrentUser(self) -> str:
        user = self._auth.current_user
        if user is None:
            return json.dumps(None)
        return json.dumps(
            {
                "username": user.login.username,
                "fullname": user.fullname,
                "role": self._auth.current_role.value,
                "pages": [p.value for p in Page if self._auth.can_access(p)],
            }
        )

    # both return {"error": "..."} when the change is refused, so the page can show it
    @Slot(str, str, result=str)
    def changePassword(self, current: str, new: str) -> str:
        try:
            self._auth.change_password(current, new)
        except InvalidCredentials:
            return json.dumps({"error": "Your current password is wrong."})
        return json.dumps({})

    @Slot(str, result=str)
    def changeUsername(self, new: str) -> str:
        try:
            self._auth.change_username(new)
        except UsernameTaken:
            return json.dumps({"error": "That username is already taken."})
        return json.dumps({})

    @Slot(result=str)
    def signOut(self) -> str:
        self.signedOut.emit()
        return json.dumps({})
