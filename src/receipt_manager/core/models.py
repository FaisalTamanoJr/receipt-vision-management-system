"""
Application uses this code to interact with the
database. The data/mappers.py will allow the changes
to reflect in SQLAlchemy.

Helpful reference:
https://docs.python.org/3/library/dataclasses.html
"""

from __future__ import annotations  # for forward references detection

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# User


@dataclass
class Role:
    id: int | None = None

    name: str
    users: list[User] = field(default_factory=list)


@dataclass
class Login:
    id: int | None = None
    user_id: int

    username: str
    password: str


@dataclass
class User:
    id: int | None = None
    role_id: int
    login_id: int

    fullname: str
    phone: str
    email: str
    birthday: date | None = None
    date_created: date = field(default_factory=date.today)

    receipts: list[Receipt] = field(default_factory=list)


# Receipts
@dataclass
class Receipt:
    id: int | None = None
    user_id: int

    receipt_number: str
    original_image_path: str
    purchase_date: date

    @property
    def purchase_year(self) -> int:
        return self.purchase_date.year

    @property
    def purchase_month(self) -> int:
        return self.purchase_date.month

    @property
    def purchase_day(self) -> int:
        return self.purchase_date.day

    upload_date: datetime = field(default_factory=datetime.now)
    total_amount: Decimal
    payer_name: str
    payer_address: str
    payer_tin: str
    payer_method: str
    check_number: str
    bank_branch: str

    items: list[ReceiptItem] = field(default_factory=list)


@dataclass
class ReceiptItem:
    id: int | None = None
    receipt_id: int | None = None
    inventory_item_id: int | None = None

    quantity: int
    unit_price: Decimal
    total_price: Decimal


# Inventory
@dataclass
class ProductType:
    id: int | None = None

    name: str
    inventory_item: list[InventoryItem] = field(default_factory=list)


@dataclass
class InventoryItem:
    id: int | None = None

    product_type_id: int
    supplier_id: int | None = None
    name: str
    average_daily_consumption: Decimal

    receipt_items: list[ReceiptItem] = field(default_factory=list)


@dataclass
class StockLedger:
    id: int | None = None

    inventory_item_id: int
    current_quantity: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Supplier:
    id: int | None = None

    name: str
    contact_info: str

    items: list[InventoryItem] = field(default_factory=list)
