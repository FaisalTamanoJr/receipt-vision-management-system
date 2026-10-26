"""
Application uses this code to interact with the
database. The data/mappers.py will allow the changes
to reflect in SQLAlchemy.

Helpful reference:
https://docs.python.org/3/library/dataclasses.html
"""

from __future__ import annotations  # for forward references detection

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

# User


@dataclass(kw_only=True)
class Role:
    id: int | None = None

    name: str
    users: list[User] = field(default_factory=list)


@dataclass(kw_only=True)
class Login:
    id: int | None = None
    user_id: int

    username: str
    password: str


@dataclass(kw_only=True)
class User:
    id: int | None = None
    role_id: int

    fullname: str | None = None
    phone: str | None = None
    email: str | None = None
    birthday: date | None = None
    date_created: date = field(default_factory=date.today)

    login: Login | None = None
    receipts: list[Receipt] = field(default_factory=list)


# Receipts
@dataclass(kw_only=True)
class Receipt:
    id: int | None = None
    user_id: int

    receipt_number: str
    original_image_path: str
    purchase_date: date
    upload_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_amount: Decimal
    payer_name: str
    payer_address: str = ""
    payer_tin: str = ""
    payment_method: str = ""
    check_number: str = ""
    bank_branch: str = ""

    items: list[ReceiptItem] = field(default_factory=list)

    @property
    def purchase_year(self) -> int:
        return self.purchase_date.year

    @property
    def purchase_month(self) -> int:
        return self.purchase_date.month

    @property
    def purchase_day(self) -> int:
        return self.purchase_date.day


@dataclass(kw_only=True)
class ReceiptItem:
    id: int | None = None
    receipt_id: int | None = None
    inventory_item_id: int | None = None

    quantity: int
    unit_price: Decimal
    total_price: Decimal


# Inventory
@dataclass(kw_only=True)
class ProductType:
    id: int | None = None

    name: str
    products: list[InventoryItem] = field(default_factory=list)


@dataclass(kw_only=True)
class InventoryItem:
    id: int | None = None

    product_type_id: int
    supplier_id: int
    name: str
    average_daily_consumption: Decimal = Decimal(0)

    receipt_items: list[ReceiptItem] = field(default_factory=list)
    stock_ledger: StockLedger | None = None


@dataclass(kw_only=True)
class StockLedger:
    id: int | None = None

    inventory_item_id: int
    current_quantity: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(kw_only=True)
class Supplier:
    id: int | None = None

    name: str
    contact_info: str = ""

    products: list[InventoryItem] = field(default_factory=list)
