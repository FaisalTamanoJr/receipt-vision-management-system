from __future__ import annotations  # for forward references detection

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# User


@dataclass
class Role:
    id: int | None = None
    name: str


@dataclass
class Login:
    id: int | None = None
    username: str
    password_hash: str


@dataclass
class User:
    id: int | None = None
    role_id: int
    fullname: str
    phone: str
    email: str
    birthday: date | None = None
    date_created: date = field(default_factory=date.today)


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


@dataclass
class InventoryItem:
    id: int | None = None
    product_type_id: int
    name: str
    average_daily_consumption: Decimal


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
